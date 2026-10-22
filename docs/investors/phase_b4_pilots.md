# Phase B4 pilot InvestorProfile migration

Scope: only 张坤 (`zhang_kun`), 冯柳 (`feng_liu`), 傅鹏博 (`fu_pengbo`). These are **project strategies inspired by public investing philosophies**, not reconstructions of private models. Default production remains Legacy. The other nine A-share investor agents, Risk Manager, Portfolio Manager, providers, Factor formulas and legacy `_factors()` were not migrated.

## A–B. Architecture and result contract

`DataService → RawMetricLoader → FactorEngine → FactorResult → InvestorProfile → StrategyEvaluator → StrategyEvaluationResult → AnalystResult adapter`. The strategy layer uses factor IDs and checks `v1` versions; it never imports CLI rendering. [Contracts](../../src/investors/contracts.py), [profiles](../../src/investors/profiles.py), [evaluation](../../src/investors/engine.py), and [runtime adapter](../../src/investors/runtime.py) are separate modules.

`StrategyEvaluationResult` contains `profile_id`, `profile_version`, a directional `strategy_score`, deterministic `signal` and `confidence`, versioned `used_factors` with role/weight/status/quality, core/supporting/overall coverage, profile-specific key metrics, strengths, risks, interpretations and limitations. NEW mode maps these to the existing AnalystResult fields and adds audit fields. No final trade quantity is calculated in this layer.

## C–F. Three versioned profiles

All selected IDs exist in the Factor Registry, except the explicitly typed strategy composite `low_expectation_proxy:v1`. It is built from existing versioned factors and cannot be confused with an observed expectation measure. Every profile has its own factor weights, time horizon, capability priorities, minimum factor coverage, signal policy, confidence cap, missing-data policy, metric priority and interpretation rules.

| Profile | CORE | SUPPORTING | OPTIONAL | Horizon |
| --- | --- | --- | --- | --- |
| 张坤 v2 | profitability_quality, cash_conversion, balance_sheet_safety, margin_trend | valuation_level, valuation_percentile, revenue_cagr_3y | momentum_6m, drawdown_6m | 3–5 years |
| 冯柳 v1 | low_expectation_proxy, growth_acceleration, margin_trend | earnings_growth_yoy, valuation_level, valuation_percentile | momentum_6m, drawdown_6m | 1–3 years |
| 傅鹏博 v1 | revenue_growth_yoy, earnings_growth_yoy, growth_acceleration, profitability_quality, cash_conversion | valuation_level, valuation_percentile, margin_trend, balance_sheet_safety | momentum_6m | 2–4 years |

张坤 gives operating quality, cash conversion and balance-sheet safety much greater weight than six-month price movement. Missing multi-year quality history limits confidence; persistence, moat and capital efficiency remain explicit future requirements. 冯柳 requires both a valuation/price-pressure **proxy** and positive operating improvement before a bullish signal; cheap PE or drawdown alone cannot create one. The proxy's limitation is mandatory in its FactorResult, used-factor audit and NEW reasoning. 傅鹏博 uses three growth factors in its core and prevents strong ROE alone from creating a bullish signal when growth is clearly deteriorating.

## G–I. Direction, confidence and missing data

`strategy_score = sum(available_factor_weight × normalized_score) / sum(available_factor_weight)`. Missing scores are excluded, never replaced with zero. Profile thresholds are explicit: 张坤 ±0.25; 冯柳 +0.22/−0.22 with proxy-plus-improvement gate; 傅鹏博 +0.28/−0.25 with growth-quality gate. Direction and evidence strength are separate: a bullish score can retain a low confidence when data are sparse.

`confidence = min(100, 90 × (0.65 × core_coverage + 0.25 × supporting_coverage + 0.10 × optional_coverage) × mean_quality_modifier)`, followed by profile missing-history, core-missing, proxy and critical-evidence caps and a degraded-source penalty, then rounded to one decimal. Quality modifiers are validated 1.00, unverified 0.85, degraded 0.60; a PARTIAL result additionally multiplies its quality contribution by 0.85. CORE history gaps, unavailable capabilities and the proxy limitation reduce confidence without fabricating a bearish factor score. Profile policies and caps are in source code and tested.

| Profile | Missing CORE cap | CORE history cap | Proxy cap | Minimum CORE coverage |
| --- | ---: | ---: | ---: | ---: |
| 张坤 | 55% | 65% | — | 0.60 |
| 冯柳 | 45% | 50% | 60% | 0.55 |
| 傅鹏博 | 50% | 60% | — | 0.60 |

All profiles also use a 40% cap below minimum CORE coverage and a 35% cap when critical capability evidence is unavailable. A degraded factor applies an additional 0.85 multiplier. These are explicit v1 policy choices, not statistically calibrated probabilities.

## J. Investor-specific interpretation

