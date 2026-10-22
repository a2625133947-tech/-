"""Ten explicitly different, public-philosophy-inspired project strategy prototypes.

Pilot Profiles (B4):
  - zhang_kun (v2)
  - feng_liu (v1)
  - fu_pengbo (v1)

Expanded Shadow Profiles (B5):
  - duan_yongping (v1)
  - deng_xiaofeng (v1)
  - zhu_shaoxing (v1)
  - liu_yanchun (v1)
  - xie_zhiyu (v1)
  - dong_chengfei (v1)
  - chen_guangming (v1)

NOT_READY Profiles (Kept in Legacy):
  - wang_yawei (missing restructuring/flow data)
  - lin_yuan (missing monopoly/pricing power proxy)
"""

from decimal import Decimal

from src.data.capabilities import Capability as C
from src.factors.engine import default_registry
from src.investors.contracts import (
    ConfidencePolicy, InvestorProfile, MissingDataPolicy, SignalPolicy,
)

PROXY_ID = "low_expectation_proxy"
_registry = default_registry()


def _profile(*, profile_id, display_name, description, core, supporting, optional,
             weights, horizon, critical, important, extra, coverage, signal,
             missing, priority, strengths, risks, interpretations, limitations=(),
             known_missing_dimensions=(), version="v1"):
    selected = core + supporting + optional
    for factor_id in selected:
        if factor_id != PROXY_ID:
            _registry.get(factor_id)  # Reject an invented or renamed Factor ID.
    return InvestorProfile(
        profile_id=profile_id, display_name=display_name, description=description,
        version=version, core_factors=core, supporting_factors=supporting,
        optional_factors=optional,
        factor_weights={key: Decimal(str(weights[key])) for key in selected},
        factor_versions={key: "v1" for key in selected}, time_horizon=horizon,
        critical_capabilities=frozenset(critical), important_capabilities=frozenset(important),
        optional_capabilities=frozenset(extra), minimum_factor_coverage=Decimal(str(coverage)),
        signal_policy=signal, confidence_policy=ConfidencePolicy(), missing_data_policy=missing,
        key_metric_priority=priority, strength_rules=strengths, risk_rules=risks,
        interpretation_rules=interpretations, limitations=limitations,
        known_missing_dimensions=known_missing_dimensions,
    )


# ==============================================================================
# Pilot Profiles (Phase B4)
# ==============================================================================

