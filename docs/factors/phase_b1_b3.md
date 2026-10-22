# Phase B1–B3: Factor Engine (2026-09-27)

Scope: an independent research factor layer. No InvestorProfile, legacy `_factors`, signal, confidence, Risk Manager, Portfolio Manager, CLI or Provider routing was changed. All existing workspace modifications were retained.

## A–C. Architecture, result contract and registry

`DataService → normalized FinancialStatement / ValuationSnapshot / PriceBar → RawMetricLoader → RawMetricSeries → FactorEngine → FactorResult`. The factor definitions never import BaoStock, AKShare, CLI, LLM or Investor names. [`src/factors/contracts.py`](../../src/factors/contracts.py) defines `Factor`, `FactorContext`, `RawMetricPoint`, `RawMetricSeries`, `FactorResult`, category/type/status and deterministic quality aggregation. [`src/factors/loader.py`](../../src/factors/loader.py) is the only boundary that requests DataService capabilities. [`src/factors/definitions.py`](../../src/factors/definitions.py) holds versioned formulas. [`src/factors/engine.py`](../../src/factors/engine.py) registers, filters by category and evaluates by factor ID. The registry rejects duplicate IDs, unknown dependencies and cycles. The current graph is only normalized data → raw metrics → factors; no built-in factor depends on another factor.

`FactorResult` has `factor_id`, `version`, `factor_type`, `raw_value`, `raw_unit`, `normalized_score`, `status`, `quality`, `coverage`, `as_of`, `window`, consumed `inputs`, flattened `provenance`, `reason` and `limitations`. Scores use **[-1, +1]**; raw values keep their own units. An unavailable/invalid/insufficient result has **no score**, rather than a fabricated zero. All first-wave factors are `DIRECT`; a future proxy must explicitly use `FactorType.PROXY` and describe its limitations.

## D. Raw metrics implemented

The loader carries reported `revenue`, `cost_of_revenue`, `net_income`, `operating_income`, `operating_cash_flow`, `capital_expenditure`, balance-sheet fields and daily `PE/PB/PS`. It derives `gross_margin`, `operating_margin`, `net_margin`, `free_cash_flow = OCF − |capex|`, annual `ROE = annual net income / average(current, prior-year equity)`, `debt_to_equity`, `current_ratio` and `cash_ratio`. Derived points retain their component provenance and use the **latest** component `available_at`; the worst input quality propagates. Latest-report ratios and annual growth series are kept distinct. `FCF_YIELD` is deferred because its dated market-cap denominator is only partially reliable; no approximate denominator is inserted.

## E–G. Implemented factors, requirements and versioned formulas

Every formula below is `v1`. `clamp(x)` means `min(1, max(-1, x))`; arithmetic uses fractions internally, so 20% is `0.20`. The initial score centers are explicit modeling parameters, not an empirical calibration or an Investor rule.

| Factor ID / category | Required capability and history | Raw value | Normalized score |
| --- | --- | --- | --- |
| `profitability_quality` / Quality | INCOME_STATEMENT, latest comparable period; ROE from BALANCE_SHEET optional | Mean of present net margin, ROE, operating margin | Mean of `clamp(net_margin/0.25−1)`, optional `clamp(ROE/0.15−1)`, optional `clamp(operating_margin/0.25−1)` |
| `cash_conversion` / Cash flow | INCOME_STATEMENT + CASH_FLOW_STATEMENT, one aligned period, NI > 0; FCF optional | OCF / NI | Mean of `clamp(OCF/NI−1)` and, when present, `clamp(FCF/NI−0.75)` |
| `balance_sheet_safety` / Quality | BALANCE_SHEET, dated D/E; liquidity ratios optional | Debt / equity | Mean of `clamp(1−2×D/E)`, optional `clamp((current_ratio−1.5)/1.5)`, optional `clamp((cash_ratio−0.5)/0.5)` |
| `revenue_growth_yoy` / Growth | INCOME_STATEMENT, two consecutive annual periods | Current / prior − 1, positive non-near-zero base | `clamp(raw/0.20)` |
| `revenue_cagr_3y` / Growth | INCOME_STATEMENT, four consecutive annual periods | `(current/base)^(1/3)−1`, positive base | `clamp(raw/0.20)` |
| `earnings_growth_yoy` / Growth | INCOME_STATEMENT, two consecutive annual periods | Current / prior − 1; prior NI must be positive and non-near-zero | `clamp(raw/0.20)` |
| `growth_acceleration` / Growth | INCOME_STATEMENT, three consecutive annual revenue periods | Latest YoY growth − previous YoY growth | `clamp(raw/0.10)` |
| `margin_trend` / Quality | INCOME_STATEMENT, three consecutive annual net margins | `(latest−first)/2` fraction points per year | `clamp(raw/0.05)` |
| `valuation_level` / Valuation | VALUATION_HISTORY, latest positive PE; PB/PS optional on same day | Latest PE multiple | Mean of `clamp((25−PE)/15)`, optional `clamp((4−PB)/3)`, optional `clamp((7−PS)/5)` |
| `valuation_percentile` / Valuation | VALUATION_HISTORY, ≥252 positive PE days spanning ≥365 calendar days | Rank of latest PE against prior positive PE observations | `1−2×rank`; low historical rank scores higher |
| `momentum_1m/3m/6m/12m` / Price | PRICE_ADJUSTED, 21/63/126/252 bars spanning ≥28/84/175/350 days | Last adjusted close / first − 1 | `clamp(raw/divisor)`, with divisors 0.10, 0.20, 0.30, 0.50 respectively |
| `drawdown_6m` / Price | PRICE_ADJUSTED, 126 bars spanning ≥175 days | Last adjusted close / window peak − 1 | `clamp(1 + raw/0.125)` |
| `volatility_3m` / Price | PRICE_ADJUSTED, 64 bars spanning ≥84 days | Sample standard deviation of daily adjusted returns × √252 | `clamp((0.40−raw)/0.30)` |

