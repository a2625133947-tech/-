# Phase B5: Shadow-Only Investor Expansion

## 1. Scope and Safety Boundaries

Phase B5 expands the research-only shadow evaluation framework from the three pilot profiles (张坤 v2, 冯柳 v1, 傅鹏博 v1) to the seven `DESIGN_READY` investors:
- **段永平** (duan_yongping v1)
- **邓晓峰** (deng_xiaofeng v1)
- **朱少醒** (zhu_shaoxing v1)
- **刘彦春** (liu_yanchun v1)
- **谢治宇** (xie_zhiyu v1)
- **董承非** (dong_chengfei v1)
- **陈光明** (chen_guangming v1)

**Strict Safety Mandates**:
1. **Production Default**: Remains strictly `LEGACY`.
2. **Shadow-Only**: In `SHADOW` mode, production `analyst_signals` strictly retains Legacy outputs. Risk Manager and Portfolio Manager read only Legacy signals and confidence. New results are computed in the background and stored exclusively under `investor_shadow`.
3. **NOT_READY Investors**: **王亚伟** and **林园** remain in `NOT_READY` status; they do not have `InvestorProfile` implementations and remain 100% in Legacy.
4. **No Parameter Tuning**: Factor formulas, weights, and thresholds were not tweaked to chase alpha or match legacy signals.

---

## 2. Factor Registry Audit

Before implementing the new profiles, `default_registry()` was audited:
- **Available Factors (16 total)**:
  `balance_sheet_safety`, `cash_conversion`, `drawdown_6m`, `earnings_growth_yoy`, `growth_acceleration`, `margin_trend`, `momentum_12m`, `momentum_1m`, `momentum_3m`, `momentum_6m`, `profitability_quality`, `revenue_cagr_3y`, `revenue_growth_yoy`, `valuation_level`, `valuation_percentile`, `volatility_3m`.
- **Volatility Check**:
  Phase B4.6 design draft mentioned `volatility_6m`. Actual registry contains only `volatility_3m`. Rather than inventing an unverified `volatility_6m`, **董承非** profile was configured with the verified `volatility_3m` from the registry.

---

## 3. Coverage Semantics Refinement

To avoid the misconception that "Factor Coverage" equates to "Philosophy Completeness", coverage is explicitly partitioned:
- **`implemented_factor_coverage`**: The fraction of declared factors in the profile that can actually be calculated with valid scores by the Factor Engine for the requested observation window.
- **`strategy_evidence_coverage`**: The fraction of the strategy's theoretical evidence dimensions supported by the current data and factor engine:
  $$\text{strategy\_evidence\_coverage} = \text{implemented\_factor\_coverage} \times \frac{N_{\text{declared\_factors}}}{N_{\text{declared\_factors}} + N_{\text{known\_missing\_dimensions}}}$$
- **`known_missing_dimensions`**: Formally recorded qualitative and structural dimensions of the investor's philosophy that the quantitative model cannot express (e.g. franchise moat, capital allocation quality, commodity cycle stage). Strategy coverage can never claim "100%".

---

## 4. Profile Design Summary (Seven Expanded Profiles)

| Investor | Version | Style | CORE Factors | SUPPORTING Factors | OPTIONAL Factors | Key Gate & Reason Code | Known Missing Dimensions |
|---|---|---|---|---|---|---|---|
| **段永平** | v1 | `long_term_quality` | `profitability_quality`, `cash_conversion`, `balance_sheet_safety`, `margin_trend` | `valuation_level`, `valuation_percentile` | `revenue_cagr_3y` | `long_term_quality_core_evidence` | 商业模式护城河, 长期再投资资本回报, 管理层资本配置, 品牌与特许经营壁垒 |
| **邓晓峰** | v1 | `value_turnaround` | `valuation_level`, `valuation_percentile`, `earnings_growth_yoy`, `margin_trend` | `profitability_quality`, `balance_sheet_safety` | `momentum_6m`, `drawdown_6m` | `valuation_and_earnings_recovery`<br>`operating_deterioration_blocks_turnaround` | 行业周期位置, 大宗商品价格敏感度, 产业景气阶段, 产能去化程度 |
| **朱少醒** | v1 | `balanced_quality_growth` | `profitability_quality`, `revenue_growth_yoy`, `cash_conversion` | `valuation_level`, `balance_sheet_safety`, `margin_trend`, `growth_acceleration` | `momentum_6m`, `drawdown_6m` | `quality_not_failing`<br>`weak_quality_blocks_growth` | 管理层资本配置质量, 长期竞争优势, 企业家精神与公司治理 |
| **刘彦春** | v1 | `consumer_quality_growth` | `profitability_quality`, `revenue_growth_yoy`, `earnings_growth_yoy`, `cash_conversion` | `margin_trend`, `revenue_cagr_3y`, `valuation_level` | `balance_sheet_safety`, `momentum_6m` | `growth_positive_gate`<br>`revenue_contraction_blocks_bullish` | 品牌定价权, 渠道库存与动销, 终端消费者粘性, 复购与品类扩张 |
| **谢治宇** | v1 | `growth_valuation_balance` | `growth_acceleration`, `revenue_growth_yoy`, `earnings_growth_yoy`, `valuation_level` | `profitability_quality`, `valuation_percentile`, `balance_sheet_safety` | `momentum_6m` | `growth_deceleration_gate`<br>`growth_deceleration_blocks_bullish` | PEG 动态指标, 行业相对估值, 远期盈利预测, 产业技术演进判断 |
| **董承非** | v1 | `value_discipline_safety` | `balance_sheet_safety`, `valuation_level`, `valuation_percentile`, `cash_conversion` | `profitability_quality`, `drawdown_6m` | `volatility_3m`, `momentum_6m` | `balance_sheet_safety_gate`<br>`balance_sheet_risk_blocks_bullish` | FCF multiple / P-CF, 股息持续性与分红意愿, 资产重置成本与清算价值 |
| **陈光明** | v1 | `quality_value_cash` | `profitability_quality`, `cash_conversion`, `balance_sheet_safety`, `valuation_level` | `valuation_percentile`, `margin_trend`, `revenue_cagr_3y` | `drawdown_6m` | `cash_backing_gate`<br>`weak_cash_conversion_blocks_bullish` | 股东盈余精确模型, 公司治理评分, 长期资本配置效率 |

