# Stage 4–7 validation (600519)

Parameters: 2026-03-25 through 2026-09-25, one 段永平 strategy prototype,
DeepSeek `deepseek-chat`, CNY 100,000 starting cash, no positions.
The source baseline is `stage1_600519_before.json`. The final run is
`stage47_600519_after.json`. Neither file contains API credentials.

| Migrated ability | Test and baseline result |
| --- | --- |
| Unadjusted daily prices | 127 rows, 2026-03-25 through 2026-09-24; every legacy field and value equal. |
| Instrument name | 600519 → 贵州茅台; missing and request failure have different typed states. |
| Three financial statements | Latest legacy metrics report period 2026-06-30; every metric field equal. Publication date gates strict as-of reads. |
| Dated share capital | Legacy market capitalization inputs and output equal. Feed lacks announcement time, so strict historical reads cannot claim visibility before a saved retrieval. Compatibility observations are marked DEGRADED. |
| Valuation history | BaoStock daily PE/PB/PS normalized as a dated series. Derived market capitalization records price and dated-share input provenance. Latest legacy PE/PB/PS and market cap equal. |
| Recent news | Ten legacy news rows equal. Typed results distinguish empty success, source failure, unsupported, and unavailable historical date. |

Deterministic comparisons: prices, financial metrics, news, stock name, Analyst
input, Analyst signal/confidence/key metrics/strengths/risks, and Risk Manager
output are equal. The live Portfolio Manager again returned BUY 15, within the
Risk Manager maximum of 15 shares. Its confidence was 65 versus 66 in the
Stage 1 baseline; the LLM also changed the reasoning text. A mock-LLM full
workflow test checks the deterministic chain and valid trading quantity.

The run-level DataAvailabilityReport for the selected strategy counted six
requested ticker/capability pairs: five available, share capital partial,
coverage 0.9167. This is request-level coverage, not total system coverage.

Limits retained intentionally: legacy list-returning news calls still map
non-present typed results to an empty list for existing Agent compatibility;
the typed DataService result and run availability report preserve the reason.
The share-capital source has change dates but no publication dates, and the
recent-news feed has no reliable historical snapshots. Strict historical
queries do not treat those later-fetched records as known in the past.