No factor takes a nonpositive PE as a cheapness signal. Growth with a zero, negative or near-zero base is `INVALID_INPUT`; a year gap is `INSUFFICIENT_HISTORY`. The price factors reject unadjusted bars. These rules deliberately avoid discontinuous one-point scoring thresholds, while bounded scores can still saturate at −1 or +1.

## H–I. Availability, coverage, quality and `as_of`

Required input absent → `UNAVAILABLE`, not zero. A visible series shorter than required history → `INSUFFICIENT_HISTORY`; an observed value or adjusted snapshot published/captured after `as_of` → `NOT_AVAILABLE_AS_OF`. Invalid denominator, nonpositive PE or unadjusted price → `INVALID_INPUT`. Missing optional metrics produce `PARTIAL` with factor-local coverage such as 2/3. `DEGRADED` source quality or a price-source conflict propagates to `DEGRADED` result. Quality order is `VALIDATED > UNVERIFIED > DEGRADED`, with the worst consumed component retained. Coverage combines input presence and minimum-history fulfillment; it is not the global DataAvailabilityReport score.

The loader passes the exact requested `as_of` to DataService in strict mode, never asks an Agent or LLM for data, and never requests NEWS or DIVIDEND for these factors. Derived raw metrics use the latest input availability. Current adjusted prices cannot be used for pre-capture historical replay unless a matching point-in-time snapshot exists. Future financial reports, price snapshots and reports with unavailable publication dates are excluded before factor calculation. The Stage 8 snapshot tests separately cover future news captures; no first-wave Factor consumes news.

## J–M. Versioning, golden dataset, shadow evaluation and tests

Every registered factor has a stable ID and `version="v1"`, both emitted in each result. Formula changes should create `v2`; old backtests can retain `v1`. The [golden fixture](../../tests/fixtures/factors/golden_v1.json) contains **synthetic, normalized** 600519, 000001 and 300750 cases with dates, units, availability and provenance. These are deterministic test inputs, **not observed market history**. Tests cover all 16 factors on all three contexts, required/optional missingness, coverage, history, `as_of`, negative/zero/near-zero bases, nonpositive PE, NaN rejection, degraded source, conflicts, ex-date continuity, adjusted-price requirement and registry cycles. Live 600519 DataService loading was tested separately; its results can move with upstream data. The fixed [600519 shadow report](shadow_600519.md) compares the saved legacy baseline with overlapping new factors.

Final verification: the factor test file contains **37** passing tests; `poetry run pytest -q --disable-warnings` passed **140** tests with 12 suppressed warnings. The added boundary cases verify duplicate financial dates, proxy limitation requirements, Decimal CAGR, mixed or duplicate adjusted-price dates, long gaps in volatility history, and optional metrics from a different period. The 3M momentum window uses a minimum span of 84 calendar days and passes the fixed long-window case. The ordinary CLI still displays the existing AnalystResult; no factor diagnostics were inserted into user output.

## N–O. Deferred factors and next migration

The [future requirement list](future_requirements.md) keeps analyst revisions, consensus, true surprise, management quality, moat, industry cycle, catalysts, full ownership change and official announcement events unavailable. No proxy is represented as those real data concepts.

For Phase B4, migrate one InvestorProfile at a time by **factor ID and version**, capture a before/after signal baseline, map missing/partial/degraded results to explicit Investor policy, and keep the legacy path available until each profile has passed a shadow comparison. Only then change score weights or CLI presentation. No such migration is included here.