The same negative `momentum_6m` is a low-weight observation for 张坤, price-pressure support that still does not prove improvement for 冯柳, and auxiliary negative trend confirmation for 傅鹏博. A low `valuation_percentile` similarly produces three distinct interpretations. Strengths, risks and `key_metrics` are selected from **the factors actually used by that profile**; they are not copied from the legacy global `FACTOR_NARRATIVES`. LLM output can replace only explanatory prose in NEW mode. The code always retains deterministic signal, confidence, metrics, strengths and risks; 冯柳's proxy limitation is appended even if generated prose omits it. A deterministic fallback works without LLM.

## K. Modes and production isolation

`LEGACY` (default) follows the original path. Set `A_SHARE_INVESTOR_MODE=new|shadow|legacy`, pass `investor_mode=` to `run_hedge_fund`, or pass `state.metadata.investor_mode` for an explicit pilot run. The switch applies only to the three named profiles. `NEW` uses normalized DataService and the new strategy result. `SHADOW` returns the Legacy AnalystResult unchanged and stores a separate `data.investor_shadow[agent_id][ticker]` record with legacy factors, new used factors, both signals/confidences and change flags. The programmatic response includes `investor_shadow`; CLI `--show-reasoning` prints it when present. Shadow evaluation errors are recorded without changing the production result. Existing Risk/Portfolio consumers continue to read `data.analyst_signals`.

## L–M. 600519 / 000001 / 300750 comparison

The exact-input [synthetic Legacy baseline](../baselines/b4_legacy_fixture.json) and [synthetic shadow comparison](../baselines/b4_shadow_fixture.json) are reproducible tests, **not market observations**. They explain factor-set and formula differences without upstream timing changes. The [live Legacy capture](../baselines/b4_legacy_live_2026-09-25.json) used the old API with requested cutoff 2026-09-25; its latest returned price date was 2026-09-24 for all three tickers. The [live New probe](../baselines/b4_new_live_probe.json) used DataService on 2026-09-27. It allowed a two-minute request window so a same-run adjusted-price snapshot could be captured, then reset `as_of` to the actual retrieval completion time **before** Factor Engine evaluation; future inputs were filtered again. These live runs differ in cutoff and therefore are descriptive, not an exact point-in-time A/B backtest.

| Ticker | Profile | Live Legacy signal / confidence | Live New signal / confidence | New score | New core / supporting coverage |
| --- | --- | --- | --- | ---: | ---: |
| 600519 | 张坤 | bullish / 74.2% | bullish / 55.0% | +0.538 | 0.917 / 1.000 |
| 600519 | 冯柳 | bearish / 48.4% | bearish / 60.0% | −0.222 | 1.000 / 1.000 |
| 600519 | 傅鹏博 | neutral / 23.6% | neutral / 50.0% | +0.045 | 0.933 / 1.000 |
| 000001 | 张坤 | neutral / 0.0% | neutral / 29.6% | +0.444 | 0.000 / 1.000 |
| 000001 | 冯柳 | bullish / 34.4% | neutral / 45.0% | +0.261 | 0.667 / 0.667 |
| 000001 | 傅鹏博 | bullish / 25.6% | neutral / 35.0% | +0.044 | 0.400 / 0.500 |
| 300750 | 张坤 | bullish / 77.8% | neutral / 55.0% | +0.240 | 0.917 / 1.000 |
| 300750 | 冯柳 | bullish / 60.6% | bullish / 60.0% | +0.742 | 1.000 / 1.000 |
| 300750 | 傅鹏博 | bullish / 77.8% | bullish / 50.0% | +0.584 | 0.933 / 1.000 |

Changes reflect different factor definitions, required histories, profile gates and quality/coverage rules; the differing live cutoffs may contribute. In particular, 000001 冯柳 has a positive strategy score but remains neutral without enough improvement evidence. 300750 张坤 shifts from bullish to neutral because its continuous quality score sits below that profile's +0.25 threshold. The low New confidence on several rows reflects core or proxy evidence caps, rather than a rescaled Legacy confidence. The JSON comparison contains each profile's factor set, used factors, statuses, key metrics, strengths, risks and explicit signal/confidence deltas.

## N–O. Verification and next migration gate

Tests cover all three distinct CORE sets, metric priorities, rules and missing policies; same-factor different interpretation; proxy limitation and improvement gate; 张坤's negative-momentum case; 傅鹏博's growth-quality conflict; deterministic confidence, absent scores and caps; mixed-`as_of` and version rejection; all three Legacy/Shadow/NEW agent modes; no-LLM fallback; untouched behavior for a nonpilot investor; and preservation of the Legacy result under Shadow, including a three-agent workflow. `poetry run pytest -q --disable-warnings`: **155 passed, 12 warnings**. Python compilation of new modules and capture scripts also passed.

The architecture is suitable for **planning** migrations of the remaining nine profiles, but they have not been migrated. Before enabling NEW by default, run matched-cutoff, point-in-time live shadow captures for an extended observation period, review false positives and provider coverage, then migrate and version one profile at a time. The current live table is not sufficient evidence to switch the production default.
