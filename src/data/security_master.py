"""Authoritative Security Master and Symbol Resolution Engine.

Powered by official CNINFO (巨潮资讯) statutory disclosure stock master catalog.
Provides in-memory indexing, ranking, search, caching and offline failover.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional
from pydantic import BaseModel, Field

_logger = logging.getLogger(__name__)

SECURITY_MASTER_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "security_master.json"
)

CNINFO_STOCK_JSON_URL = "http://www.cninfo.com.cn/new/data/szse_stock.json"

# Explicit supported US aliases share the existing selector and resolver. Unknown
# symbols are not guessed. A full US exchange catalogue can replace this seed later.
US_SECURITIES = {
    "AAPL": ("Apple", "NASDAQ", ("apple", "apple inc", "apple inc.")),
    "MSFT": ("Microsoft", "NASDAQ", ("microsoft", "microsoft corporation")),
    "NVDA": ("NVIDIA", "NASDAQ", ("nvidia", "nvidia corporation")),
    "TSLA": ("Tesla", "NASDAQ", ("tesla", "tesla inc")),
    "AMZN": ("Amazon", "NASDAQ", ("amazon", "amazon.com")),
    "GOOGL": ("Alphabet", "NASDAQ", ("alphabet", "google")),
}


class Security(BaseModel):
    symbol: str = Field(description="6位证券代码，如 600519")
    canonical_symbol: str = Field(description="系统标准提交代码，如 600519")
    name: str = Field(description="中文简称，如 贵州茅台")
    pinyin: str = Field(default="", description="官方拼音缩写，如 gzmt")
    exchange: str = Field(description="交易所代号：SSE, SZSE, BSE")
    exchange_name: str = Field(description="交易所显示全称，如 上海证券交易所")
    board: str = Field(description="板块：主板, 科创板, 创业板, 北交所")
    market: str = Field(default="CN", description="所属市场：CN")
    asset_type: str = Field(default="stock", description="资产类型")
    org_id: Optional[str] = Field(default=None, description="巨潮资讯机构代码")


class SearchResultItem(BaseModel):
    symbol: str
    canonical_symbol: str
    name: str
    pinyin: str
    exchange: str
    exchange_name: str
    board: str
    market: str
    asset_type: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total_matches: int
    has_more: bool
    cached: bool = True
    last_updated: str = ""


class ResolveResponse(BaseModel):
    query: str
    resolved: bool
    security: Optional[SearchResultItem] = None
    ambiguous: bool = False
    candidates: list[SearchResultItem] = Field(default_factory=list)
    message: str = ""


def classify_exchange_board(code: str) -> tuple[str, str, str, str]:
    """Accurately classify exchange, exchange name and board by A-share code rules."""
    code_str = str(code).strip()
    if code_str.startswith(("600", "601", "603", "605")):
        return "SSE", "上海证券交易所", "主板", "CN"
    elif code_str.startswith("688"):
        return "SSE", "上海证券交易所", "科创板", "CN"
    elif code_str.startswith(("000", "001")):
        return "SZSE", "深圳证券交易所", "主板", "CN"
    elif code_str.startswith(("002", "003")):
        return "SZSE", "深圳证券交易所", "主板", "CN"
    elif code_str.startswith(("300", "301")):
        return "SZSE", "深圳证券交易所", "创业板", "CN"
    elif code_str.startswith(("8", "4", "92")):
        return "BSE", "北京证券交易所", "北交所", "CN"
    return "OTHER", "其他交易所", "其他", "CN"


class SecurityMaster:
    """Singleton in-memory cache and search engine for A-share securities."""
    _instance: Optional[SecurityMaster] = None

    def __init__(self):
        self._securities: list[Security] = []
        self._by_symbol: dict[str, Security] = {}
        self._by_name: dict[str, Security] = {}
        self._last_loaded_time: float = 0
        self._cache_duration_seconds: float = 24 * 60 * 60  # 24 hours
        self._last_updated_date: str = "2026-09-29"
        self._initialize()

    @classmethod
    def get_instance(cls) -> SecurityMaster:
        if cls._instance is None:
            cls._instance = SecurityMaster()
        return cls._instance

    def _initialize(self):
        """Load from local disk cache first, then attempt network refresh if stale."""
        loaded = self._load_from_disk()
        if not loaded or (time.time() - self._last_loaded_time > self._cache_duration_seconds):
            try:
                self.refresh()
            except Exception as e:
                _logger.warning("Network refresh of Security Master failed, using local cache: %s", e)

    def _load_from_disk(self) -> bool:
        if not os.path.exists(SECURITY_MASTER_CACHE_FILE):
            return False
        try:
            with open(SECURITY_MASTER_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_list = data.get("securities", [])
            self._last_updated_date = data.get("updated_at", "2026-09-29")
            self._populate_index(raw_list)
            self._last_loaded_time = os.path.getmtime(SECURITY_MASTER_CACHE_FILE)
            _logger.info("Loaded %d securities from local cache file", len(self._securities))
            return len(self._securities) > 0
        except Exception as e:
            _logger.error("Failed to load local security master cache: %s", e)
            return False

    def _save_to_disk(self):
        os.makedirs(os.path.dirname(SECURITY_MASTER_CACHE_FILE), exist_ok=True)
        try:
            with open(SECURITY_MASTER_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "total": len(self._securities),
                    "updated_at": self._last_updated_date,
                    "securities": [s.model_dump() for s in self._securities]
                }, f, ensure_ascii=False, indent=2)
            _logger.info("Saved %d securities to %s", len(self._securities), SECURITY_MASTER_CACHE_FILE)
        except Exception as e:
            _logger.error("Failed to save security master to disk: %s", e)

    def _populate_index(self, raw_list: list[dict]):
        sec_list = []
        by_symbol = {}
        by_name = {}
        for item in raw_list:
            sec = Security(**item)
            sec_list.append(sec)
            by_symbol[sec.symbol] = sec
            by_name[sec.name] = sec
        for code, (name, exchange, _) in US_SECURITIES.items():
            if code in by_symbol:
                continue
            sec = Security(symbol=code, canonical_symbol=code, name=name, exchange=exchange,
                           exchange_name=exchange, board="US equity", market="US")
            sec_list.append(sec)
            by_symbol[code] = sec
            by_name[name] = sec
        self._securities = sec_list
        self._by_symbol = by_symbol
        self._by_name = by_name

    def refresh(self) -> int:
        """Fetch latest authoritative stock list from CNINFO."""
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        resp = requests.get(CNINFO_STOCK_JSON_URL, headers=headers, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        raw_stocks = data.get("stockList", [])
        if not raw_stocks:
            raise ValueError("Empty stock list returned from CNINFO")

        processed = []
        for s in raw_stocks:
            code = str(s.get("code", "")).strip().zfill(6)
            name = str(s.get("zwjc", "")).strip()
            pinyin = str(s.get("pinyin", "")).strip().lower()
            org_id = str(s.get("orgId", "")).strip()
            exch, exch_name, board, market = classify_exchange_board(code)

            processed.append({
                "symbol": code,
                "canonical_symbol": code,
                "name": name,
                "pinyin": pinyin,
                "exchange": exch,
                "exchange_name": exch_name,
                "board": board,
                "market": market,
                "asset_type": "stock",
                "org_id": org_id or None
            })

        import datetime
        self._last_updated_date = datetime.date.today().isoformat()
        self._populate_index(processed)
        self._last_loaded_time = time.time()
        self._save_to_disk()
        return len(self._securities)

    def search(self, query: str, limit: int = 10) -> SearchResponse:
        """High-performance multi-tier ranking search."""
        q = query.strip()
        if not q:
            # Return popular core assets by default when empty
            popular = ["600519", "000001", "300750", "600036", "000858", "688981", "601318", "002594"]
            matched = [SearchResultItem(**self._by_symbol[c].model_dump()) for c in popular if c in self._by_symbol]
            return SearchResponse(
                query="",
                results=matched[:limit],
                total_matches=len(matched),
                has_more=False,
                cached=True,
                last_updated=self._last_updated_date
            )

        q_lower = q.lower()
        scored_items: list[tuple[int, Security]] = []

        for sec in self._securities:
            score = 0
            # 1. Exact symbol match (Highest priority)
            if sec.symbol == q:
                score += 1000
            # 2. Prefix symbol match
            elif sec.symbol.startswith(q):
                score += 800 - len(sec.symbol)
            # 3. Exact name match
            if sec.name == q:
                score += 900
            # 4. Name prefix match
            elif sec.name.startswith(q):
                score += 700 - len(sec.name)
            # 5. Pinyin exact match
            if sec.pinyin and sec.pinyin == q_lower:
                score += 650
            # 6. Pinyin prefix match
            elif sec.pinyin and sec.pinyin.startswith(q_lower):
                score += 550 - len(sec.pinyin)
            # 7. Name contains match
            elif q in sec.name:
                score += 350 - sec.name.find(q) * 10
            # 8. Pinyin contains match
            elif sec.pinyin and q_lower in sec.pinyin:
                score += 250 - sec.pinyin.find(q_lower) * 10
            # 9. Symbol contains match
            elif q in sec.symbol:
                score += 150 - sec.symbol.find(q) * 10

            if score > 0:
                scored_items.append((score, sec))

        # Sort descending by score
        scored_items.sort(key=lambda x: x[0], reverse=True)
        total_matches = len(scored_items)
        has_more = total_matches > limit
        top_results = [SearchResultItem(**item[1].model_dump()) for item in scored_items[:limit]]

        return SearchResponse(
            query=query,
            results=top_results,
            total_matches=total_matches,
            has_more=has_more,
            cached=True,
            last_updated=self._last_updated_date
        )

    def resolve(self, query: str) -> ResolveResponse:
        """Deterministic resolver: resolve code or name into canonical security or clarify ambiguity."""
        q = query.strip()
        if not q:
            return ResolveResponse(query="", resolved=False, message="查询为空")
        for code, (_, _, aliases) in US_SECURITIES.items():
            if q.upper() == code or q.casefold() in aliases:
                q = code
                break
        if re.fullmatch(r"(?:SH|SZ|BJ)\d{6}", q.upper()):
            q = q[2:]
        if re.fullmatch(r"\d{6}\.(?:SH|SZ|BJ)", q.upper()):
            q = q[:6]

        # 1. Direct code hit
        if q in self._by_symbol:
            sec = self._by_symbol[q]
            return ResolveResponse(
                query=query,
                resolved=True,
                security=SearchResultItem(**sec.model_dump()),
                ambiguous=False,
                message=f"已精确匹配代码: {sec.name} ({sec.symbol})"
            )

        # 2. Direct name hit
        if q in self._by_name:
            sec = self._by_name[q]
            return ResolveResponse(
                query=query,
                resolved=True,
                security=SearchResultItem(**sec.model_dump()),
                ambiguous=False,
                message=f"已精确匹配公司名称: {sec.name} ({sec.symbol})"
            )

        # 3. Fuzzy search for single unambiguous match
        search_res = self.search(q, limit=10)
        if search_res.total_matches == 1:
            item = search_res.results[0]
            return ResolveResponse(
                query=query,
                resolved=True,
                security=item,
                ambiguous=False,
                message=f"已匹配唯一标的: {item.name} ({item.symbol})"
            )
        elif search_res.total_matches > 1:
            return ResolveResponse(
                query=query,
                resolved=False,
                ambiguous=True,
                candidates=search_res.results,
                message=f"匹配到 {search_res.total_matches} 只相关股票，请在下拉列表中明确选择"
            )

        return ResolveResponse(
            query=query,
            resolved=False,
            ambiguous=False,
            message="未找到匹配股票，请检查股票代码或公司名称"
        )
