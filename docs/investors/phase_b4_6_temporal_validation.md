# Phase B4.6: Temporal / Point-in-Time Shadow Validation

## 1. Scope, Purpose & Safety Boundary

Phase B4.6 evaluates the **strategy semantic stability** of the three pilot investor profiles (张坤 v2, 冯柳 v1, 傅鹏博 v1) across different historical `as_of` dates, earnings announcement cycles, and market phases.

**Critical Non-Goals & Boundaries**:
- This phase does **not** evaluate trading alpha, backtest returns, Sharpe ratio, or market prediction accuracy.
- Production default remains strictly `LEGACY`.
- The remaining nine investors are **not** migrated; they remain in Legacy with only read-only design reviews conducted.
- The temporal runner does not enter the investment graph, Risk Manager, or Portfolio Manager.

---

## 2. Point-in-Time Principles & Temporal Capability Policy

Free A-share providers (BaoStock, AKShare/Sina, AKShare/EastMoney) have structural data limitations. Today's live downloads of backward-adjusted prices, CSRC industry classifications, or share-capital records do not maintain point-in-time revision archives. Therefore, current data must never be backfilled into arbitrary past `as_of` dates.

All capabilities are classified under `TemporalCapabilityPolicy` (`src/data/temporal.py`):

| Classification | Capabilities | PIT Safety Level | Retrospective Handling | Prospective Handling |
|---|---|---|---|---|
| **HISTORICALLY_RECONSTRUCTIBLE** | `INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW_STATEMENT`, `REVENUE`, `NET_INCOME`, `CAPEX`, `FREE_CASH_FLOW`, `ROE`, `GROSS_MARGIN`, `OPERATING_MARGIN`, `NET_MARGIN`, `PRICE_DAILY`, `VOLUME` | `PIT_SAFE` | Fully eligible: filtered strictly by `available_at <= as_of` and `period_end <= as_of.date()` | Full fidelity |
| **ARCHIVED_ONLY** | `PRICE_ADJUSTED`, `VALUATION_HISTORY`, `PE`, `PB`, `PS`, `DIVIDEND`, `SHARE_CAPITAL`, `SHARE_CAPITAL_EVENTS`, `MARKET_CAP`, `EV_EBITDA`, `FCF_YIELD`, `NEWS` | `PIT_PARTIAL` | **Ineligible** for retrospective backfill without an archived snapshot; marked `NOT_AVAILABLE_FOR_DATE` / `NOT_AVAILABLE_AS_OF` | Full fidelity when replaying archived prospective snapshot |
| **CURRENT_ONLY** | `INDUSTRY`, `SECTOR`, `INSTRUMENT_METADATA`, `COMPANY_PROFILE` | `CURRENT_ONLY` | **Strictly prohibited** from backfilling historical dates | Retained at snapshot capture time |
| **UNAVAILABLE** | `PRICE_INTRADAY`, `ROIC`, `ANNOUNCEMENTS`, `ANALYST_ESTIMATES`, `EARNINGS_REVISIONS`, `CONSENSUS_FORECAST`, `MANAGEMENT`, `OWNERSHIP`, `MAJOR_SHAREHOLDERS`, etc. | `PIT_PARTIAL` | `UNSUPPORTED` / `UNAVAILABLE` | `UNSUPPORTED` |

---

## 3. Two Validation Tracks

### Track A: Retrospective PIT-Safe Validation
- Operates on financial statements with authentic announcement dates (`available_at`).
- Non-PIT-safe capabilities (e.g. backward-adjusted prices, valuation multiples) are marked `NOT_AVAILABLE_FOR_DATE`.
- Factors depending on missing capabilities yield `NOT_AVAILABLE_AS_OF` or `UNAVAILABLE`.
- Profile missing-data policies handle missing inputs deterministically without look-ahead bias.

### Track B: Prospective Snapshot Accumulation
- From the current date forward, complete `FrozenDataSnapshot` instances are captured and archived.
- Future cross-time price behavior (momentum, drawdown, volatility) is evaluated using genuine archived snapshots.

---

## 4. Snapshot Collector, Deduplication & Retention

`src/investors/collector.py` provides standalone collection and catalog management (`collect-shadow-snapshots` CLI):
- **Content Hash Deduplication**: `compute_content_hash()` generates a SHA256 digest over normalized financial statements, prices, valuations, shares, dividends, and industry payload (independent of execution timestamps). Identical observations are recognized as duplicates and not saved as redundant files, while recording a `CaptureEvent`.
- **Milestone Retention Policy**: `SnapshotRetentionPolicy` protects milestone events from being pruned:
  - `EARNINGS_RELEASE`: new financial statement period published.
  - `CORPORATE_ACTION_SHARE_CHANGE` / `CORPORATE_ACTION_DIVIDEND`: capital or payout events.
  - `SIGNIFICANT_PRICE_MOVE`: single-day close move $\ge 5\%$.
  - `CAPABILITY_STATUS_CHANGE`: provider availability or schema change.
