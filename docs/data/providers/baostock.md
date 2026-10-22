# BaoStock qualification — Stage 8 (2026-09-27)

## Scope and sources

Runtime: Poetry environment, BaoStock `00.9.40`, anonymous `bs.login()` returned code `0`. The installed BaoStock API docstrings and live responses were checked for `query_adjust_factor`, `query_history_k_data_plus`, `query_stock_industry`, `query_stock_basic`, and `query_dividend_data`. The vendor site is [baostock.com](https://baostock.com); its current landing page did not expose a stable, machine-readable API specification or redistribution license during this audit. Treat license/redistribution as unverified; this qualification covers technical use in the local project only.

| Capability | API and raw fields | Login / token | Observed history and timing | Qualification |
| --- | --- | --- | --- | --- |
| Adjusted daily OHLC | `query_history_k_data_plus`, `adjustflag=1` backward, `2` forward, `3` unadjusted; `query_adjust_factor` provides `dividOperateDate`, `foreAdjustFactor`, `backAdjustFactor`, `adjustFactor` | BaoStock session / no user token | 311 trading bars for each of 600519, 000001 and 300750 from 2025-06-20 to 2026-09-25. Factor events present from 2023 onward in this sample. Vendor gives no historical revision timestamp. | **PARTIAL**: current series works; strict historical `as_of` requires a previously captured snapshot. |
| Industry | `query_stock_industry`: `updateDate`, `industry`, `industryClassification` | Same | Three active samples returned one CSRC industry row updated 2026-09-21. Delisted 600001 returned an empty industry. No historical revision feed verified. | **PARTIAL**: current classification only, archived from capture. |
| Dividend | `query_dividend_data(yearType='operate')`: plan announcement date, record date, ex-date, cash/stock per share | Same | 600519, 000001 and 300750 each returned three events in the requested 2025-06-20 to 2026-09-25 window. Final payout is gated to the day after ex-date because an earlier plan date does not prove the final amount was already known. | **PARTIAL**: strict pre-capture `as_of` is unavailable; date-level timing and no official announcement ID. |
| Stock basic | `query_stock_basic`: name, IPO date, exit date, type, status | Same | Names returned for all five qualification symbols, including delisted 600001. Name only was already in production. | Existing partial metadata; no claim of a complete company profile. |
| Index history | `query_history_k_data_plus` for `sh.000300` | Same | Existing index price path retained. Adjusted stock semantics are not assigned to the index. | Existing capability unchanged. |

## Five-symbol checks

| Ticker | Characteristic | Adjusted OHLC | Industry | Dividend/factor evidence |
| --- | --- | --- | --- | --- |
| 600519 | Large, long-listed, regular cash dividends | 311 / 311 matching raw trading dates; first 2025-06-20, last 2026-09-24 | `C15酒、饮料和精制茶制造业` | 2025-06-26 ex-date: raw close return -1.1046%, backward +0.8336%, forward +0.8337%. |
| 000001 | Long-listed bank, recent ex-date | 311 / 311 matching dates | `J66货币金融服务` | 2026-09-24 ex-date: raw -2.5862%, backward -0.4406%, forward -0.4405%. |
| 300750 | Growth-board constituent | 311 / 311 matching dates | `C38电气机械和器材制造业` | Seven factor events in 2023-2026 sample; dividends returned. |
| 600000 | Older bank with conspicuous ex-date | Two event-window bars tested | `J66货币金融服务` | 2026-07-16 ex-date: raw -4.9409%, backward -0.4500%, forward -0.4499%. |
| 600001 | Delisted 2009-12-29 | Empty in current window, expected | Empty | No recent factor/dividend events, expected. |

The three active full-window adjusted calls each had 311 raw/adjusted date matches (0 missing pairs in this sample). All BaoStock requests in this bounded run returned error code `0`; this is **not** a long-run uptime estimate. Schema fields matched the installed API in this run; schema stability across vendor upgrades is unmeasured. No credential was used or saved.

| Qualification measure | Observed result |
| --- | --- |
| Coverage | 3/3 active full-window adjusted series present; 600000 ex-date pair present; delisted 600001 correctly empty. Industry 4/4 active names in the five-symbol sample; 600001 industry empty. |
| Earliest / latest adjusted day | 2025-06-20 / 2026-09-24 for the three full-window symbols; the requested end was 2026-09-25. |
| Missing rate | 0/933 raw/adjusted date pairs missing for 600519, 000001 and 300750. This measures pair alignment, not all exchange trading days. |
| Request success | All bounded BaoStock requests returned API code `0`; no statistical uptime claim. |
| Schema stability | Expected fields in this version and run; cross-version stability unmeasured. |
| Update frequency | Daily K-lines; industry `updateDate` last showed 2026-09-21; dividends are event-driven. No vendor SLA verified. |
| `available_at` and `as_of` | Adjusted and industry history lack revision timestamps; strict pre-capture replay unavailable. Dividend event date is conservative, but strict replay also requires capture. |
| Unit consistency | OHLC in CNY, volume in shares, dividend cash in CNY/share, factor dimensionless. |

## `as_of`, units, and maintenance

- Raw and adjusted OHLC are separate. An adjusted bar keeps raw OHLC, the effective adjusted/raw multiplier, the latest vendor factor and its event date. Volume remains individual shares. Forward-adjusted values can change after future dividends, so both adjusted modes are unavailable for an earlier strict `as_of` without a local snapshot captured by that time.
- Industry `updateDate` is **not** treated as a publication timestamp. Current classification is visible only from local retrieval; prior snapshots are needed for backtests.
- Dividend cash is CNY per share; a plan announcement date is retained, but the final amount is visible only after ex-date. Strict historical reads before a local capture return `NOT_AVAILABLE_FOR_DATE` because the vendor does not expose all value revisions.
- New adapter responses carry source-payload SHA-256 where captured. A snapshot records the adapter-received payload hash, normalized result and actual retrieval time. It does not invent a pre-capture state.
- Public documentation/licensing and request limits were not conclusively verified; no data is redistributed by this project change. Recheck before commercial or bulk use.
