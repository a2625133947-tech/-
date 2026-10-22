"""Adapters for the project's existing BaoStock and AKShare source calls.

The legacy transport helpers stay in a_share during incremental migration so
existing tests and callers keep their behavior. No new source is added here.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.capabilities import AccessTier, Capability, Market
from src.data.domain import (
    Adjustment, CompanyProfile, DataEnvelope, DataStatus, DividendEvent, FinancialField,
    FinancialStatement, Instrument, NewsItem, ObservedValue, PriceBar, Quality,
    ShareCapitalEvent, StatementType, Unit, ValuationSnapshot,
)
from src.data.errors import InvalidData, ProviderFailure, SchemaChanged, UnsupportedCapability, classify_provider_error
from src.data.providers import DataRequest, ProviderDescriptor
from src.tools import a_share

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _published_on(day: date) -> datetime:
    # Source exposes a date, not a release time: use date-level visibility only.
    return datetime.combine(day, time.min, SHANGHAI).astimezone(timezone.utc)


def _instrument(ticker: str) -> Instrument:
    code, _, _ = a_share.normalize_ticker(ticker)
    return Instrument(ticker=ticker, market=Market.CN_SH if code.startswith("sh.") else Market.CN_SZ,
                      currency=Unit.CNY)


def _wrap(value, provider: str, request: DataRequest, retrieved: datetime,
          available: datetime, unit: Unit = Unit.NONE, quality: Quality = Quality.UNVERIFIED,
          raw_hash: str | None = None):
    return DataEnvelope(status=DataStatus.PRESENT, provider=provider, observation=ObservedValue(
        value=value, provider=provider, observed_date=request.end_date or request.as_of.date(),
        available_at=available, retrieved_at=retrieved, unit=unit, quality=quality), raw_hash=raw_hash)


def _hash_payload(payload) -> str:
    encoded = (payload if isinstance(payload, str) else
               json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
    return sha256(encoded.encode("utf-8")).hexdigest()


class BaoStockProvider:
    provider_id = "baostock"
    capabilities = frozenset({Capability.PRICE_DAILY, Capability.VOLUME, Capability.PE, Capability.PB,
                              Capability.PS, Capability.VALUATION_HISTORY, Capability.INSTRUMENT_METADATA,
                              Capability.PRICE_ADJUSTED, Capability.INDUSTRY, Capability.DIVIDEND})
    markets = frozenset({Market.CN_SH, Market.CN_SZ})
    access_tier = AccessTier.FREE

    def supports(self, request: DataRequest) -> bool:
        return request.instrument.market in self.markets and request.capability in self.capabilities

    @staticmethod
    def fetch_raw_history(code: str, start_date: str, end_date: str) -> tuple[dict, ...]:
        import baostock as bs

        fields = a_share._index_fields if code == "sh.000300" else a_share._stock_fields
        with a_share._baostock_lock:
            a_share._logger.debug("BaoStock daily history: %s %s to %s fields=%s",
                                  code, start_date, end_date, fields)
            login = bs.login()
            if login.error_code != "0":
                raise ProviderFailure(f"BaoStock login failed: {login.error_code}")
            try:
                result = bs.query_history_k_data_plus(
                    code, fields, start_date=start_date, end_date=end_date,
                    frequency="d", adjustflag="3")
                if result.error_code != "0":
                    raise ProviderFailure(f"BaoStock daily query failed: {result.error_code}")
                rows = []
                while result.next():
                    rows.append(dict(zip(result.fields, result.get_row_data())))
                return tuple(rows)
            finally:
                bs.logout()

    def _rows(self, request: DataRequest) -> tuple[dict, ...]:
        if not self.supports(request):
            raise UnsupportedCapability(request.capability)
        if request.start_date is None or request.end_date is None:
            raise InvalidData("start_date and end_date are required")
        code, _, _ = a_share.normalize_ticker(request.instrument.ticker)
        try:
            return a_share._history(code, request.start_date.isoformat(), request.end_date.isoformat())
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise classify_provider_error(exc) from exc

    def get_price_history(self, request: DataRequest) -> DataEnvelope[list[PriceBar]]:
        if request.capability is Capability.PRICE_ADJUSTED:
            return self.get_adjusted_history(request)
        if request.capability not in (Capability.PRICE_DAILY, Capability.VOLUME) or request.adjustment is not Adjustment.UNADJUSTED:
            raise UnsupportedCapability("only unadjusted daily prices are implemented")
        rows = self._rows(request)
        retrieved = datetime.now(timezone.utc)
        instrument = request.instrument
        bars = []
        for row in rows:
            values = [a_share._number(row.get(key)) for key in ("open", "close", "high", "low", "volume")]
            if any(value is None for value in values):
                continue  # Preserve the legacy API's missing-row behavior.
            try:
                bars.append(PriceBar(instrument=instrument, trading_date=date.fromisoformat(row["date"]),
                                     open=Decimal(str(values[0])), close=Decimal(str(values[1])),
                                     high=Decimal(str(values[2])), low=Decimal(str(values[3])),
                                     volume=Decimal(int(values[4])), adjustment=Adjustment.UNADJUSTED))
            except (KeyError, TypeError, ValueError) as exc:
                raise InvalidData(f"invalid price row: {exc}") from exc
        if not bars:
            return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=self.provider_id)
        return _wrap(bars, self.provider_id, request, retrieved, _published_on(bars[-1].trading_date),
                     Unit.CNY, Quality.VALIDATED)

    @staticmethod
    def fetch_raw_adjusted(code: str, start: str, end: str, flag: str) -> tuple[tuple[dict, ...], tuple[dict, ...], tuple[dict, ...]]:
        import baostock as bs

        with a_share._baostock_lock:
            login = bs.login()
            if login.error_code != "0":
                raise ProviderFailure(f"BaoStock login failed: {login.error_code}")
            try:
                def rows(result):
                    if result.error_code != "0":
                        raise ProviderFailure(f"BaoStock query failed: {result.error_code}")
                    output = []
                    while result.next():
                        output.append(dict(zip(result.fields, result.get_row_data())))
                    return tuple(output)
                fields = "date,open,high,low,close,volume"
                raw = rows(bs.query_history_k_data_plus(code, fields, start_date=start,
                           end_date=end, frequency="d", adjustflag="3"))
                adjusted = rows(bs.query_history_k_data_plus(code, fields, start_date=start,
                                end_date=end, frequency="d", adjustflag=flag))
                factors = rows(bs.query_adjust_factor(code, start_date="1990-01-01", end_date=end))
                return raw, adjusted, factors
            finally:
                bs.logout()

    def get_adjusted_history(self, request: DataRequest) -> DataEnvelope[list[PriceBar]]:
        if request.capability is not Capability.PRICE_ADJUSTED or request.adjustment is Adjustment.UNADJUSTED:
            raise UnsupportedCapability("specify forward or backward adjustment")
        if request.start_date is None or request.end_date is None:
            raise InvalidData("adjusted history needs start and end dates")
        retrieved = datetime.now(timezone.utc)
        if not request.compatibility_mode and request.as_of < retrieved:
            return DataEnvelope(status=DataStatus.NOT_AVAILABLE_FOR_DATE, provider=self.provider_id,
                                reason="current adjusted series has no archived historical revision")
        code, _, is_index = a_share.normalize_ticker(request.instrument.ticker)
        if is_index:
            raise UnsupportedCapability("stock adjustment is not defined for the index")
        flag = "2" if request.adjustment is Adjustment.FORWARD else "1"
        raw, adjusted, factors = self.fetch_raw_adjusted(code, request.start_date.isoformat(),
                                                         request.end_date.isoformat(), flag)
        raw_by_date = {item["date"]: item for item in raw}
        if {item["date"] for item in adjusted} != set(raw_by_date):
            raise InvalidData("adjusted and raw trading dates differ")
        events = sorted((date.fromisoformat(row["dividOperateDate"]), row) for row in factors
                        if row.get("dividOperateDate"))
        bars = []
        has_missing_volume = False
        for row in adjusted:
            source = raw_by_date[row["date"]]
            day = date.fromisoformat(row["date"])
            prices = {key: Decimal(row[key]) for key in ("open", "high", "low", "close")}
            originals = {key: Decimal(source[key]) for key in ("open", "high", "low", "close")}
            if originals["close"] <= 0:
                raise InvalidData("raw close must be positive")
            # The factor is the effective price multiplier for this bar. Keep
            # the source's event factor separately in qualification evidence.
            factor = prices["close"] / originals["close"]
            preceding = [event for event in events if event[0] <= day]
            source_date, source_row = preceding[-1] if preceding else (None, None)
            source_field = "foreAdjustFactor" if request.adjustment is Adjustment.FORWARD else "backAdjustFactor"
            source_factor = Decimal(source_row[source_field]) if source_row and source_row.get(source_field) else None

            # Handle volume: BaoStock returns empty string "" during suspension days.
            # Empty string is NOT 0; treat as missing (None) with DEGRADED quality.
            raw_vol = source.get("volume")
            if raw_vol == "" or raw_vol is None:
                parsed_volume = None
                has_missing_volume = True
            else:
                try:
                    parsed_volume = Decimal(raw_vol)
                except Exception as exc:
                    raise InvalidData(f"invalid volume in raw source: {exc}") from exc

            bars.append(PriceBar(instrument=request.instrument, trading_date=day,
                                 **prices, volume=parsed_volume,
                                 adjustment=request.adjustment,
                                 **{f"raw_{key}": value for key, value in originals.items()},
                                 adjustment_factor=factor, source_factor=source_factor,
                                 source_factor_date=source_date))
        if not bars:
            return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=self.provider_id)
        # The vendor does not publish revision history for adjusted K-lines.
        # Retrieval is the earliest defensible point-in-time availability.
        retrieved = datetime.now(timezone.utc)
        quality = (
            Quality.DEGRADED
            if (request.adjustment is Adjustment.FORWARD or has_missing_volume)
            else Quality.UNVERIFIED
        )
        envelope = _wrap(bars, self.provider_id, request, retrieved, retrieved, Unit.CNY,
                         quality, _hash_payload({"raw": raw, "adjusted": adjusted, "factors": factors}))
        if has_missing_volume:
            envelope.reason = "volume missing on some suspension bars"
        return envelope

    def get_industry(self, request: DataRequest) -> DataEnvelope[CompanyProfile]:
        if request.capability is not Capability.INDUSTRY:
            raise UnsupportedCapability(request.capability)
        retrieved = datetime.now(timezone.utc)
        if not request.compatibility_mode and request.as_of < retrieved:
            return DataEnvelope(status=DataStatus.NOT_AVAILABLE_FOR_DATE, provider=self.provider_id,
                                reason="current industry classification has no archived historical revision")
        import baostock as bs
        code, _, is_index = a_share.normalize_ticker(request.instrument.ticker)
        if is_index:
            raise UnsupportedCapability("index has no stock industry")
        with a_share._baostock_lock:
            login = bs.login()
            if login.error_code != "0":
                raise ProviderFailure(f"BaoStock login failed: {login.error_code}")
            try:
                response = bs.query_stock_industry(code=code)
                if response.error_code != "0":
                    raise ProviderFailure(f"BaoStock industry failed: {response.error_code}")
                rows = []
                while response.next():
                    rows.append(dict(zip(response.fields, response.get_row_data())))
            finally:
                bs.logout()
        if not rows or not rows[0].get("industry"):
            return DataEnvelope(status=DataStatus.MISSING, provider=self.provider_id)
        row = rows[0]
        retrieved = datetime.now(timezone.utc)
        return _wrap(CompanyProfile(instrument=request.instrument,
                     name=row.get("code_name") or request.instrument.ticker,
                     industry=row["industry"]), self.provider_id, request,
                     retrieved, retrieved, Unit.NONE, Quality.UNVERIFIED, _hash_payload(row))

    def get_dividends(self, request: DataRequest) -> DataEnvelope[list[DividendEvent]]:
        if request.capability is not Capability.DIVIDEND:
            raise UnsupportedCapability(request.capability)
        if request.start_date is None or request.end_date is None:
            raise InvalidData("dividend history needs start and end dates")
        if not request.compatibility_mode and request.as_of < datetime.now(timezone.utc):
            return DataEnvelope(status=DataStatus.NOT_AVAILABLE_FOR_DATE, provider=self.provider_id,
                                reason="historical final-dividend revisions require a prior snapshot")
        import baostock as bs
        code, _, is_index = a_share.normalize_ticker(request.instrument.ticker)
        if is_index:
            raise UnsupportedCapability("index has no dividend events")
        start = request.start_date
        end = request.end_date
        with a_share._baostock_lock:
            login = bs.login()
            if login.error_code != "0":
                raise ProviderFailure(f"BaoStock login failed: {login.error_code}")
            try:
                rows = []
                for year in range(start.year, end.year + 1):
                    response = bs.query_dividend_data(code, year=year, yearType="operate")
                    if response.error_code != "0":
                        raise ProviderFailure(f"BaoStock dividend failed: {response.error_code}")
                    while response.next():
                        rows.append(dict(zip(response.fields, response.get_row_data())))
            finally:
                bs.logout()
        retrieved = datetime.now(timezone.utc)
        events = []
        for row in rows:
            announced, ex_day = row.get("dividPlanAnnounceDate"), row.get("dividOperateDate")
            if not announced or not ex_day:
                continue
            day = date.fromisoformat(ex_day)
            if not start <= day <= end:
                continue
            # Final payout may differ from the earlier plan. Only expose the
            # final event after its ex-date, conservatively on the next day.
            announced_day = date.fromisoformat(announced)
            available = _published_on(date.fromordinal(max(day, announced_day).toordinal() + 1))
            if available > request.as_of:
                continue
            events.append(DividendEvent(instrument=request.instrument,
                announced_date=announced_day, ex_date=day,
                cash_per_share=Decimal(row.get("dividCashPsBeforeTax") or "0"),
                stock_per_share=Decimal(row.get("dividStocksPs") or "0"),
                provider=self.provider_id, available_at=available,
                retrieved_at=retrieved, quality=Quality.DEGRADED))
        if not events:
            return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=self.provider_id)
        events.sort(key=lambda item: item.ex_date)
        return _wrap(events, self.provider_id, request, retrieved,
                     max(item.available_at for item in events), Unit.CNY, Quality.DEGRADED,
                     _hash_payload(rows))

    def get_valuation_history(self, request: DataRequest) -> DataEnvelope[list[ValuationSnapshot]]:
        if request.capability not in (Capability.VALUATION_HISTORY, Capability.PE, Capability.PB, Capability.PS):
            raise UnsupportedCapability(request.capability)
        rows = self._rows(request)
        retrieved = datetime.now(timezone.utc)
        snapshots = []
        for row in rows:
            day = date.fromisoformat(row["date"])
            values = {key: a_share._number(row.get(raw)) for key, raw in
                      (("pe", "peTTM"), ("pb", "pbMRQ"), ("ps", "psTTM"))}
            close = a_share._number(row.get("close"))
            snapshots.append(ValuationSnapshot(
                instrument=request.instrument, observed_date=day,
                **{key: Decimal(str(value)) if value is not None else None for key, value in values.items()},
                close=Decimal(str(close)) if close is not None else None,
                provider=self.provider_id, available_at=_published_on(day), retrieved_at=retrieved,
                quality=Quality.VALIDATED))
        if not snapshots:
            return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=self.provider_id)
        return _wrap(snapshots, self.provider_id, request, retrieved,
                     _published_on(snapshots[-1].observed_date), Unit.MULTIPLE, Quality.VALIDATED)

    def get_company_profile(self, request: DataRequest) -> DataEnvelope[CompanyProfile]:
        if request.capability is not Capability.INSTRUMENT_METADATA:
            raise UnsupportedCapability(request.capability)
        import baostock as bs

        code, _, is_index = a_share.normalize_ticker(request.instrument.ticker)
        if is_index:
            return DataEnvelope(status=DataStatus.MISSING, provider=self.provider_id, reason="index has no company profile")
        with a_share._baostock_lock:
            try:
                login = bs.login()
                if login.error_code != "0":
                    raise ProviderFailure(f"BaoStock login failed: {login.error_code}")
                try:
                    response = bs.query_stock_basic(code=code)
                    if response.error_code != "0":
                        raise ProviderFailure(f"BaoStock stock basic failed: {response.error_code}")
                    if not response.next():
                        return DataEnvelope(status=DataStatus.MISSING, provider=self.provider_id)
                    row = dict(zip(response.fields, response.get_row_data()))
                finally:
                    bs.logout()
            except ProviderFailure:
                raise
            except Exception as exc:
                raise classify_provider_error(exc) from exc
        name = str(row.get("code_name") or "").strip()
        if not name:
            return DataEnvelope(status=DataStatus.MISSING, provider=self.provider_id)
        retrieved = datetime.now(timezone.utc)
        profile = CompanyProfile(instrument=request.instrument, name=name)
        return _wrap(profile, self.provider_id, request, retrieved, retrieved,
                     raw_hash=_hash_payload(row))


class AKShareSinaProvider:
    provider_id = "akshare_sina"
    capabilities = frozenset({Capability.INCOME_STATEMENT, Capability.BALANCE_SHEET,
                              Capability.CASH_FLOW_STATEMENT})
    markets = frozenset({Market.CN_SH, Market.CN_SZ})
    access_tier = AccessTier.FREE

    def supports(self, request: DataRequest) -> bool:
        return request.instrument.market in self.markets and request.capability in self.capabilities

    @staticmethod
    def fetch_raw_statements(sina_code: str) -> dict[str, pd.DataFrame]:
        import akshare as ak

        frames = {}
        for statement in ("资产负债表", "利润表", "现金流量表"):
            a_share._logger.debug("AKShare Sina statement: %s %s", sina_code, statement)
            frame = ak.stock_financial_report_sina(stock=sina_code, symbol=statement)
            if frame is None or frame.empty:
                raise ProviderFailure(f"AKShare/Sina returned no {statement} for {sina_code}")
            frames[statement] = frame.copy()
        return frames

    def get_financial_statements(self, request: DataRequest) -> DataEnvelope[list[FinancialStatement]]:
        if not self.supports(request):
            raise UnsupportedCapability(request.capability)
        _, sina_code, index = a_share.normalize_ticker(request.instrument.ticker)
        if index:
            raise UnsupportedCapability("index has no company statements")
        try:
            frames = a_share._statements(sina_code)
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise classify_provider_error(exc) from exc
        names = {
            "利润表": StatementType.INCOME,
            "资产负债表": StatementType.BALANCE_SHEET,
            "现金流量表": StatementType.CASH_FLOW,
        }
        wanted = {Capability.INCOME_STATEMENT: "利润表",
                  Capability.BALANCE_SHEET: "资产负债表",
                  Capability.CASH_FLOW_STATEMENT: "现金流量表"}[request.capability]
        frame = frames.get(wanted)
        if frame is None or not {"报告日", "公告日期"}.issubset(frame.columns):
            raise SchemaChanged(f"{wanted}: report or announcement date missing")
        end = request.end_date or request.as_of.astimezone(SHANGHAI).date()
        visible = a_share._visible(frame, end.isoformat())
        statements = []
        for report_date, row in visible.items():
            announced = date.fromisoformat(a_share._as_date(row["公告日期"]))
            available = _published_on(announced)
            if available > request.as_of:
                continue
            fields = []
            for canonical, (statement, aliases) in a_share._aliases.items():
                if statement == wanted:
                    value = a_share._field({wanted: {report_date: row}}, report_date, canonical)
                    fields.append(FinancialField(name=canonical,
                                                 value=Decimal(str(value)) if value is not None else None,
                                                 unit=Unit.CNY if canonical != "earnings_per_share" else Unit.NONE))
            statements.append(FinancialStatement(
                instrument=request.instrument, statement_type=names[wanted],
                period_end=date.fromisoformat(report_date),
                period="annual" if report_date.endswith("12-31") else
                       ("snapshot" if wanted == "资产负债表" else "reported_ytd"),
                fields=tuple(fields), available_at=available))
        if not statements:
            future = any(a_share._as_date(v) and a_share._as_date(v) > end.isoformat()
                         for v in frame["公告日期"])
            return DataEnvelope(status=DataStatus.NOT_PUBLISHED if future else DataStatus.EMPTY_SUCCESS,
                                provider=self.provider_id)
        statements.sort(key=lambda item: item.period_end)
        retrieved = datetime.now(timezone.utc)
        return _wrap(statements, self.provider_id, request, retrieved,
                     max(item.available_at for item in statements), Unit.CNY, Quality.VALIDATED)


class AKShareEastMoneyProvider:
    provider_id = "akshare_eastmoney"
    capabilities = frozenset({Capability.SHARE_CAPITAL, Capability.NEWS})
    markets = frozenset({Market.CN_SH, Market.CN_SZ})
    access_tier = AccessTier.FREE

    def supports(self, request: DataRequest) -> bool:
        return request.instrument.market in self.markets and request.capability in self.capabilities

    @staticmethod
    def fetch_raw_share_history(sina_code: str) -> tuple[tuple[str, float], ...]:
        import akshare as ak

        symbol = f"{sina_code[-6:]}.{sina_code[:2].upper()}"
        a_share._logger.debug("AKShare dated share history: %s", symbol)
        frame = ak.stock_zh_a_gbjg_em(symbol=symbol)
        if frame is None or frame.empty or not {"变更日期", "总股本"}.issubset(frame.columns):
            return ()
        points = []
        for _, row in frame.iterrows():
            changed = a_share._as_date(row.get("变更日期"))
            shares = a_share._number(row.get("总股本"))
            if changed and shares is not None and shares > 0:
                points.append((changed, shares))
        return tuple(sorted(points))

    def get_share_capital(self, request: DataRequest) -> DataEnvelope[list[ShareCapitalEvent]]:
        if request.capability is not Capability.SHARE_CAPITAL or not self.supports(request):
            raise UnsupportedCapability(request.capability)
        _, sina_code, index = a_share.normalize_ticker(request.instrument.ticker)
        if index:
            raise UnsupportedCapability("index has no share capital")
        try:
            history = a_share._share_history(sina_code)
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise classify_provider_error(exc) from exc
        retrieved = datetime.now(timezone.utc)
        events = []
        for changed, shares in history:
            day = date.fromisoformat(changed)
            # The feed has no announcement timestamp. Strict historical reads
            # may only use a saved snapshot fetched by that as_of date.
            available = _published_on(day) if request.compatibility_mode else retrieved
            if day <= (request.end_date or request.as_of.date()):
                events.append(ShareCapitalEvent(
                    instrument=request.instrument, effective_date=day,
                    total_shares=Decimal(str(shares)), provider=self.provider_id,
                    available_at=available, retrieved_at=retrieved, quality=Quality.DEGRADED))
        if not events:
            return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=self.provider_id)
        return _wrap(events, self.provider_id, request, retrieved,
                     max(item.available_at for item in events), Unit.SHARES, Quality.DEGRADED,
                     _hash_payload(history))

    def get_news(self, request: DataRequest) -> DataEnvelope[list[NewsItem]]:
        if request.capability is not Capability.NEWS or not self.supports(request):
            raise UnsupportedCapability(request.capability)
        _, sina_code, index = a_share.normalize_ticker(request.instrument.ticker)
        if index:
            raise UnsupportedCapability("index has no company news")
        retrieved = datetime.now(timezone.utc)
        if (not request.compatibility_mode and
                request.as_of.astimezone(SHANGHAI).date() < retrieved.astimezone(SHANGHAI).date()):
            return DataEnvelope(status=DataStatus.NOT_AVAILABLE_FOR_DATE, provider=self.provider_id,
                                reason="recent feed has no historical snapshot for this as_of")
        import akshare as ak
        try:
            frame = ak.stock_news_em(symbol=sina_code[-6:])
        except Exception as exc:
            raise classify_provider_error(exc) from exc
        if frame is None or frame.empty:
            return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=self.provider_id)
        if not {"发布时间", "新闻标题"}.issubset(frame.columns):
            raise SchemaChanged("news publication or title column missing")
        end = request.end_date or request.as_of.astimezone(SHANGHAI).date()
        output = []
        for _, row in frame.iterrows():
            published = a_share._as_date(row.get("发布时间"))
            if not published or published > end.isoformat() or (request.start_date and published < request.start_date.isoformat()):
                continue
            raw_time = str(row.get("发布时间") or "")
            parsed = pd.to_datetime(raw_time, errors="coerce")
            if pd.isna(parsed):
                continue
            published_at = parsed.to_pydatetime()
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=SHANGHAI)
            else:
                published_at = published_at.astimezone(SHANGHAI)
            if not request.compatibility_mode and published_at > request.as_of:
                continue
            output.append(NewsItem(
                instrument=request.instrument, title=str(row.get("新闻标题") or ""),
                published_at=published_at,
                source=str(row.get("文章来源") or ""), url=str(row.get("新闻链接") or "")))
        if not output:
            return DataEnvelope(status=DataStatus.EMPTY_SUCCESS, provider=self.provider_id)
        output.sort(key=lambda item: item.published_at.date(), reverse=True)
        return _wrap(output, self.provider_id, request, retrieved,
                     max(item.published_at for item in output), Unit.NONE, Quality.UNVERIFIED,
                     _hash_payload(frame.to_json(orient="records", force_ascii=False)))