- **Prospective Catalog**: `docs/baselines/shadow/live/temporal_catalog.json` indexes snapshots, content hashes, capability coverage, quality statuses, and retention tags.

---

## 5. BaoStock Adjusted Volume Empty String Resolution

- **Diagnosis**: For tickers such as `600438` and `688347`, BaoStock returns `""` (empty string) for volume on trading suspension dates. Attempting `Decimal("")` caused an `InvalidOperation` exception, aborting snapshot capture.
- **Root Cause & Semantics**: BaoStock uses `""` to denote suspension/unreported volume, not a traded volume of zero.
- **Correction**:
  - Empty string is **never** coerced to `0`. It is parsed as `None` (missing volume).
  - `PriceBar.volume` domain model updated to `Decimal | None = Field(default=None, ge=0)`.
  - When volume is missing but OHLC is valid, the price envelope quality is set to `Quality.DEGRADED` and reason records `"volume missing on some suspension bars"`.
  - Corrupted, non-empty text strings continue to raise `InvalidData`.
  - Regression tests in `tests/test_stage8_data.py` verify that `600438` and `688347` parse successfully with `volume is None` and `Quality.DEGRADED`.

---

## 6. Retrospective Temporal Runner & Strategy Trace

`TemporalShadowRunner` (`src/investors/temporal.py`):
1. Takes `(ticker, profile, as_of, source_data, policy)`.
2. Filters source data via `build_pit_constrained_snapshot()`.
3. Runs New Factor Engine $\to$ New Strategy Evaluator $\to$ Legacy evaluation $\to$ DifferenceReport.
4. Produces `StrategyTrace` containing sequential evaluations across reporting periods.

### Announcement Timeline Verification (e.g. 600519)
- Before 2025 Annual announcement (`2026-04-15`): latest visible statement is `2025-09-30` (Q3).
- After 2025 Annual announcement (`2026-04-20`): latest visible statement moves to `2025-12-31`.
- After 2026 Q1 announcement (`2026-05-01`): latest visible statement moves to `2026-03-31`.
- After 2026 Q2 announcement (`2026-08-20`): latest visible statement moves to `2026-06-30`.
- Look-ahead bias is strictly zero.

---

## 7. Metamorphic Testing & Transition Audits

- **Monotonicity (Metamorphic Tests)**:
  - 张坤: Keeping other factors constant, improving `cash_conversion` score monotonically increases or maintains `strategy_score`.
  - 冯柳: With proxy established ($>0$), improving operating turnaround metrics (`growth_acceleration`, `margin_trend`) monotonically increases or maintains `strategy_score`.
  - 傅鹏博: Improving `growth_acceleration` monotonically increases or maintains `strategy_score`.
- **Determinism**: Same snapshot + profile version + factor version guarantees 100% byte-for-byte identical output.
- **Confidence Monotonicity**: Adding missing core factors increases confidence; missing core factors trigger profile missing-data caps (`core_missing_cap`, `critical_evidence_absent <= 35`).

---

## 8. Confidence Distribution Audit

Audit of 54 matched comparisons across 18 live snapshots:
- **Legacy Confidence**: Mean 36.9–42.4%, with high volatility (stdev 14.4–22.5%, min 0.0%, max 76.9%).
  - *Structural Defect in Legacy*: Legacy formula `min(85, abs(weighted) * 65 + 20) * coverage` coupled confidence directly to score magnitude. A near-neutral score produced low confidence even with 100% complete data.
- **New Confidence**: Mean 46.9–55.3%, tighter standard deviation (6.0–9.7%, min 29.6%, max 60.0%).
  - *Semantic Soundness*: New confidence measures evidence credibility. It applies explicit caps:
    - `core_missing_cap` (50–55%)
    - `proxy_cap` (60% for Feng Liu)
    - `critical_evidence_absent` (capped at 35%)
    - `degraded` penalty ($\times 0.85$).
  - High confidence is never awarded without complete, high-quality core evidence.

---

## 9. Remaining Nine Investor Design Review

