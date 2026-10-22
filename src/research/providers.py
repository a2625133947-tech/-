"""Discovery adapters and bounded public-source acquisition."""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx

from .documents import MAX_BYTES
from .models import PeriodRange, ResearchReportMetadata


@dataclass
class DiscoveryResult:
    reports: list[ResearchReportMetadata] = field(default_factory=list)
    complete: bool = True
    warnings: list[str] = field(default_factory=list)


@dataclass
class AcquiredDocument:
    raw: bytes
    content_type: str
    url: str
    abstract: bool = False


class ResearchReportProvider(Protocol):
    name: str

    def discover(self, security, period: PeriodRange, limit: int) -> DiscoveryResult:
        ...

    def acquire(self, metadata: ResearchReportMetadata) -> AcquiredDocument:
        ...


def validate_public_url(url: str, *, official_fake_ip=False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("only public HTTP(S) document URLs are permitted")
    if parsed.port not in (None, 80, 443):
        raise ValueError("nonstandard document port blocked")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))

    def permitted(address):
        ip = ipaddress.ip_address(address)
        # TUN proxies synthesize addresses in the RFC 2544 benchmark block. Only
        # hard-coded adapter-owned official hosts receive this exception.
        fake = official_fake_ip and parsed.hostname in {"pdf.dfcfw.com", "data.eastmoney.com"} and ip.version == 4 and ip in ipaddress.ip_network("198.18.0.0/15")
        return ip.is_global or fake

    if not addresses or any(not permitted(item[4][0]) for item in addresses):
        raise ValueError("private, loopback or reserved document address blocked")


class PublicDocumentClient:
    """Allowed hosts come from adapter configuration, never from report text."""

    def __init__(self, allowed_hosts: set[str], transport=None, *, official_fake_ip=False):
        self.allowed_hosts = allowed_hosts
        self.transport = transport
        self.official_fake_ip = official_fake_ip

    def fetch(self, url: str) -> AcquiredDocument:
        with httpx.Client(timeout=httpx.Timeout(25, connect=10), follow_redirects=False, transport=self.transport, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}) as client:
            for _ in range(4):
                host = urlparse(url).hostname
                if host not in self.allowed_hosts:
                    raise ValueError("document host is not enabled in this provider")
                # DNS validation is tested independently even when injecting a deterministic transport.
                if self.transport is None:
                    validate_public_url(url, official_fake_ip=self.official_fake_ip)
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers.get("location", ""))
                        continue
                    response.raise_for_status()
                    if int(response.headers.get("content-length", "0")) > MAX_BYTES:
                        raise ValueError("document exceeds download limit")
                    body = bytearray()
                    for block in response.iter_bytes():
                        body.extend(block)
                        if len(body) > MAX_BYTES:
                            raise ValueError("document exceeds download limit")
                    return AcquiredDocument(bytes(body), response.headers.get("content-type", ""), url)
        raise ValueError("too many document redirects")


