# Phase B4.5: Matched Shadow Validation

## Scope and safety boundary

This phase adds a research-only matched evaluator for the three existing pilot profiles. The production default remains `LEGACY`; the runner is not connected to the graph, Risk Manager, Portfolio Manager, or the other nine Investors. It does not optimize historical returns or tune weights, thresholds, or confidence.

## Frozen snapshot and matched inputs

`FrozenDataSnapshot.capture_current()` calls the existing `DataService` once for current BaoStock and AKShare data. It retains the provider envelopes and the normalized `FactorContext`, including provider status, observation dates, availability, retrieval time, quality, revision, and the full normalized price bars. The snapshot freezes at capture completion and filters observations against `available_at` and the local market date. Snapshot validation rejects a ticker mismatch, different price rows, adjustment mismatch, or a metric published after `as_of`.

`MatchedShadowRunner.run(ticker, investor_profile, as_of, frozen_data)` accepts only the frozen snapshot. It has no Provider or DataService dependency and makes no external requests. New factors and the Legacy adapter both read the same normalized financial points and adjusted price bars. For six-month momentum, the Legacy adapter uses the exact 126 adjusted bars consumed by New, with the same start/end dates and close values; only the Legacy hard-grade formula differs. The production Legacy agent remains unchanged. A `snapshot_id` binds both evaluations to the exact serialized input. The DifferenceReport includes an input manifest with adjustment mode, price range/count, statement counts, capability statuses, and provider IDs. `save_frozen_snapshot()` and `save_shadow_result()` write replayable snapshot and result JSON atomically.

Current free-provider endpoints do not expose archived revisions for adjusted price history, industry, or share-capital data. Therefore `capture_current()` is a current capture, not a way to reconstruct an arbitrary historical snapshot. A historical `as_of` run needs an already archived snapshot.

## Difference report and explainability

Every match stores Legacy raw factor values, factor scores, signal and confidence; New used factors, versions, scores, strategy score, signal, confidence, three coverage values, and limitations; plus added/removed factors, formula notes, missing-data and proxy effects, signal/confidence changes, and the threshold/gate trace.

Each New evaluation now has `FactorContribution` records linking the selected factor version and role to its raw value, normalized score, active weight, exact weighted contribution, raw metric inputs, and provenance. Contributions reconcile exactly to `strategy_score`, including a deterministic Decimal residual assignment on the final active contribution. `SignalExplanation` records the thresholds, profile gate, gate inputs, pass state, and reason code. The accompanying Chinese `signal_reason` remains a readable summary.

Confidence means “当前策略判断的数据支撑和结论可信程度”; it is not an upside probability, profit probability, or win rate. This definition is carried on the result schema and should be preserved in future UI/API contracts.

## Validation corpus

`tests/fixtures/shadow/strategy_semantics_v1.json` contains 12 deterministic, label-free scenario inputs covering mature quality, high growth, financials, cyclicals, expensive growth, cheap low growth, drawdown with improving/deteriorating operations, high ROE with weak cash, high debt, growth slowdown, and severe missing evidence. The cases perturb normalized factor inputs for offline strategy-semantics checks; they are not claims about named public companies and contain no assigned `bullish`/`bearish` labels. The separately captured live sample catalog is also replayed offline in CI; those tests never make external requests.

## Live matched sample catalog

Eighteen successful current snapshots were captured on 2026-09-27 from the configured free sources. All returned price and valuation histories have 287 rows from 2025-07-24 through 2026-09-24. Income, balance-sheet, and cash-flow rows vary by ticker; the latest statement period in each snapshot is 2026-06-30. The capture timestamp is later than the latest market-data date and is recorded separately as `as_of`.

| Frozen input | Provider | Coverage across the 18 snapshots |
|---|---|---:|
| Backward-adjusted prices | BaoStock | 287 bars each; 2025-07-24 to 2026-09-24 |
| Valuation history | BaoStock | 287 rows each; same observation window |
| Income statements | AKShare/Sina | 32–123 periods per ticker; latest period 2026-06-30 |
| Balance sheets | AKShare/Sina | 29–120 periods per ticker; latest period 2026-06-30 |
| Cash-flow statements | AKShare/Sina | 32–104 periods per ticker; latest period 2026-06-30 |
| Share-capital events | AKShare/Eastmoney | 15–667 events per ticker |
| Industry | BaoStock | Present for all 18 snapshots |
| Dividends | BaoStock | 0–3 events per ticker |

`docs/baselines/shadow/live/catalog.json` indexes all 18 snapshots and their 54 saved matched results. It contains no manually assigned signal labels. `test_live_catalog_replays_all_matched_results_without_provider_access` reloads each frozen input and reproduces all three profile results against the saved result records. This gives deterministic regression coverage while retaining actual observed outputs as replay evidence.

The sample spans BaoStock industry classifications C15 (000858, 600519), C38 (000333, 000651, 300014, 300207, 300274, 300750), C32 (002460, 600111), C36 (002594, 600418, 601127), J66 financial services (000001, 600036, 601398), C39 (000063), and I65 (688256). A few observed dimensions from the frozen data are:

- 300750: 2025 annual net income grew 42.3% year over year; 2026-06 total liabilities/assets was 63.7%.
- 688256: 2025 annual net income grew 555.2%; latest captured PE was 206.0. A single-year growth rate can reflect a low comparison base, and PE is not directly comparable across industries.
- 002460: maximum close-to-prior-peak drawdown in the captured window was 52.1%, while 2025 annual net income grew 177.8%.
- 000063: the same price-window measure was a 40.7% drawdown, and 2025 annual net income fell 33.3%.
- 000651: latest captured PE was 7.7 and 2025 annual net income fell 9.9%; this is a low-PE/weak-growth observation within this sample, not a universal valuation label.

These are descriptions of the captured statements, prices, and valuation rows, not assigned strategy outcomes. The synthetic corpus remains the controlled source for specific high-ROE/weak-cash, debt, and missing-data behavior scenarios.

Two additional capture candidates, 600438 and 688347, failed before a snapshot could be saved because BaoStock returned a blank adjusted-volume field that could not be parsed as a decimal. Provider code was not changed; those failures are excluded from the successful sample catalog.

## Matched live comparisons

For 600519 all three profiles used the same snapshot `d37d7fdaef87986a509449fb31e0d4418b52222d669f67602a410239e84d8207`, with `as_of=2026-09-27T14:12:12.075721Z`.

| Profile | Legacy | New | New score | Core / overall coverage | Confidence delta |
|---|---|---|---:|---:|---:|
| 张坤 v2 | bullish / 52.5 | bullish / 55.0 | 0.5379 | 0.9167 / 0.9630 | +2.5 |
| 冯柳 v1 | neutral / 24.1 | bearish / 60.0 | -0.2223 | 1.0000 / 1.0000 | +35.9 |
| 傅鹏博 v1 | neutral / 30.8 | neutral / 50.0 | 0.0446 | 0.9333 / 0.9667 | +19.2 |

These differences are comparison evidence, not a correctness ranking. The same 126 adjusted bars yield a Legacy six-month return of -9.63%, which remains in its neutral hard-grade band; New maps that return continuously to a -0.321 factor score. The source window is matched, while formula and threshold behavior differ. For 冯柳 the low-expectation proxy is available, but the operating-improvement mean is -0.4703, so the profile gate produces bearish just past its score boundary. For 傅鹏博 the three growth inputs average -0.4290; the growth gate blocks bullish despite high profitability and cash-conversion scores. For 张坤 the quality, cash-conversion, and balance-sheet core scores dominate the lower-weight momentum observation. The confidence values remain evidence-confidence scores, not probabilities.

Across all 18 live tickers, Legacy/New signals differ on 5/18 Zhang Kun, 11/18 Feng Liu, and 6/18 Fu Pengbo comparisons. Mean confidence deltas (New minus Legacy) are +13.64, +14.15, and +4.56 points respectively; per-profile ranges are -15.6 to +31.4, -31.9 to +35.9, and -20.6 to +19.2. These are descriptive differences in model behavior, not calibration or accuracy results. In the final three added samples, the signal pairs were: 000063 — Feng bearish/neutral, Fu bearish/neutral, Zhang bearish/bearish; 600418 — Feng neutral/neutral, Fu bearish/neutral, Zhang bearish/bearish; 601127 — all three neutral/neutral.

## Evidence-driven Profile change

One output-contract defect was found: 张坤 v1 had an `valuation_level` strength message but no corresponding risk message. A high-quality/high-valuation case could therefore omit the requested valuation risk. Added the explicit risk wording “核心经营质量良好，但估值偏高压缩预期回报” and incremented only Zhang Kun's profile version to v2. No factor formula, weight, signal threshold, or confidence policy changed. Historical B4 records remain v1 and are not rewritten.

The other detected issue was numerical bookkeeping rather than an investment-policy change: independent Decimal divisions could make the displayed factor contributions sum to the strategy score with a last-place residual. The final active contribution now absorbs that deterministic residual so the audit trail reconciles exactly.

Matched replay also exposed nondeterministic ordering in the missing-capability explanation because it iterated a `frozenset`. Capabilities are now rendered in sorted order. This only stabilizes explanatory text; signal, score, confidence, and factor inputs are unchanged. The three affected Zhang Kun result records were regenerated from their original frozen snapshots with only that ordering normalized.

## Test coverage and migration assessment

`tests/test_matched_shadow.py` verifies snapshot round-trip/hash stability, future-publication rejection, ticker/as-of/adjustment matching, identical adjusted-price input, no Provider calls inside the runner, full DifferenceReport fields, provenance links, exact contribution reconciliation, all three profiles' behavioral cases, confidence monotonicity, signal monotonicity including profile gates, key-metric provenance, profile-specific strengths/risks, proxy limitations, missing-data states, persistence, all 12 synthetic corpus entries, and offline replay of all 54 live catalog comparisons.

Validation completed with `poetry run pytest -q`: 177 passed, with 12 dependency deprecation warnings. `compileall` and `git diff --check` also passed.

This phase does **not** authorize migration of the remaining nine Investors. Eighteen live tickers provide broader coverage, but they are from one capture date and do not establish long-term stability, strategy accuracy, or readiness of the other nine profile definitions. The 12-case semantic corpus is synthetic and deterministic. Broader time coverage and separate review of each remaining profile are still required before migration readiness can be claimed.
