# Stage 8: free data capability expansion (2026-09-27)

This report records bounded live checks and code changes. It stops before Investor Factor Architecture. Existing uncommitted workspace edits were retained. Earlier production baselines remain in [`docs/baselines/stage1_600519_before.json`](../baselines/stage1_600519_before.json) and [`docs/baselines/stage47_validation.md`](../baselines/stage47_validation.md).

## A–D. Inventory, unused capability and providers

Current production sources remain BaoStock (unadjusted prices, volume, PE/PB/PS, stock name), AKShare/Sina (three statements), and AKShare/EastMoney (dated total shares, recent news). This round expands **BaoStock only**. No new Provider was registered. Full qualification evidence is in [`providers/baostock.md`](providers/baostock.md); candidate audit is in [`providers/akshare_candidates.md`](providers/akshare_candidates.md).

`CURRENT_UNUSED_CAPABILITIES` found and verified on BaoStock: `query_adjust_factor` plus both adjusted K-line modes; current CSRC industry; dividend events with plan and ex-dates; stock-basic IPO/exit/status (name was already used). BaoStock index data was already supported. AKShare's Sina dividend history and alternative price feed were tested as cross-checks, while company info failed and other event/ownership interfaces were not qualified. For each candidate's access, history, `as_of`, frequency, missingness, stability and programmatic-use evidence, see the provider reports. Unverified is never called available.

## E–F. Added capabilities and matrix

| Capability | Before | After | Production source | Limit |
| --- | --- | --- | --- | --- |
| `PRICE_ADJUSTED` | UNAVAILABLE | PARTIAL | BaoStock | Both adjustment modes, raw OHLC and factors; no vendor revision history, so pre-capture strict `as_of` is unavailable. |
| `INDUSTRY` | UNAVAILABLE | PARTIAL | BaoStock | Current CSRC class; previous revisions require snapshots. |
| `DIVIDEND` | UNAVAILABLE | PARTIAL | BaoStock | Cash/stock per share and dates; final value gated after ex-date, strict pre-capture `as_of` unavailable, official announcement ID absent. |
| `VALUATION_HISTORY` | PARTIAL | PARTIAL | BaoStock | Existing normalized PE/PB/PS; no status inflation. |
| `COMPANY_PROFILE`, `SECTOR`, `ANNOUNCEMENTS` | UNAVAILABLE | UNAVAILABLE | None qualified | No full profile, sector taxonomy or licensed disclosure feed. |
| `CORPORATE_ACTIONS`, `SHARE_CAPITAL_EVENTS`, `OWNERSHIP`, `MAJOR_SHAREHOLDERS`, `MANAGEMENT_HOLDINGS`, `SHAREHOLDER_CHANGES`, `LOCKUP_RELEASE`, `PLEDGE` | UNAVAILABLE | UNAVAILABLE | None qualified | Existing dated total-share feed is only `SHARE_CAPITAL` PARTIAL and lacks announcement time. |

The inventory contains 43 named capabilities after adding explicit names for event gaps: 5 AVAILABLE, 21 PARTIAL, 17 UNAVAILABLE. The before inventory had 39 names: 5 AVAILABLE, 18 PARTIAL, 16 UNAVAILABLE. The extra four names describe gaps, not newly obtained data. Access tier remains separate from availability; no `PAID_ONLY` availability state was introduced.

## G–H. Qualification and historical `as_of`

BaoStock passed bounded live contract checks for 600519, 000001, 300750, 600000 and delisted 600001; the old stock correctly returned no current adjusted bars or industry. The three active full-window samples each returned 311 adjusted bars with exact raw date alignment. 600519 and 000001 ex-date windows showed the expected adjusted return continuity. Provider request success in this run does not establish long-run reliability or license rights.

Current adjusted, industry and dividend results require a prior capture for strict historical replay. Pre-capture requests return `NOT_AVAILABLE_FOR_DATE`; they never reuse today's revised values as though those values were known years ago. Dividend final amounts also carry an event-level date after their ex-date, rather than the earlier plan date. That conservative rule avoids a clear future-value leak but cannot recover all historical vendor revisions. Existing Sina statements retain their actual announcement-date gate.

## I. Point-in-time snapshots