---

## 5. Frozen Snapshot Replay (18 Live Snapshots $\times$ 7 Profiles)

Using `MatchedShadowRunner` completely offline without any provider calls:
- All 18 baseline snapshots were evaluated across the 7 new profiles ($18 \times 7 = 126$ new matched comparison records).
- Atomic matched results were saved to `docs/baselines/shadow/live/results/`.
- Total shadow results in the baseline library are now $18 \times 10 = 180$ records.
- `docs/baselines/shadow/live/temporal_catalog.json` was updated with 18 catalog entries, each indexing the 10 shadow profile evaluations.

---

## 6. Synthetic Behavioral Validation

Synthetic scenario tests in `tests/test_expanded_shadow.py` verify that each profile enforces its distinct strategy philosophy:
1. **段永平**: High business quality ($+0.80$) with severe price decline ($-0.90$) remains bullish ($+0.60+$ score); short-term momentum does not dominate.
2. **邓晓峰**: Cheap valuation ($+0.90$) combined with deteriorating earnings ($-0.60$) and margins ($-0.50$) blocks bullish signal (`operating_deterioration_blocks_turnaround`).
3. **朱少醒**: Blistering growth ($+0.95$) with severely degraded quality ($-0.40$ ROE, $-0.50$ cash conversion) blocks bullish signal (`weak_quality_blocks_growth`).
4. **刘彦春**: High margins ($+0.85$) with contracting consumer demand ($-0.45$ revenue, $-0.50$ net income) blocks bullish signal (`revenue_contraction_blocks_bullish`).
5. **谢治宇**: Growth deceleration ($-0.60$ acceleration) with stagnant profit blocks bullish signal (`growth_deceleration_blocks_bullish`).
6. **董承非**: Deep valuation discount ($+0.80$) with excessive balance sheet leverage ($-0.50$) blocks bullish signal (`balance_sheet_risk_blocks_bullish`).
7. **陈光明**: High accounting ROE ($+0.85$) without cash flow backing ($-0.50$ cash conversion) blocks bullish signal (`weak_cash_conversion_blocks_bullish`).

---

## 7. Migration Readiness Matrix

| Investor | Profile Version | Phase Status | Factor Engine Coverage | Implemented Coverage | Evidence Coverage | Known Missing Dimensions Count | Shadow Replay Status | Production Status |
|---|---|---|---|---|---|---|---|---|
| **张坤** | v2 | Pilot | 95% | 55.6%–96.3% | 45.5%–78.8% | 2 | `SHADOW_READY` | LEGACY |
| **冯柳** | v1 | Pilot | 75% | 75.0%–100.0% | 54.5%–72.7% | 3 | `SHADOW_READY` | LEGACY |
| **傅鹏博** | v1 | Pilot | 90% | 50.0%–96.7% | 41.7%–80.6% | 2 | `SHADOW_READY` | LEGACY |
| **段永平** | v1 | Expanded | 100% | 42.9%–95.2% | 27.3%–60.6% | 4 | `SHADOW_READY` | LEGACY |
| **邓晓峰** | v1 | Expanded | 85% | 50.0%–95.8% | 33.3%–63.9% | 4 | `SHADOW_READY` | LEGACY |
| **朱少醒** | v1 | Expanded | 90% | 55.6%–96.3% | 41.7%–72.2% | 3 | `SHADOW_READY` | LEGACY |
| **刘彦春** | v1 | Expanded | 95% | 44.4%–96.3% | 30.8%–66.7% | 4 | `SHADOW_READY` | LEGACY |
| **谢治宇** | v1 | Expanded | 85% | 62.5%–95.8% | 41.7%–63.9% | 4 | `SHADOW_READY` | LEGACY |
| **董承非** | v1 | Expanded | 85% | 62.5%–95.8% | 41.7%–63.9% | 4 | `SHADOW_READY` | LEGACY |
| **陈光明** | v1 | Expanded | 90% | 50.0%–95.8% | 33.3%–63.9% | 4 | `SHADOW_READY` | LEGACY |
| **王亚伟** | — | Unmigrated | 65% | — | — | >5 | `NOT_READY` | LEGACY |
| **林园** | — | Unmigrated | 80% | — | — | >5 | `NOT_READY` | LEGACY |

---

## 8. Test Execution Summary

Running `poetry run pytest`:
- Original baseline tests: **177 passed**
- BaoStock volume regression tests: **+2 passed**
- Temporal shadow validation tests: **+22 passed**
- Expanded shadow investor tests: **+13 passed**
- **Total Suite**: **214 passed**, 0 failed, 12 dependency deprecation warnings.
