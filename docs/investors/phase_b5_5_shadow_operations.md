# Phase B5.5: Shadow Operations + Confidence Semantics Audit

## 1. Scope, Operational Directives & Safety Boundaries

Phase B5.5 solidifies shadow research operations and rectifies confidence semantics:
- **No New Investors**: 10 profiles remain in `SHADOW_PROFILES`; 王亚伟 and 林园 remain `NOT_READY`.
- **No Factor/Profile Formula Changes**: Factor formulas, weights, thresholds, and profile gates were **not** modified.
- **Production Isolation**: Production default continues strictly as `LEGACY`. No `NEW` evaluation enters Risk Manager or Portfolio Manager.

---

## 2. Confidence Formula Audit

### Prior Data Flow & Variables
In Phase B4–B5, `StrategyEvaluator.evaluate()` computed confidence as:
$$\text{base\_confidence} = \text{cp.maximum} \times \left(0.65 \times \text{core} + 0.25 \times \text{supporting} + 0.10 \times \text{optional}\right) \times \text{quality}$$
Subject to:
- `core_missing_cap` (e.g. 55 for zhang_kun, 50 for fu_pengbo) if $\text{core} < 1$.
- `history_missing_cap` (e.g. 65 for zhang_kun) if insufficient history.
- `minimum_coverage_cap` ($\le 40$) if $\text{core} < \text{minimum\_coverage}$.
- `critical_capability_cap` ($\le 35$) if critical capability unavailable.
- `proxy_cap` ($\le 60$ for feng_liu).
- `degraded` penalty ($\times 0.85$).

### The Semantic Defect Discovered
`known_missing_dimensions` and `strategy_evidence_coverage` were computed as metadata properties, but **did not actually participate** in bounding confidence. Consequently, for profiles like `xie_zhiyu` or `deng_xiaofeng`, when 100% of declared quantitative factors were present, confidence reached 84%–90%, despite ~35%–40% of the theoretical strategy dimensions (e.g. PEG, cycle position, relative valuation) being completely unobservable.

---

## 3. Relationship: `strategy_evidence_coverage` vs `Confidence`

- **`strategy_evidence_coverage`**: The fraction of theoretical investment philosophy dimensions observable by the model:
  $$\text{strategy\_evidence\_coverage} = \text{implemented\_factor\_coverage} \times \frac{N_{\text{declared}}}{N_{\text{declared}} + N_{\text{missing\_dimensions}}}$$
- **`confidence`**: The credibility and degree of data support for the current quantitative conclusion.
- **Rule**: `confidence` is **not** set equal to `strategy_evidence_coverage`. Instead, unobservable theoretical dimensions establish a **Profile-specific ceiling**:
  $$\text{strategy\_evidence\_cap} = 40.0 + 50.0 \times \frac{N_{\text{declared}}}{N_{\text{total}}}$$
  When $N_{\text{missing}} = 0$, cap is $90.0\%$ (unconstrained). When 4 dimensions are missing ($N_{\text{declared}}/N_{\text{total}} \approx 66.7\%$), cap is $73.3\%$. High confidence ($>80\%$) can never be awarded when substantial qualitative pillars are missing.

---

## 4. Confidence Diagnostic Breakdown (`ConfidenceComponents`)

Every `StrategyEvaluationResult` now includes a `ConfidenceComponents` breakdown:
- `maximum_possible`: 90.0
- `core_coverage`, `supporting_coverage`, `optional_coverage`, `coverage_score`
- `evidence_quality`
- `unconstrained_confidence`
- Available caps: `core_missing_cap`, `history_missing_cap`, `minimum_coverage_cap`, `critical_capability_cap`, `proxy_cap`, `strategy_evidence_cap`
- `active_cap_name` & `active_cap_value`: identifies exactly which constraint bound the calculation
- `degraded_penalty_applied` & `degraded_penalty_multiplier`
- `final_confidence`
- `audit_trail`: step-by-step mathematical reasoning log

---

## 5. Proxy Penalty and Double-Penalty Prevention

For strategies relying on proxy factors (e.g. 冯柳 `low_expectation_proxy`):
- `proxy_cap` (60.0) and `strategy_evidence_cap` (76.4) are evaluated together as candidate ceilings.
- The effective ceiling is $\min(\text{proxy\_cap}, \text{strategy\_evidence\_cap}) = 60.0$.
- Because caps are evaluated with $\min()$ rather than multiplicative compounding, there is **zero double-penalty**.

---

## 6. Collector Run Health Report (`CollectorRunReport`)

`SnapshotCollector.collect_many()` produces a structured execution report:
- `run_id`: deterministic UTC timestamp identifier
- `started_at`, `completed_at`, `duration_seconds`
- `requested_tickers`, `successful`, `failed`
- `snapshot_created`, `snapshot_deduplicated`, `snapshot_degraded`, `snapshot_failed`
- `shadow_evaluations_success`, `shadow_evaluations_failed`
- `provider_failures`, `capability_degradations`, `events`

---

## 7. Corpus Integrity & Resumability

- **Partial-Run Detection**: `TemporalCatalogEntry` tracks `expected_profiles`, `completed_profiles`, `missing_profiles`, and `run_status` (`COMPLETE` vs `PARTIAL_RUN`).
- **Resumable Transaction**: `SnapshotCollector.resume_incomplete_evaluations()` scans the catalog, loads snapshots for any incomplete entry, executes missing profile evaluations, updates results, and marks `evaluation_complete = True`.

---

## 8. Idempotency & Version Coexistence

- **Snapshot Idempotency**: Re-running collection on unchanged data yields identical `content_hash`, triggering deduplication without redundant file creation.
- **Evaluation Idempotency**: Evaluation identity is bound by `(snapshot_id, profile_id, profile_version, factor_versions)`. Repeated evaluations overwrite or reuse deterministic results.
- **Version Coexistence**: Profile `v1` and `v2` evaluations coexist on the same snapshot without mutual overwrites.

---

## 9. Longitudinal Dataset Schema & Outcome Separation

- **`LongitudinalShadowRecord`** (`src/investors/longitudinal.py`): Immutable evaluation record capturing score, signal, confidence components, coverage metrics, contributions, and metadata.
- **`OutcomeRecord`**: Future realizations (e.g. 1M, 3M, 6M returns, benchmark excess returns) are strictly segregated into `OutcomeRecord` linked by `snapshot_id` and `ticker`. Forward returns are **never** written into `StrategyEvaluationResult`.

---

## 10. Operational Monitoring & Drift Detection (`src/investors/monitoring.py`)

- **Data Drift**: `check_data_drift()` detects degradation spikes ($>40\%$) and partial runs.
- **Distribution Shift**: `check_distribution_shift()` detects signal monopolies (100% bullish/bearish) or uncharacteristic confidence shifts ($>85\%$ inflation or $<25\%$ collapse).
- **Corpus Summary Tool**: `shadow-corpus-summary` CLI inspects snapshot counts, ticker coverage, signal and confidence distributions, and drift warnings without calculating returns or Sharpe ratios.

---

## 11. Test Results Summary

Running `poetry run pytest`:
- Existing baseline & Phase B4/B5 tests: **214 passed**
- New Phase B5.5 tests in `tests/test_shadow_operations.py`: **+9 passed**
- **Total Test Suite**: **223 passed**, 0 failed, 12 dependency deprecation warnings.
- `python -m compileall src tests`: **0 errors**.