[`src/data/snapshots.py`](../../src/data/snapshots.py) adds an append-only SQLite archive: `snapshot_date`, `provider`, `capability`, `ticker`, `retrieved_at`, `raw_hash`, `normalized_result`. The hash covers the payload passed from the adapter to normalization (raw BaoStock rows, an AKShare DataFrame serialization or, for the legacy share helper, its returned row tuple); it is **not** an HTTP-body hash. No API credentials are stored. A unique key avoids duplicate captures of the same retrieved observation.

`SnapshotStore.as_of()` selects only captures with `retrieved_at <= as_of`, then checks the observation's `available_at`. Adjusted price and event snapshots additionally match the request range and adjustment mode; news snapshots retain earlier captured headlines when a later recent-feed page drops them. `DataService` uses the archive for strict historical reads and writes new present, hashed observations when a store is supplied. Set `DATA_SNAPSHOT_DB=data/snapshots.sqlite3` to enable automatic accumulation in ordinary runs; the example setting is in [`.env.example`](../../.env.example). The path is opt-in so tests and existing runs cannot silently put fixtures into a user's real archive. SQLite files are ignored by Git and need independent backup. A local real archive at `data/snapshots.sqlite3` contains six 600519 captures: name, industry, two adjusted-price revisions, share capital and news. Dividend had no event within the September 2026 capture window.

Snapshots only preserve states actually observed after capture begins. They cannot create historical news or industry states before 2026-09-27. The archive stores the normalized result and a source-payload hash, not the entire source response; a future audit requiring byte-for-byte source replay would need an additional raw-payload store.

## J. Multiple-source comparison

BaoStock versus AKShare/Sina unadjusted 600519 prices, 2026-09-21 through 09-24: four dates aligned; close and share-volume differences were all zero after unit normalization. AKShare/EastMoney displayed volume in lots and cannot be compared without multiplying by 100; a second EastMoney request failed with `ConnectionError`, so it was not registered as a redundant price provider. BaoStock versus AKShare/Sina 600519 2026-06-26 dividend: 28.02423 CNY/share versus 280.242 CNY/10 shares = 28.0242 CNY/share (rounding difference 0.00003). Their plan versus implementation announcement dates differ, so dates are not treated as interchangeable.

The Resolver now compares only equal-unit, equal-observation-date numeric candidates when asked to resolve multiple sources. A difference above tolerance marks the chosen envelope `conflict=True`, `quality=DEGRADED`, with a reason; source order alone does not hide it. Deterministic tests cover agreement, divergence and incomparable units. Production routing still has one qualified provider per capability in this round, so no fabricated live conflict was claimed.

## K–N. 600519, tests, remaining gaps and Phase B readiness

| 600519 ability | Before | After |
| --- | --- | --- |
| Unadjusted prices, statements, news, name, Analyst input and trade output | Stage 4–7 baseline | Existing route unchanged; regression tests compare prices with saved rows. |
| Adjusted prices | None | 311 raw-aligned backward/forward bars in the 2025-06-20–2026-09-25 sample, with raw OHLC, effective multiplier and vendor factor event. |
| Industry | None | Current `C15酒、饮料和精制茶制造业`; historical revisions only from local capture onward. |
| Dividend | None | Three final events in the same window; 2025-06-26 example 27.673 CNY/share. |
| 2026-09-27 local archive | None | Six captures across five 600519 capabilities; earlier history remains unavailable. |

Final local test command: `poetry run pytest -q` → **103 passed, 12 pre-existing third-party/deprecation warnings**. CI uses deterministic mocked responses; live endpoint checks were run separately. CLI, Risk Manager, Portfolio Manager, Investor signals and investment formulas were not edited. The saved 600519 unadjusted-price fixture still matches the production compatibility path.

Still not reliably free/qualified: analyst estimates, earnings revisions, consensus forecasts, complete official announcements, management/ownership changes, lockup releases, pledge events and exact historical profile/industry revisions. Tushare's official 2026-09-27 permission table puts its ordinary free tier at unadjusted daily prices only; many desired interfaces require at least 2,000 points or separate authorization. The published 2,000-point tier is priced, while individually earned-point eligibility was not tested. No paid/conditional entitlement is counted as community-free coverage.

Phase B can use existing unadjusted daily price/volume and partial valuation/statements now. Dividend-aware total return, drawdown, momentum and volatility can be **researched** using the new adjusted series and cash dividend events, subject to `as_of` and revision limits; strict pre-capture backtests cannot treat the current forward-adjusted history as point-in-time data. Current industry can support present-day classification only. No Factor weights or InvestorProfile logic were changed here.