| Investor | Core Factors Proposed | Supporting Factors | Optional Factors | Current Engine Coverage | Key Missing Capabilities | Proxy Requirements | Design Readiness |
|---|---|---|---|---|---|---|---|
| **段永平** | `profitability_quality`, `cash_conversion`, `balance_sheet_safety`, `margin_trend` | `valuation_level`, `valuation_percentile` | `revenue_cagr_3y` | 100% | Franchise moat, long-term ROIC | None | `DESIGN_READY` |
| **邓晓峰** | `valuation_level`, `valuation_percentile`, `earnings_growth_yoy`, `margin_trend` | `profitability_quality`, `balance_sheet_safety` | `momentum_6m`, `drawdown_6m` | 85% | Industry cycle position, commodity sensitivity | Cycle turnaround proxy | `DESIGN_READY` |
| **朱少醒** | `profitability_quality`, `revenue_growth_yoy`, `cash_conversion` | `valuation_level`, `balance_sheet_safety`, `margin_trend`, `growth_acceleration` | `momentum_6m`, `drawdown_6m` | 90% | Long-term capital allocation efficiency | None | `DESIGN_READY` |
| **刘彦春** | `profitability_quality`, `revenue_growth_yoy`, `earnings_growth_yoy`, `cash_conversion` | `margin_trend`, `revenue_cagr_3y`, `valuation_level` | `balance_sheet_safety`, `momentum_6m` | 95% | Consumer brand pricing power, channel inventory | None | `DESIGN_READY` |
| **谢治宇** | `growth_acceleration`, `revenue_growth_yoy`, `earnings_growth_yoy`, `valuation_level` | `profitability_quality`, `valuation_percentile`, `balance_sheet_safety` | `momentum_6m` | 85% | PEG factor, industry relative valuation | Growth-valuation match proxy | `DESIGN_READY` |
| **董承非** | `balance_sheet_safety`, `valuation_level`, `valuation_percentile`, `cash_conversion` | `profitability_quality`, `drawdown_6m` | `volatility_6m`, `momentum_6m` | 85% | P/CF ratio, dividend consistency | Downside safety proxy | `DESIGN_READY` |
| **王亚伟** | `earnings_growth_yoy`, `growth_acceleration`, `momentum_6m`, `momentum_3m` | `valuation_level`, `drawdown_6m`, `balance_sheet_safety` | `volatility_6m` | 65% | Corporate restructuring, major shareholder changes, capital flow | Restructuring catalyst proxy | `NOT_READY` |
| **陈光明** | `profitability_quality`, `cash_conversion`, `balance_sheet_safety`, `valuation_level` | `valuation_percentile`, `margin_trend`, `revenue_cagr_3y` | `drawdown_6m` | 90% | Owner earnings, governance metrics | None | `DESIGN_READY` |
| **林园** | `profitability_quality`, `cash_conversion`, `revenue_cagr_3y`, `margin_trend` | `earnings_growth_yoy`, `revenue_growth_yoy`, `valuation_level` | `balance_sheet_safety` | 80% | Monopoly/license barriers, pricing power index | Rigid demand monopoly proxy | `NOT_READY` |

---

## 10. Migration Readiness Matrix

| Investor | Factor Coverage | Temporal Evidence | Missing Critical Factors | Proxy Dependence | Profile Design Reviewed | Migration Readiness |
|---|---|---|---|---|---|---|
| **张坤** (Pilot) | 95% | 18 live snapshots + 12 synthetic cases + multi-period traces | None | Low | Yes (v2 validated) | **SHADOW_READY** |
| **冯柳** (Pilot) | 75% | 18 live snapshots + 12 synthetic cases + multi-period traces | Market consensus, revision history | High (`low_expectation_proxy`) | Yes (v1 validated) | **SHADOW_READY** |
| **傅鹏博** (Pilot) | 90% | 18 live snapshots + 12 synthetic cases + multi-period traces | Analyst forward projections | Low (Growth gate enforced) | Yes (v1 validated) | **SHADOW_READY** |
| **段永平** | 100% | None (design only) | None | Low | Yes | `DESIGN_READY` |
| **邓晓峰** | 85% | None (design only) | Cycle position | Medium | Yes | `DESIGN_READY` |
| **朱少醒** | 90% | None (design only) | Management quality | Low | Yes | `DESIGN_READY` |
| **刘彦春** | 95% | None (design only) | Pricing power | Low | Yes | `DESIGN_READY` |
| **谢治宇** | 85% | None (design only) | PEG ratio | Medium | Yes | `DESIGN_READY` |
| **董承非** | 85% | None (design only) | P/CF multiple | Low | Yes | `DESIGN_READY` |
| **王亚伟** | 65% | None (design only) | Restructuring, flow data | High | Yes | `NOT_READY` |
| **陈光明** | 90% | None (design only) | Owner earnings | Low | Yes | `DESIGN_READY` |
| **林园** | 80% | None (design only) | Monopoly barrier indicators | High | Yes | `NOT_READY` |

---

## 11. Test Results Summary

- Existing baseline tests: **177 passed**
- BaoStock missing volume regression tests: **+2 passed**
- Temporal and point-in-time shadow validation tests: **+22 passed**
- **Total Test Suite**: **201 passed**, 0 failed, 12 dependency deprecation warnings.
