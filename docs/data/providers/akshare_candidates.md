# AKShare and official-source candidates — Stage 8 (2026-09-27)

AKShare documentation checked: [A-share stock data](https://akshare.akfamily.xyz/data/stock/stock.html). Installed AKShare version: `1.18.97`. AKShare wraps several upstream sites, so the package interface alone does not prove upstream publication time, long-run availability, API authorization or data redistribution rights.

| Candidate capability | AKShare interface / upstream | Login / token | Bounded runtime result and temporal quality | Decision |
| --- | --- | --- | --- | --- |
| Company profile | `stock_individual_info_em` / EastMoney | None observed / no token | 600519 request failed with `ConnectionError`; cannot estimate historical span or missingness. | Candidate; current BaoStock name is retained. |
| Dividend | `stock_history_dividend_detail` / Sina | None observed / no token | 600519 returned 31 rows with announcement and ex-dates; displayed `派息` is per ten shares (2026-06-26: 280.242 per ten, versus BaoStock 28.02423 per share). The shown announcement date is implementation-stage 2026-06-22, not BaoStock's initial-plan date. | Useful independent cross-check; no duplicate production adapter. |
| Share-capital events | `stock_zh_a_gbjg_em` / EastMoney | None observed / no token | 600519 returned 16 dated rows, including `变动原因`, but no announcement timestamp. Pandas `SettingWithCopyWarning` appeared. | Existing share-capital provider remains partial; no claim of historical publication time. |
| Alternative unadjusted OHLC | `stock_zh_a_daily` / Sina; `stock_zh_a_hist` / EastMoney | None observed / no token | Sina produced four 600519 days 2026-09-21–24 and matched BaoStock close and share volume exactly. EastMoney returned once and then failed with `ConnectionError`. | No extra price provider: no capability gain and instability observed. |
| Industry / sector, stock actions, holders, management, lockups, pledge | AKShare catalog contains candidate interfaces, including CNInfo and EastMoney wrappers | Interface-dependent | Historical publication time, per-ticker missingness, stability and upstream license were not verified in this round. | **UNAVAILABLE** in production; no registry entry. |
| Announcements | `stock_notice_report` / EastMoney wrapper | Interface-dependent | The listed endpoint was not qualified against source ID, true `published_at`, document URL and license. | **UNAVAILABLE** in production. |

Official disclosure research: the [CNInfo public site](https://www.cninfo.com.cn/new/index) links to a [data service platform](https://webapi.cninfo.com.cn/) that advertises API access. The visible site does not establish anonymous API entitlement, rate limits or redistribution permission. No CNInfo adapter or private webpage endpoint was added.

## Tushare registered/paid gate

The current official [permission matrix](https://tushare.pro/document/2?doc_id=108), [price/frequency table](https://tushare.pro/document/2?doc_id=290) and [stock-basic page](https://tushare.pro/document/2?doc_id=25) were read on 2026-09-27. The published zero-price tier has 120 points, 50 requests/minute and 8,000/day, restricted to **unadjusted daily prices**. The 2,000-point tier is listed at CNY 200/year; its frequency table shows 200 requests/minute and 100,000/day per API. The site also describes earning points, but no account-specific earned points were verified. Separate-entitlement APIs, including announcements/news, are outside ordinary points entitlement.

| Desired capability | Official permission evidence | Community-free decision |
| --- | --- | --- |
| `STOCK_BASIC` / company name | `stock_basic` 2,000 points | Not verified free; BaoStock already covers name. |
| Adjusted OHLC and `ADJ_FACTOR` | `pro_bar` adjusted history 2,000 points; factor permission not separately proven | Not added; BaoStock extension already covers current series. |
| `DAILY_BASIC` valuation | Permission matrix lists 2,000 points minimum | Not added; BaoStock already supplies partial PE/PB/PS. |
| `FINANCIAL_INDICATORS` | `fina_indicator` 2,000 points minimum | Not added; Sina statement-derived fields remain. |
| `DIVIDEND` | `dividend` 2,000 points minimum | Not added; BaoStock supplies partial events. |
| Industry/sector | `index_classify` 2,000 points minimum; constituent interface also listed at 2,000 | Not added; current BaoStock industry is partial. |
| Shareholder counts/changes, pledge | `stk_holdernumber`, `stk_holdertrade`, `pledge_stat` listed at 2,000 points | Not added without account entitlement. |
| Lockup release | `share_float` listed at 3,000 points | Not added without account entitlement. |
| Announcements/news | Separate entitlement in the current price/frequency table | Not treated as registered-free. |

Tushare is a conditional `REGISTERED_FREE` candidate **only for permissions an actual user account can demonstrate without payment**; the published paid point tiers and separate entitlements are not counted as free coverage. No user token or account rights were available, so no Tushare request or Provider registration occurred. The checked official pages did not establish a general student/high-school eligibility grant; `STUDENT_VERIFICATION` is not hard-coded.

This is a bounded audit, not a claim that untested candidate APIs are absent. For all unqualified rows, historical span, missing rate, update cadence, `available_at` quality, programmatic-use permission and request success rate are **unknown**, rather than silently assumed to be good.
