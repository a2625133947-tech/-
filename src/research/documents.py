"""Bounded document parsing and stable canonical identity; never parses search snippets."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from difflib import SequenceMatcher
from io import BytesIO

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .models import Chunk, ParsedDocument, ResearchReportMetadata

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 300
MAX_TEXT = 1_000_000
CHUNK_SIZE = 2400


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def normalized_title(title: str) -> str:
    return re.sub(r"[\W_]+", "", title).casefold()


def canonical_id(metadata: ResearchReportMetadata) -> str:
    return "RR-" + digest(f"{metadata.ticker}|{metadata.institution.strip().casefold()}|{metadata.published_at}|{normalized_title(metadata.title)}")[:24]


def same_report(a: ResearchReportMetadata, b: ResearchReportMetadata) -> bool:
    if a.ticker != b.ticker or a.market != b.market:
        return False
    if (a.content_hash and a.content_hash == b.content_hash) or (a.pdf_hash and a.pdf_hash == b.pdf_hash):
        return True
    return a.institution.strip().casefold() == b.institution.strip().casefold() and a.published_at == b.published_at and SequenceMatcher(None, normalized_title(a.title), normalized_title(b.title)).ratio() >= 0.94


def parse_document(metadata: ResearchReportMetadata, raw: bytes, content_type: str, *, abstract=False) -> ParsedDocument:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("empty or oversized document")
    pages: list[tuple[int | None, str]] = []
    if raw.startswith(b"%PDF") or "application/pdf" in content_type:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted or len(reader.pages) > MAX_PAGES:
            raise ValueError("encrypted or oversized PDF")
        pages = [(i + 1, p.extract_text(extraction_mode="layout") or "" if "/Contents" in p else "") for i, p in enumerate(reader.pages)]
        metadata.pdf_hash = digest(raw)
    elif "html" in content_type:
        soup = BeautifulSoup(raw, "html.parser")
        for node in soup(["script", "style", "nav", "header", "footer", "form", "iframe"]):
            node.decompose()
        # Require an actual report body. Search/results/homepages cannot pass.
        body = soup.select_one(".ctx-content, .report-content, .research-content, article, main")
        if body is None:
            raise ValueError("HTML has no identifiable report body")
        pages = [(None, body.get_text("\n", strip=True))]
    elif content_type.startswith("text/plain"):
        pages = [(None, raw.decode("utf-8-sig", errors="strict"))]
    else:
        raise ValueError("unsupported document content type")
    chunks = []
    parts = []
    offset = 0
    metadata.canonical_report_id = metadata.canonical_report_id or canonical_id(metadata)
    for page, text in pages:
        text = text.replace("\x00", "").strip()
        if not text:
            continue
        parts.append(text)
        for start in range(0, len(text), CHUNK_SIZE):
            piece = text[start : start + CHUNK_SIZE]
            chunks.append(Chunk(chunk_id=f"{metadata.canonical_report_id}-C{len(chunks)+1}", report_id=metadata.canonical_report_id, page=page, start=offset + start, end=offset + start + len(piece), text=piece))
        offset += len(text) + 1
        if offset > MAX_TEXT:
            raise ValueError("parsed text exceeds limit")
    text = "\n".join(parts)
    if len(text) < 80:
        raise ValueError("insufficient readable text; scanned PDF needs OCR")
    # Strong target identity guard after acquisition, not just on search metadata.
    identity = (metadata.ticker, metadata.company_name)
    if not any(value and value.casefold() in text.casefold() for value in identity):
        raise ValueError("document does not identify the target security")
    if metadata.institution.casefold() not in text.casefold():
        raise ValueError("document does not identify the declared institution")
    # Provider upload dates can differ from the date printed on the report.
    printed = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text[:500])
    if printed:
        metadata.provider_published_at = metadata.published_at
        metadata.published_at = date(*map(int, printed.groups()))
    metadata.canonical_report_id = canonical_id(metadata)
    for index, chunk in enumerate(chunks):
        chunk.report_id = metadata.canonical_report_id
        chunk.chunk_id = f"{metadata.canonical_report_id}-C{index+1}"
    metadata.content_hash = digest(text)
    return ParsedDocument(metadata=metadata, text=text, chunks=chunks, content_kind="abstract" if abstract else "full_text")