PILOT_PROFILES = {
    "zhang_kun": _profile(
        profile_id="zhang_kun", display_name="张坤", description="长期经营质量与现金创造策略原型",
        version="v2",
        core=("profitability_quality", "cash_conversion", "balance_sheet_safety", "margin_trend"),
        supporting=("valuation_level", "valuation_percentile", "revenue_cagr_3y"),
        optional=("momentum_6m", "drawdown_6m"),
        weights=dict(profitability_quality=4, cash_conversion=4, balance_sheet_safety=3,
                     margin_trend=3, valuation_level=2, valuation_percentile=1,
                     revenue_cagr_3y=1, momentum_6m=0.25, drawdown_6m=0.25),
        horizon="3–5 years", critical=(C.INCOME_STATEMENT, C.CASH_FLOW_STATEMENT, C.BALANCE_SHEET),
        important=(C.VALUATION_HISTORY,), extra=(C.PRICE_ADJUSTED,), coverage="0.60",
        signal=SignalPolicy(Decimal("0.25"), Decimal("-0.25"), "long_term_quality"),
        missing=MissingDataPolicy(55, 65, specific_limitations=("多年盈利持续性和资本效率尚无独立可靠因子",)),
        priority=("profitability_quality", "cash_conversion", "balance_sheet_safety", "margin_trend",
                  "valuation_level", "revenue_cagr_3y"),
        strengths={"profitability_quality": "盈利质量支持长期经营判断", "cash_conversion": "利润具有现金流支撑",
                   "balance_sheet_safety": "资产负债状况稳健", "valuation_level": "当前估值提供一定安全边际"},
        risks={"profitability_quality": "盈利质量转弱", "cash_conversion": "利润现金转化不足",
               "balance_sheet_safety": "资产负债压力影响长期持有", "margin_trend": "利润率持续承压",
               "valuation_level": "核心经营质量良好，但估值偏高压缩预期回报",
               "momentum_6m": "价格走弱，仅作低权重观察"},
        interpretations={"momentum_6m": ("价格改善仅作辅助观察", "价格走弱不单独推翻长期质量判断", "短期价格不主导判断"),
                         "valuation_percentile": ("历史估值位置提供一定安全边际", "估值位置偏高", "估值位置中性")},
        limitations=("该模型仅为公开理念启发的项目策略原型，未衡量真实竞争护城河",),
        known_missing_dimensions=("商业模式护城河", "管理层资本配置质量"),
    ),
    "feng_liu": _profile(
        profile_id="feng_liu", display_name="冯柳", description="低估值和价格压制代理加经营改善策略原型",
        core=(PROXY_ID, "growth_acceleration", "margin_trend"),
        supporting=("earnings_growth_yoy", "valuation_level", "valuation_percentile"),
        optional=("momentum_6m", "drawdown_6m"),
        weights={PROXY_ID: 4, "growth_acceleration": 4, "margin_trend": 3,
                 "earnings_growth_yoy": 2, "valuation_level": 1,
                 "valuation_percentile": 1, "momentum_6m": 0.5, "drawdown_6m": 0.5},
        horizon="1–3 years", critical=(C.INCOME_STATEMENT, C.VALUATION_HISTORY, C.PRICE_ADJUSTED),
        important=(C.BALANCE_SHEET,), extra=(), coverage="0.55",
        signal=SignalPolicy(Decimal("0.22"), Decimal("-0.22"), "proxy_plus_improvement"),
        missing=MissingDataPolicy(45, 50, proxy_cap=60,
                                  specific_limitations=("没有真实市场预期、分析师预测和完整催化剂数据",)),
        priority=(PROXY_ID, "growth_acceleration", "margin_trend", "earnings_growth_yoy",
                  "valuation_percentile", "valuation_level"),
        strengths={PROXY_ID: "估值与价格位置具备低预期代理特征",
                   "growth_acceleration": "营收增长正在改善", "margin_trend": "利润率改善得到确认"},
        risks={"growth_acceleration": "营收增速继续恶化", "margin_trend": "利润率继续恶化",
               "earnings_growth_yoy": "盈利增长仍弱", PROXY_ID: "尚无明显估值与价格压制代理证据"},
        interpretations={"momentum_6m": ("价格回升削弱价格压制代理", "价格走弱可增强价格压制代理，但不证明经营改善", "价格变化仅作代理输入"),
                         "valuation_percentile": ("历史低估值位置增强代理条件", "历史估值位置偏高", "历史估值位置中性")},
        limitations=("LOW_EXPECTATION_PROXY 仅反映估值与价格压制，不能证明真实市场预期低",),
        known_missing_dimensions=("真实市场预期", "分析师一致预期", "业绩预测修正趋势"),
    ),
    "fu_pengbo": _profile(
        profile_id="fu_pengbo", display_name="傅鹏博", description="成长持续性、经营质量与估值匹配策略原型",
        core=("revenue_growth_yoy", "earnings_growth_yoy", "growth_acceleration",
              "profitability_quality", "cash_conversion"),
        supporting=("valuation_level", "valuation_percentile", "margin_trend", "balance_sheet_safety"),
        optional=("momentum_6m",),
        weights=dict(revenue_growth_yoy=4, earnings_growth_yoy=4, growth_acceleration=3,
                     profitability_quality=3, cash_conversion=2, valuation_level=2,
                     valuation_percentile=1, margin_trend=2, balance_sheet_safety=1, momentum_6m=0.5),
        horizon="2–4 years", critical=(C.INCOME_STATEMENT, C.CASH_FLOW_STATEMENT),
        important=(C.VALUATION_HISTORY, C.BALANCE_SHEET), extra=(C.PRICE_ADJUSTED,), coverage="0.60",
        signal=SignalPolicy(Decimal("0.28"), Decimal("-0.25"), "growth_quality"),
        missing=MissingDataPolicy(50, 60, specific_limitations=("增速加速度历史不足会降低成长持续性判断的可信度",)),
        priority=("revenue_growth_yoy", "earnings_growth_yoy", "growth_acceleration",
                  "profitability_quality", "cash_conversion", "valuation_level"),
        strengths={"revenue_growth_yoy": "营收成长为策略提供支撑", "earnings_growth_yoy": "盈利成长与营收相互印证",
                   "growth_acceleration": "成长速度改善", "profitability_quality": "盈利质量支持成长"},
        risks={"revenue_growth_yoy": "营收成长转弱", "earnings_growth_yoy": "盈利成长转弱",
               "growth_acceleration": "成长明显减速", "cash_conversion": "成长缺少现金流支撑",
               "valuation_level": "当前估值对成长兑现要求较高", "momentum_6m": "价格趋势对成长判断形成辅助负面确认"},
        interpretations={"momentum_6m": ("价格趋势辅助确认成长", "价格趋势对成长构成辅助负面确认", "短期价格仅作辅助"),
                         "valuation_percentile": ("估值位置降低成长兑现压力", "估值位置提高成长兑现要求", "估值位置中性")},
        limitations=("成长持续性仅由现有财报历史衡量，未使用分析师预测",),
        known_missing_dimensions=("分析师远期盈利预测", "产业技术迭代跟踪"),
    ),
}