class EastMoneyProvider:
    name = "eastmoney"

    def __init__(self, transport=None):
        self.transport = transport
        self.documents = PublicDocumentClient({"pdf.dfcfw.com", "data.eastmoney.com"}, transport, official_fake_ip=True)

    @staticmethod
    def normalize(row: dict, security) -> ResearchReportMetadata:
        code = str(row.get("stockCode", "")).zfill(6)
        if code != security.canonical_symbol:
            raise ValueError("discovery result belongs to another stock")
        info = str(row.get("infoCode", ""))
        if not re.fullmatch(r"[A-Za-z0-9]+", info):
            raise ValueError("invalid EastMoney document identifier")
        title, institution = str(row.get("title", "")).strip(), str(row.get("orgSName") or row.get("orgName") or "").strip()
        return ResearchReportMetadata(
            report_id=f"eastmoney:{info}",
            ticker=code,
            company_name=security.name,
            market=security.market,
            title=title,
            institution=institution,
            analyst=[a.strip() for a in re.split(r"[,，、;；]", str(row.get("researcher") or "")) if a.strip()],
            published_at=date.fromisoformat(str(row["publishDate"])[:10]),
            rating=str(row.get("sRatingName") or ""),
            source_url=f"https://data.eastmoney.com/report/zw_stock.jshtml?infocode={info}",
            pdf_url=f"https://pdf.dfcfw.com/pdf/H3_{info}_1.pdf",
            source_provider="eastmoney",
        )

    def discover(self, security, period: PeriodRange, limit: int) -> DiscoveryResult:
        if security.market != "CN":
            return DiscoveryResult(complete=False, warnings=["EastMoney company research adapter supports CN equities only"])
        result = DiscoveryResult()
        page = 1
        with httpx.Client(timeout=25, transport=self.transport, headers={"Referer": "https://data.eastmoney.com/", "User-Agent": "Mozilla/5.0"}) as client:
            while len(result.reports) < limit:
                response = client.get("https://reportapi.eastmoney.com/report/list", params={"code": security.canonical_symbol, "industryCode": "*", "pageSize": min(100, limit), "pageNo": page, "beginTime": str(period.start), "endTime": str(period.end), "qType": 0, "orgCode": "", "orgName": "", "reportType": "", "rating": "", "ratingChange": "", "author": "", "fields": "", "sort": "publishDate", "order": "desc"})
                response.raise_for_status()
                payload = response.json()
                if "data" not in payload or not isinstance(payload["data"], list):
                    raise ValueError("EastMoney returned invalid research response")
                rows = payload["data"]
                for row in rows:
                    try:
                        item = self.normalize(row, security)
                        if period.start <= item.published_at <= period.end:
                            result.reports.append(item)
                    except (ValueError, KeyError) as exc:
                        result.warnings.append(f"metadata rejected: {type(exc).__name__}")
                        result.complete = False
                total_pages = int(payload.get("TotalPage") or payload.get("totalPage") or 1)
                if not rows or page >= total_pages:
                    break
                if len(result.reports) >= limit:
                    result.complete = False
                    result.warnings.append("discovery limit reached; additional reports may exist")
                    break
                page += 1
        result.reports = result.reports[:limit]
        return result

    def acquire(self, metadata: ResearchReportMetadata) -> AcquiredDocument:
        errors = []
        for url in (metadata.pdf_url, metadata.source_url):
            if not url:
                continue
            try:
                doc = self.documents.fetch(url)
                if url == metadata.source_url:
                    # EastMoney detail body is a published excerpt, not a complete PDF.
                    doc.abstract = True
                return doc
            except (httpx.HTTPError, ValueError, OSError) as exc:
                errors.append(type(exc).__name__)
        raise ValueError("all report acquisition URLs failed: " + ", ".join(errors))


class BrokerFeedProvider:
    """Optional provider-independent JSON feed, including licensed US research.

    A configured feed returns {reports: [ResearchReportMetadata], complete: bool}.
    It must supply issuer/date/title/security and approved original document URLs.
    Search snippets are deliberately not accepted as report bodies.
    """

    name = "broker_feed"

    def __init__(self, feed_url: str, allowed_hosts: set[str]):
        self.feed_url = feed_url
        self.documents = PublicDocumentClient(allowed_hosts)

    def discover(self, security, period: PeriodRange, limit: int) -> DiscoveryResult:
        validate_public_url(self.feed_url)
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            response = client.get(self.feed_url, params={"ticker": security.canonical_symbol, "market": security.market, "start": str(period.start), "end": str(period.end), "limit": limit})
            response.raise_for_status()
            payload = response.json()
        reports = []
        for row in payload["reports"]:
            metadata = ResearchReportMetadata.model_validate({**row, "source_provider": self.name})
            if metadata.ticker == security.canonical_symbol and metadata.market == security.market:
                reports.append(metadata)
        return DiscoveryResult(reports=reports[:limit], complete=payload.get("complete", False) and len(reports) <= limit, warnings=[] if payload.get("complete") else ["feed does not confirm complete discovery"])

    def acquire(self, metadata: ResearchReportMetadata) -> AcquiredDocument:
        return self.documents.fetch(metadata.pdf_url or metadata.source_url)
