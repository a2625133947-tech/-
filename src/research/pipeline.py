"""Discovery -> acquisition -> parsing -> dedup -> bounded synthesis -> verification."""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from .documents import canonical_id, digest, parse_document, same_report
from .grounding import report_summary, synthesize
from .models import Coverage, PARSER_VERSION, PROMPT_VERSION, ResearchReportMetadata, ReportSummary

logger = logging.getLogger(__name__)


class ResearchPipeline:
    def __init__(self, store, providers, workers=4):
        self.store = store
        self.providers = {p.name: p for p in providers}
        self.workers = min(max(workers, 1), 4)

    def run(self, security, period, *, limit=100, refresh=False, regenerate=False, llm_state=None, progress=None):
        started = time.monotonic()
        progress = progress or (lambda *args: None)
        errors, discovered = [], []
        coverage = Coverage()
        metrics = {"llm_calls": 0, "input_characters": 0, "max_prompt_chars": 0, "document_cache_hits": 0, "summary_cache_hits": 0, "discovery_cache_hits": 0, "period_cache_hit": False, "download_workers": self.workers, "parsed_characters": 0, "chunk_count": 0}
        progress("DISCOVERING", 0, len(self.providers))
        for index, provider in enumerate(self.providers.values()):
            key = "discovery:" + digest(f"{provider.name}|{security.market}|{security.canonical_symbol}|{period.model_dump_json()}|{limit}")
            try:
                cached = None if refresh else self.store.cache_get(key)
                if cached:
                    items = [ResearchReportMetadata.model_validate(item) for item in cached["reports"]]
                    complete, warnings = cached["complete"], cached["warnings"]
                    metrics["discovery_cache_hits"] += 1
                else:
                    result = provider.discover(security, period, limit)
                    items, complete, warnings = result.reports, result.complete, result.warnings
                    self.store.cache_put(key, security.canonical_symbol, "discovery", {"reports": [m.model_dump(mode="json") for m in items], "complete": complete, "warnings": warnings}, ttl=21600)
                coverage.discovery_complete &= complete
                errors.extend({"provider": provider.name, "stage": "discovery", "error": w} for w in warnings)
                for meta in items:
                    coverage.discovered += 1
                    if meta.ticker != security.canonical_symbol or meta.market != security.market:
                        errors.append({"provider": provider.name, "stage": "metadata", "error": "wrong target security"})
                        continue
                    if not period.start <= meta.published_at <= period.end:
                        coverage.out_of_period += 1
                        continue
                    meta.canonical_report_id = canonical_id(meta)
                    meta.source_urls = sorted({*meta.source_urls, meta.source_url, *([meta.pdf_url] if meta.pdf_url else [])})
                    discovered.append(meta)
            except Exception as exc:
                logger.warning("research discovery provider=%s error_type=%s", provider.name, type(exc).__name__)
                coverage.discovery_complete = False
                errors.append({"provider": provider.name, "stage": "discovery", "error": type(exc).__name__})
            progress("DISCOVERING", index + 1, len(self.providers))

        groups = []
        for meta in discovered:
            group = next((g for g in groups if same_report(g[0], meta)), None)
            if group is not None:
                group.append(meta)
                coverage.duplicates += 1
            else:
                groups.append([meta])
        coverage.unique_reports = len(groups)

        def acquire_group(group):
            # Cached parsed documents include immutable raw bytes; repeat clicks do not download.
            for meta in group:
                cached = self.store.get_document(meta.canonical_report_id)
                if cached and cached.parser_version == PARSER_VERSION:
                    return cached, None, None, True, []
            failures = []
            for meta in group:
                discovery_id = meta.canonical_report_id
                raw, content_type = None, None
                try:
                    old = self.store.raw_source(discovery_id)
                    cached_document = self.store.get_document(discovery_id)
                    if old and cached_document:
                        raw, content_type = old
                        doc = parse_document(meta, raw, content_type, abstract=cached_document.content_kind == "abstract")
                    else:
                        acquired = self.providers[meta.source_provider].acquire(meta)
                        raw, content_type = acquired.raw, acquired.content_type
                        doc = parse_document(meta, raw, content_type, abstract=acquired.abstract)
                    if discovery_id != doc.metadata.canonical_report_id:
                        self.store.cache_put("alias:" + discovery_id, meta.ticker, "report_alias", {"canonical_report_id": doc.metadata.canonical_report_id})
                    return doc, raw, content_type, False, failures
                except Exception as exc:
                    failures.append({"provider": meta.source_provider, "report_id": meta.canonical_report_id, "stage": "acquisition_or_parse", "error": type(exc).__name__})
                    # Never save network exception URLs/queries that may carry provider credentials.
                    self.store.save_document(meta, raw, content_type, error=type(exc).__name__)
            return None, None, None, False, failures

        documents = []
        progress("DOWNLOADING", 0, len(groups))
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(acquire_group, group): group for group in groups}
            # Stable source order makes canonical selection independent of download timing.
            for index, future in enumerate(futures):
                doc, raw, content_type, cached, failures = future.result()
                errors.extend(failures)
                if doc is None:
                    coverage.failed += 1
                else:
                    metrics["document_cache_hits"] += cached
                    if not period.start <= doc.metadata.published_at <= period.end:
                        coverage.out_of_period += 1
                        coverage.unique_reports -= 1
                        self.store.save_document(doc.metadata, raw, content_type, doc)
                        progress("PARSING", index + 1, len(groups))
                        continue
                    aliases = {u for m in futures[future] for u in m.source_urls}
                    doc.metadata.source_urls = sorted(set(doc.metadata.source_urls) | aliases)
                    duplicate = next((d for d in documents if same_report(d.metadata, doc.metadata)), None)
                    if duplicate:
                        coverage.duplicates += 1
                        coverage.unique_reports -= 1
                        duplicate.metadata.source_urls = sorted(set(duplicate.metadata.source_urls) | aliases)
                        self.store.save_document(duplicate.metadata, None, None, duplicate)
                        # Alias record still caches this original byte sequence for future discovery.
                        self.store.save_document(doc.metadata, raw, content_type, doc)
                    else:
                        documents.append(doc)
                        self.store.save_document(doc.metadata, raw, content_type, doc)
                progress("PARSING", index + 1, len(groups))
        documents.sort(key=lambda d: (d.metadata.published_at, d.metadata.canonical_report_id))
        model = "extractive"
        if llm_state is not None:
            model = str(llm_state["metadata"].get("model_provider")) + ":" + str(llm_state["metadata"].get("model_name"))
        evidence_signature = sorted((d.metadata.canonical_report_id, d.metadata.content_hash, d.content_kind, d.metadata.source_urls) for d in documents)
        pkey = "period:" + digest(json.dumps([security.canonical_symbol, period.model_dump(mode="json"), evidence_signature, model, PROMPT_VERSION, PARSER_VERSION, coverage.model_dump(), errors], ensure_ascii=False, sort_keys=True))
        if not regenerate:
            from .models import ResearchContext

            cached = self.store.cache_get(pkey)
            if cached:
                ctx = ResearchContext.model_validate(cached)
                ctx.metrics = {**metrics, "period_cache_hit": True, "elapsed_seconds": round(time.monotonic() - started, 3)}
                return ctx
        summaries = []
        progress("SUMMARIZING", 0, len(documents))
        for index, document in enumerate(documents):
            metadata = document.metadata
            key = "summary:" + digest(f"{metadata.canonical_report_id}|{metadata.content_hash}|{model}|{PROMPT_VERSION}|{PARSER_VERSION}")
            cached = None if regenerate else self.store.cache_get(key)
            if cached:
                summary = ReportSummary.model_validate(cached)
                metrics["summary_cache_hits"] += 1
            else:
                summary = report_summary(document, llm_state, metrics)
                self.store.cache_put(key, security.canonical_symbol, "report_summary", summary.model_dump(mode="json"))
            summaries.append(summary)
            metrics["parsed_characters"] += len(document.text)
            metrics["chunk_count"] += len(document.chunks)
            progress("SUMMARIZING", index + 1, len(documents))
        progress("VERIFYING", 0, len(summaries))
        if metrics.get("llm_failed_batches"):
            errors.append({"stage": "llm", "error": "model extraction unavailable in some batches; verified literal extracts retained"})
        metrics["elapsed_seconds"] = round(time.monotonic() - started, 3)
        metrics["token_usage"] = None
        metrics["token_usage_note"] = "provider token usage unavailable through existing model abstraction; input characters measured exactly"
        context = synthesize(security, period, documents, summaries, coverage, errors, metrics)
        context.reports = [{**d.metadata.model_dump(mode="json"), "content_kind": d.content_kind, "status": s.status} for d, s in zip(documents, summaries)]
        # Failed unique reports remain visible, but never count as analyzed documents.
        analyzed = {d.metadata.canonical_report_id for d in documents}
        for group in groups:
            if not any(m.canonical_report_id in analyzed for m in group) and any(e.get("report_id") == group[0].canonical_report_id for e in errors):
                context.reports.append({**group[0].model_dump(mode="json"), "content_kind": "unavailable", "status": "FAILED"})
        self.store.cache_put(pkey, security.canonical_symbol, "period_summary", context.model_dump(mode="json"), ttl=21600)
        progress("VERIFYING", len(summaries), len(summaries))
        return context