# ==============================================================================
# Expanded Shadow Profiles (Phase B5)
# ==============================================================================

EXPANDED_PROFILES = {
    "duan_yongping": _profile(
        profile_id="duan_yongping", display_name="段永平", description="商业模式护城河与现金流创造策略原型",
        version="v1",
        core=("profitability_quality", "cash_conversion", "balance_sheet_safety", "margin_trend"),
        supporting=("valuation_level", "valuation_percentile"),
        optional=("revenue_cagr_3y",),
        weights=dict(profitability_quality=4, cash_conversion=4, balance_sheet_safety=3,
                     margin_trend=3, valuation_level=2, valuation_percentile=1,
                     revenue_cagr_3y=1),
        horizon="5–10 years", critical=(C.INCOME_STATEMENT, C.CASH_FLOW_STATEMENT, C.BALANCE_SHEET),
        important=(C.VALUATION_HISTORY,), extra=(), coverage="0.60",
        signal=SignalPolicy(Decimal("0.25"), Decimal("-0.25"), "long_term_quality"),
        missing=MissingDataPolicy(55, 65, specific_limitations=("商业模式护城河与再投资资本回报率尚无独立量化数据",)),
        priority=("profitability_quality", "cash_conversion", "balance_sheet_safety", "margin_trend", "valuation_level"),
        strengths={"profitability_quality": "长期高资本回报展现优秀商业模式",
                   "cash_conversion": "利润全部转化为充沛自由现金流",
                   "balance_sheet_safety": "资产负债极其健康，无财务偿债压力",
                   "valuation_level": "当前价格具备合理安全边际"},
        risks={"profitability_quality": "长期回报率转弱，商业模式可能面临挑战",
               "cash_conversion": "利润现金流转化不足，盈利质量存疑",
               "balance_sheet_safety": "资产负债杠杆过高，违背稳健经营原则",
               "margin_trend": "利润率持续走低，需警惕竞争壁垒受损",
               "valuation_level": "好生意但价格过高，压缩长期复合回报"},
        interpretations={"revenue_cagr_3y": ("中长期复合增长印证商业壁垒持续创造价值", "中长期复合增长放缓至低速通道", "长期复合增长平稳"),
                         "valuation_percentile": ("历史极低估值提供厚实安全边际", "历史高估值削弱长期持有确定性", "历史估值居中")},
        limitations=("该模型仅为公开理念启发的项目策略原型，未量化商业模式护城河与企业家精神",),
        known_missing_dimensions=("商业模式护城河", "长期再投资资本回报", "管理层资本配置", "品牌与特许经营壁垒"),
    ),
    "deng_xiaofeng": _profile(
        profile_id="deng_xiaofeng", display_name="邓晓峰", description="逆向价值评估与基本面修复策略原型",
        version="v1",
        core=("valuation_level", "valuation_percentile", "earnings_growth_yoy", "margin_trend"),
        supporting=("profitability_quality", "balance_sheet_safety"),
        optional=("momentum_6m", "drawdown_6m"),
        weights=dict(valuation_level=4, valuation_percentile=3, earnings_growth_yoy=3, margin_trend=3,
                     profitability_quality=2, balance_sheet_safety=2, momentum_6m=0.5, drawdown_6m=0.5),
        horizon="2–4 years", critical=(C.VALUATION_HISTORY, C.INCOME_STATEMENT),
        important=(C.BALANCE_SHEET, C.PRICE_ADJUSTED), extra=(), coverage="0.55",
        signal=SignalPolicy(Decimal("0.24"), Decimal("-0.24"), "value_turnaround"),
        missing=MissingDataPolicy(50, 55, specific_limitations=("行业周期位置与大宗商品价格敏感度尚无独立因子",)),
        priority=("valuation_level", "valuation_percentile", "earnings_growth_yoy", "margin_trend", "profitability_quality", "balance_sheet_safety"),
        strengths={"valuation_level": "估值具备显著折价，赔率对逆向布局有利",
                   "valuation_percentile": "处于历史极低估值分位，向下空间有限",
                   "earnings_growth_yoy": "盈利拐点初现，业绩进入修复通道",
                   "margin_trend": "毛利率与净利率环比改善确认拐点"},
        risks={"earnings_growth_yoy": "盈利修复尚未得到报表数据验证",
               "margin_trend": "利润率持续下滑，需防范价值陷阱",
               "balance_sheet_safety": "周期低谷期债务偿付压力增加",
               "valuation_level": "估值未见折价优势，逆向安全垫不足"},
        interpretations={"drawdown_6m": ("显著价格回撤提供逆向布局赔率空间", "持续深幅回撤需警惕资产减值风险", "价格回撤在常态区间"),
                         "momentum_6m": ("右侧量价走强初步确认反转", "左侧下跌加深低估值，但需基本面拐点印证", "价格动量中性")},
        limitations=("该模型属于估值与基本面修复近似，未包含真实产业周期与大宗商品敏感度数据",),
        known_missing_dimensions=("行业周期位置", "大宗商品价格敏感度", "产业景气阶段", "产能去化程度"),
    ),
    "zhu_shaoxing": _profile(
        profile_id="zhu_shaoxing", display_name="朱少醒", description="均衡质量、持续成长与合理估值策略原型",
        version="v1",
        core=("profitability_quality", "revenue_growth_yoy", "cash_conversion"),
        supporting=("valuation_level", "balance_sheet_safety", "margin_trend", "growth_acceleration"),
        optional=("momentum_6m", "drawdown_6m"),
        weights=dict(profitability_quality=4, revenue_growth_yoy=3, cash_conversion=3,
                     valuation_level=2, balance_sheet_safety=2, margin_trend=2, growth_acceleration=2,
                     momentum_6m=0.5, drawdown_6m=0.5),
        horizon="3–5 years", critical=(C.INCOME_STATEMENT, C.CASH_FLOW_STATEMENT),
        important=(C.VALUATION_HISTORY, C.BALANCE_SHEET), extra=(C.PRICE_ADJUSTED,), coverage="0.60",
        signal=SignalPolicy(Decimal("0.25"), Decimal("-0.25"), "balanced_quality_growth"),
        missing=MissingDataPolicy(50, 60, specific_limitations=("管理层资本配置能力与长期竞争优势无量化数据",)),
        priority=("profitability_quality", "revenue_growth_yoy", "cash_conversion", "valuation_level", "balance_sheet_safety"),
        strengths={"profitability_quality": "ROE 与核心盈利质量稳健优秀",
                   "revenue_growth_yoy": "营收持续健康增长，体现业务成长动能",
                   "cash_conversion": "成长具有扎实的经营性现金流支撑",
                   "valuation_level": "估值处于合理区间，收益风险比均衡"},
        risks={"profitability_quality": "ROE 或核心盈利质量明显弱化",
               "cash_conversion": "营收扩张未带来相匹配的真金白银现金流",
               "balance_sheet_safety": "财务杠杆上升，稳健性削弱",
               "valuation_level": "估值过度透支未来成长预期"},
        interpretations={"growth_acceleration": ("成长呈现边际加速，强化长期竞争壁垒", "成长速度放缓，关注是否步入成熟期", "增速平稳"),
                         "margin_trend": ("利润率走阔印证产业链议价能力", "利润率承压侵蚀盈利质量", "利润率平稳"),
                         "momentum_6m": ("价格趋势健康印证基本面", "价格走弱仅作辅助观察", "价格趋势中性")},
        limitations=("该模型为成长与质量均衡策略原型，未包含管理层定性评估与长期资本配置能力",),
        known_missing_dimensions=("管理层资本配置质量", "长期竞争优势", "企业家精神与公司治理"),
    ),
    "liu_yanchun": _profile(
        profile_id="liu_yanchun", display_name="刘彦春", description="大消费成长质量与确定性回报策略原型",
        version="v1",
        core=("profitability_quality", "revenue_growth_yoy", "earnings_growth_yoy", "cash_conversion"),
        supporting=("margin_trend", "revenue_cagr_3y", "valuation_level"),
        optional=("balance_sheet_safety", "momentum_6m"),
        weights=dict(profitability_quality=4, revenue_growth_yoy=3, earnings_growth_yoy=3, cash_conversion=3,
                     margin_trend=2, revenue_cagr_3y=2, valuation_level=2,
                     balance_sheet_safety=1, momentum_6m=0.5),
        horizon="3–5 years", critical=(C.INCOME_STATEMENT, C.CASH_FLOW_STATEMENT),
        important=(C.VALUATION_HISTORY,), extra=(C.PRICE_ADJUSTED,), coverage="0.60",
        signal=SignalPolicy(Decimal("0.26"), Decimal("-0.25"), "consumer_quality_growth"),
        missing=MissingDataPolicy(50, 60, specific_limitations=("品牌定价权与渠道动销数据尚无独立因子",)),
        priority=("profitability_quality", "revenue_growth_yoy", "earnings_growth_yoy", "cash_conversion", "margin_trend"),
        strengths={"profitability_quality": "高净利率与高 ROE 展现消费品优质商业属性",
                   "revenue_growth_yoy": "营收稳健扩张印证品牌消费需求强劲",
                   "cash_conversion": "先款后货与强现金流提供极高盈利确定性",
                   "margin_trend": "毛利率持续走阔展现出色的产品定价权"},
        risks={"revenue_growth_yoy": "营收负增长警惕终端消费需求萎缩或渠道承压",
               "earnings_growth_yoy": "利润增长失速，消费盈利拐点需谨慎评估",
               "profitability_quality": "净利率大幅下滑，消费溢价能力削弱",
               "valuation_level": "估值处于历史偏高水位，要求极高成长兑现"},
        interpretations={"revenue_cagr_3y": ("三年复合高增长展现消费长跑能力", "中长期成长放缓至低速通道", "复合增速中规中矩"),
                         "momentum_6m": ("价格趋势顺应基本面向上", "短期价格承压不改长期消费确定性", "价格表现平稳")},
        limitations=("该模型使用财务质量代理消费品特征，不衡量真实渠道库存、动销与品牌定价权",),
        known_missing_dimensions=("品牌定价权", "渠道库存与动销", "终端消费者粘性", "复购与品类扩张"),
    ),
    "xie_zhiyu": _profile(
        profile_id="xie_zhiyu", display_name="谢治宇", description="成长与估值性价比动态匹配策略原型",
        version="v1",
        core=("growth_acceleration", "revenue_growth_yoy", "earnings_growth_yoy", "valuation_level"),
        supporting=("profitability_quality", "valuation_percentile", "balance_sheet_safety"),
        optional=("momentum_6m",),
        weights=dict(growth_acceleration=4, revenue_growth_yoy=3, earnings_growth_yoy=3, valuation_level=3,
                     profitability_quality=2, valuation_percentile=2, balance_sheet_safety=1,
                     momentum_6m=0.5),
        horizon="2–4 years", critical=(C.INCOME_STATEMENT, C.VALUATION_HISTORY),
        important=(C.BALANCE_SHEET,), extra=(C.PRICE_ADJUSTED,), coverage="0.60",
        signal=SignalPolicy(Decimal("0.24"), Decimal("-0.24"), "growth_valuation_balance"),
        missing=MissingDataPolicy(50, 55, specific_limitations=("远期盈利预测与动态 PEG 指标暂无独立可靠因子",)),
        priority=("growth_acceleration", "valuation_level", "revenue_growth_yoy", "earnings_growth_yoy", "profitability_quality"),
        strengths={"growth_acceleration": "成长边际加速，业务扩张斜率提升",
                   "valuation_level": "当前估值与成长性匹配度高，具备良好性价比",
                   "earnings_growth_yoy": "盈利高增长提供坚实估值消化能力",
                   "profitability_quality": "盈利质量良好，成长并非低质扩张"},
        risks={"growth_acceleration": "成长显著减速，估值溢价可能迅速回落",
               "valuation_level": "成长增速难以匹配当前过高估值要求",
               "earnings_growth_yoy": "利润增长停滞，性价比失衡",
               "balance_sheet_safety": "过度依赖杠杆扩张财务风险加大"},
        interpretations={"valuation_percentile": ("历史低估值大幅增厚投资性价比", "历史高估值削弱安全边际", "估值分位数居中"),
                         "momentum_6m": ("量价配合趋势向上", "价格走弱加大安全边际考量", "趋势中性")},
        limitations=("该模型使用历史财报近似估值与成长匹配，不包含分析师远期预测与动态 PEG 跟踪",),
        known_missing_dimensions=("PEG 动态指标", "行业相对估值", "远期盈利预测", "产业技术演进判断"),
    ),
    "dong_chengfei": _profile(
        profile_id="dong_chengfei", display_name="董承非", description="估值纪律、财务稳健与防守反击策略原型",
        version="v1",
        core=("balance_sheet_safety", "valuation_level", "valuation_percentile", "cash_conversion"),
        supporting=("profitability_quality", "drawdown_6m"),
        optional=("volatility_3m", "momentum_6m"),
        weights=dict(balance_sheet_safety=4, valuation_level=4, valuation_percentile=3, cash_conversion=3,
                     profitability_quality=2, drawdown_6m=2,
                     volatility_3m=0.5, momentum_6m=0.5),
        horizon="2–4 years", critical=(C.BALANCE_SHEET, C.VALUATION_HISTORY, C.CASH_FLOW_STATEMENT),
        important=(C.INCOME_STATEMENT, C.PRICE_ADJUSTED), extra=(), coverage="0.60",
        signal=SignalPolicy(Decimal("0.24"), Decimal("-0.24"), "value_discipline_safety"),
        missing=MissingDataPolicy(50, 60, specific_limitations=("完整市现率与股息持续性指标尚无独立量化数据",)),
        priority=("balance_sheet_safety", "valuation_level", "valuation_percentile", "cash_conversion", "drawdown_6m"),
        strengths={"balance_sheet_safety": "资产负债表极其稳固，抗风险防守能力突出",
                   "valuation_level": "估值处于保守防御水平，具备足够下行保护",
                   "valuation_percentile": "历史估值百分位极低，赔率对投资有利",
                   "cash_conversion": "真金白银自由现金流提供安全底线"},
        risks={"balance_sheet_safety": "资产负债表恶化，有息负债承压违背防御原则",
               "valuation_level": "缺乏估值保护，价格处于透支区间",
               "cash_conversion": "现金转化能力薄弱，财务健康度受损",
               "drawdown_6m": "价格持续破位且缺乏基本面托底"},
        interpretations={"drawdown_6m": ("深幅回撤后具备较高下行安全边际", "回撤剧烈需警惕资产减值与基本面恶化", "回撤在正常波动范围"),
                         "volatility_3m": ("波动率低体现防御特征", "波动率加剧需关注潜在非基本面冲击", "波动平稳")},
        limitations=("该模型强调财务纪律与下行保护，未衡量大股东质押、表外负债及股息连续性",),
        known_missing_dimensions=("FCF multiple / P-CF", "股息持续性与分红意愿", "资产重置成本与清算价值", "下行期压力测试数据"),
    ),
    "chen_guangming": _profile(
        profile_id="chen_guangming", display_name="陈光明", description="优质企业深度价值与现金流回报策略原型",
        version="v1",
        core=("profitability_quality", "cash_conversion", "balance_sheet_safety", "valuation_level"),
        supporting=("valuation_percentile", "margin_trend", "revenue_cagr_3y"),
        optional=("drawdown_6m",),
        weights=dict(profitability_quality=4, cash_conversion=4, balance_sheet_safety=3, valuation_level=3,
                     valuation_percentile=2, margin_trend=2, revenue_cagr_3y=1,
                     drawdown_6m=0.5),
        horizon="3–5 years", critical=(C.INCOME_STATEMENT, C.CASH_FLOW_STATEMENT, C.BALANCE_SHEET, C.VALUATION_HISTORY),
        important=(C.PRICE_ADJUSTED,), extra=(), coverage="0.65",
        signal=SignalPolicy(Decimal("0.25"), Decimal("-0.25"), "quality_value_cash"),
        missing=MissingDataPolicy(55, 65, specific_limitations=("股东盈余精确模型与公司治理治理水平尚无独立数据",)),
        priority=("profitability_quality", "cash_conversion", "valuation_level", "balance_sheet_safety", "valuation_percentile"),
        strengths={"profitability_quality": "长期高资本回报展现卓越商业质地",
                   "cash_conversion": "经营现金流与自由现金流充沛，高质量兑现利润",
                   "valuation_level": "估值处于合理或低估区间，提供充足安全边际",
                   "balance_sheet_safety": "资产负债表干净健康，运营风险低"},
        risks={"cash_conversion": "账面利润未能转化为真金白银现金流",
               "profitability_quality": "核心盈利回报率走弱，竞争优势衰退",
               "valuation_level": "估值过高削弱长期复合收益率预期",
               "balance_sheet_safety": "资产负债杠杆升高，稳健性削弱"},
        interpretations={"valuation_percentile": ("历史低估值显著提升长期投资复合回报", "历史高估值带来均值回归风险", "估值位于中性区间"),
                         "revenue_cagr_3y": ("三年稳健复合增长印证持续创造价值", "增长放缓需重新审视护城河", "中长期成长平稳")},
        limitations=("该模型为质量与深度价值策略原型，未量化公司治理结构与真实股东盈余再投资回报",),
        known_missing_dimensions=("股东盈余精确模型", "公司治理评分", "长期资本配置效率", "大股东与中小股东利益一致性"),
    ),
}

# Unified registry of all 10 shadow-enabled profiles
SHADOW_PROFILES = {**PILOT_PROFILES, **EXPANDED_PROFILES}

ZHANG_KUN_V1 = _profile(
    profile_id="zhang_kun", display_name="张坤", description="长期经营质量与现金创造策略原型",
    version="v1",
    core=("profitability_quality", "cash_conversion", "balance_sheet_safety", "margin_trend"),
    supporting=("valuation_level", "valuation_percentile", "revenue_cagr_3y"),
    optional=("momentum_6m", "drawdown_6m"),
    weights=dict(profitability_quality=4, cash_conversion=4, balance_sheet_safety=3,
                 margin_trend=3, valuation_level=2, valuation_percentile=1,
                 revenue_cagr_3y=1, momentum_6m=0.25, drawdown_6m=0.25),
    horizon="3–5 years", critical=(C.INCOME_STATEMENT, C.CASH_FLOW_STATEMENT, C.BALANCE_SHEET),
    important=(C.VALUATION_HISTORY,), extra=(C.PRICE_ADJUSTED,), coverage="0.60",
    signal=SignalPolicy(Decimal("0.25"), Decimal("-0.25"), "long_term_quality"),
    missing=MissingDataPolicy(55, 65, specific_limitations=("多年盈利持续性和资本效率尚无独立可靠因子",)),
    priority=("profitability_quality", "cash_conversion", "balance_sheet_safety", "margin_trend",
              "valuation_level", "revenue_cagr_3y"),
    strengths={"profitability_quality": "盈利质量支持长期经营判断", "cash_conversion": "利润具有现金流支撑",
               "balance_sheet_safety": "资产负债状况稳健", "valuation_level": "当前估值提供一定安全边际"},
    risks={"profitability_quality": "盈利质量转弱", "cash_conversion": "利润现金转化不足",
           "balance_sheet_safety": "资产负债压力影响长期持有", "margin_trend": "利润率持续承压",
           "momentum_6m": "价格走弱，仅作低权重观察"},
    interpretations={"momentum_6m": ("价格改善仅作辅助观察", "价格走弱不单独推翻长期质量判断", "短期价格不主导判断"),
                     "valuation_percentile": ("历史估值位置提供一定安全边际", "估值位置偏高", "估值位置中性")},
    limitations=("该模型仅为公开理念启发的项目策略原型，未衡量真实竞争护城河",),
    known_missing_dimensions=("商业模式护城河", "管理层资本配置质量"),
)


def get_profile(profile_id: str, version: str = "latest") -> InvestorProfile:
    """Retrieve profile by id and version from all registered shadow profiles."""
    if profile_id == "zhang_kun" and version == "v1":
        return ZHANG_KUN_V1
    if profile_id in SHADOW_PROFILES:
        return SHADOW_PROFILES[profile_id]
    raise KeyError(f"Unknown shadow profile_id: {profile_id}")


def get_pilot_profile(profile_id: str, version: str = "latest") -> InvestorProfile:
    """Backward compatibility alias."""
    return get_profile(profile_id, version)
