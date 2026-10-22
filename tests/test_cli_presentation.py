"""CLI presentation stays independent of investment calculations."""

from io import StringIO

from rich.console import Console
from rich.cells import cell_len

from src.cli.presentation import build_analysis_result, format_metric
from src.cli.renderer import render_analysis


def sample_result():
    return {
        "decisions": {"600519": {
            "action": "buy", "quantity": 13, "confidence": 75,
            "reasoning": "基本面看多，技术面中性；控制仓位。",
        }},
        "analyst_signals": {
            "technical_analyst_agent": {"600519": {
                "signal": "neutral", "confidence": 0,
                "reasoning": {
                    "trend_following": {"signal": "bullish", "metrics": {"trend_strength": 0.332451}},
                    "momentum": {"signal": "bearish", "metrics": {"momentum_1m": -0.046006}},
                },
            }},
        },
    }


def test_percentage_formatting_and_original_decision_unchanged():
    raw = sample_result()
    result = build_analysis_result(raw, {"Technical Analyst": "Done"}, {"600519": "贵州茅台"})
    agent = result.stocks[0].agents[0]

    assert format_metric("trend_strength", 0.332451) == "33.25%"
    assert format_metric("momentum_1m", -0.046006) == "-4.60%"
    assert "趋势强度：33.25%" in agent.key_metrics
    assert "近 1 个月动量：-4.60%" in agent.key_metrics
    assert agent.strengths == ["趋势"]
    assert agent.risks == ["动量"]
    assert raw["decisions"]["600519"]["quantity"] == result.stocks[0].quantity == 13
    assert result.stocks[0].stock_name == "贵州茅台"


def test_rich_cards_wrap_cleanly_at_common_terminal_widths():
    result = build_analysis_result(sample_result(), {"Technical Analyst": "Done"})
    for width in (80, 120, 160):
        stream = StringIO()
        render_analysis(result, Console(file=stream, width=width, force_terminal=False, color_system=None))
        output = stream.getvalue()
        assert "AI Hedge Fund" in output
        assert "基本面看多" in output
        assert "趋势强度" in output
        assert "33.25%" in output
        assert "-4.60%" in output
        assert "login success" not in output
        assert "+---" not in output
        assert all(cell_len(line) <= width for line in output.splitlines())
        top = [cell_len(line) for line in output.splitlines() if line.startswith("╭")]
        bottom = [cell_len(line) for line in output.splitlines() if line.startswith("╰")]
        assert top == bottom


def test_normal_runtime_hides_provider_prints_and_warnings(capsys):
    import warnings
    from src.cli.logging import quiet_runtime

    with quiet_runtime(False):
        print("login success!")
        warnings.warn("DataFrame warning", UserWarning)
    captured = capsys.readouterr()
    assert "login success" not in captured.out
    assert "DataFrame warning" not in captured.err

    with quiet_runtime(True):
        print("login success!")
    assert "login success" in capsys.readouterr().out


def test_recoverable_source_error_becomes_a_short_user_message():
    raw = sample_result()
    raw["analyst_signals"]["technical_analyst_agent"]["600519"]["reasoning"] = (
        "已有部分指标。 数据获取异常：financial metrics: BaoStock timeout；关键指标不足，保持中性。"
    )
    result = build_analysis_result(raw)
    explanation = result.stocks[0].agents[0].reasoning
    assert "部分数据暂不可用" in explanation
    assert "关键指标不足" in explanation
    assert "BaoStock" not in explanation
    assert "timeout" not in explanation


def test_section_without_signal_does_not_invent_neutral_judgement():
    raw = sample_result()
    raw["analyst_signals"]["technical_analyst_agent"]["600519"] = {
        "signal": "bullish", "confidence": 62,
        "reasoning": {"historical_growth": {"score": 0.332451, "note": "增长稳定"}},
    }
    result = build_analysis_result(raw)
    agent = result.stocks[0].agents[0]
    assert agent.reasoning.startswith("总体判断：看多")
    assert "中性" not in agent.reasoning
    assert "增长稳定" in agent.key_metrics[1]


def test_liu_yanchun_structured_card_and_no_unprovided_placeholder():
    raw = {
        "decisions": {"600519": {"action": "buy", "quantity": 10, "confidence": 70, "reasoning": "看好核心资产。"}},
        "analyst_signals": {
            "liu_yanchun_agent": {"600519": {
                "signal": "bullish",
                "confidence": 41.7,
                "key_metrics": {
                    "roe": {"label": "ROE", "value": 0.332451, "format": "percent"},
                    "net_margin": {"label": "净利率", "value": 0.478595, "format": "percent"},
                    "fcf_yield": {"label": "自由现金流收益率", "value": 0.075487, "format": "percent"},
                    "revenue_growth": {"label": "营收增长", "value": -0.046006, "format": "percent"},
                    "earnings_growth": {"label": "盈利增长", "value": -0.094529, "format": "percent"},
                    "six_month_return": {"label": "六个月回报", "value": -0.128873, "format": "percent"},
                },
                "strengths": ["盈利质量较强", "自由现金流表现良好", "资产负债表稳健"],
                "risks": ["盈利增长承压", "当前估值吸引力有限", "近期价格动量偏弱"],
                "reasoning": "刘彦春理念启发的项目策略原型（非本人观点）。贵州茅台展现高ROE与正FCF。",
            }},
        },
    }
    result = build_analysis_result(raw, {"刘彦春": "Done"}, {"600519": "贵州茅台"})
    agent = result.stocks[0].agents[0]

    assert agent.name == "刘彦春"
    assert agent.signal == "bullish"
    assert agent.confidence == 41.7
    assert len(agent.key_metrics) == 6
    assert agent.strengths == ["盈利质量较强", "自由现金流表现良好", "资产负债表稳健"]
    assert agent.risks == ["盈利增长承压", "当前估值吸引力有限", "近期价格动量偏弱"]

    for width in (80, 120, 160):
        stream = StringIO()
        render_analysis(result, Console(file=stream, width=width, force_terminal=False, color_system=None))
        output = stream.getvalue()
        assert "未单独提供" not in output
        assert "ROE" in output
        assert "33.25%" in output
        assert "净利率" in output
        assert "47.86%" in output
        assert "自由现金流收益率" in output
        assert "7.55%" in output
        assert "营收增长" in output
        assert "-4.60%" in output
        assert "盈利增长" in output
        assert "-9.45%" in output
        assert "六个月回报" in output
        assert "-12.89%" in output
        assert "盈利质量较强" in output
        assert "盈利增长承压" in output
        assert "综合分析" in output
        assert all(cell_len(line) <= width for line in output.splitlines())


def test_empty_metrics_and_empty_strengths_risks_hide_sections():
    raw = {
        "decisions": {"600519": {"action": "hold", "quantity": 0, "confidence": 0, "reasoning": ""}},
        "analyst_signals": {
            "liu_yanchun_agent": {"600519": {
                "signal": "neutral",
                "confidence": 0.0,
                "key_metrics": {},
                "strengths": [],
                "risks": [],
                "reasoning": "暂无足够数据。",
            }},
        },
    }
    result = build_analysis_result(raw, {"刘彦春": "Done"}, {"600519": "贵州茅台"})
    stream = StringIO()
    render_analysis(result, Console(file=stream, width=80, force_terminal=False, color_system=None))
    output = stream.getvalue()

    assert "未单独提供" not in output
    assert "关键指标" not in output
    assert "优势" not in output
    assert "风险" not in output
    assert "综合分析" in output
    assert "暂无足够数据" in output


def test_fu_pengbo_and_duan_yongping_cards_render_cleanly():
    raw = {
        "decisions": {"600519": {"action": "buy", "quantity": 10, "confidence": 65, "reasoning": "加仓"}},
        "analyst_signals": {
            "fu_pengbo_agent": {"600519": {
                "signal": "bullish",
                "confidence": 55.0,
                "key_metrics": {
                    "roe": {"label": "ROE", "value": 0.383556, "format": "percent"},
                    "net_margin": {"label": "净利率", "value": 0.502655, "format": "percent"},
                    "fcf_yield": {"label": "自由现金流收益率", "value": 0.038891, "format": "percent"},
                    "revenue_growth": {"label": "营收增长", "value": 0.176317, "format": "percent"},
                    "earnings_growth": {"label": "盈利增长", "value": 0.167556, "format": "percent"},
                    "six_month_return": {"label": "六个月回报", "value": -0.086639, "format": "percent"},
                    "pe": {"label": "市盈率", "value": 20.03677, "format": "ratio"},
                    "pb": {"label": "市净率", "value": 7.550987, "format": "ratio"},
                },
                "strengths": ["营收增长良好", "盈利增长强劲", "盈利质量较强"],
                "risks": ["当前估值吸引力有限"],
                "reasoning": "傅鹏博策略关注成长与经营质量，茅台维持稳健增长。",
            }},
            "duan_yongping_agent": {"600519": {
                "signal": "bullish",
                "confidence": 60.0,
                "key_metrics": {
                    "roe": {"label": "ROE", "value": 0.383556, "format": "percent"},
                    "net_margin": {"label": "净利率", "value": 0.502655, "format": "percent"},
                    "fcf_yield": {"label": "自由现金流收益率", "value": 0.038891, "format": "percent"},
                    "revenue_growth": {"label": "营收增长", "value": 0.176317, "format": "percent"},
                    "earnings_growth": {"label": "盈利增长", "value": 0.167556, "format": "percent"},
                    "six_month_return": {"label": "六个月回报", "value": -0.086639, "format": "percent"},
                    "pe": {"label": "市盈率", "value": 20.03677, "format": "ratio"},
                    "pb": {"label": "市净率", "value": 7.550987, "format": "ratio"},
                    "debt_to_equity": {"label": "资产负债率", "value": 0.000276, "format": "percent"},
                },
                "strengths": ["盈利质量较强", "资产负债表稳健"],
                "risks": ["当前估值吸引力有限"],
                "reasoning": "段永平策略关注长期商业模式与资产负债表安全。",
            }},
        },
    }
    result = build_analysis_result(raw, {"傅鹏博": "Done", "段永平": "Done"}, {"600519": "贵州茅台"})
    assert len(result.stocks[0].agents) == 2

    for width in (80, 120, 160):
        stream = StringIO()
        render_analysis(result, Console(file=stream, width=width, force_terminal=False, color_system=None))
        output = stream.getvalue()
        assert "未单独提供" not in output
        assert "傅鹏博" in output
        assert "段永平" in output
        assert "市盈率" in output
        assert "市净率" in output


def test_cli_shadow_mode_banner_and_summary():
    raw = {
        "decisions": {"600519": {"action": "short", "quantity": 15, "confidence": 48.0, "reasoning": "Legacy short"}},
        "analyst_signals": {
            "feng_liu_agent": {"600519": {
                "signal": "bearish",
                "confidence": 48.4,
                "key_metrics": {"pe": {"label": "市盈率", "value": 28.5, "format": "ratio"}},
                "strengths": ["盈利质量较强"],
                "risks": ["当前估值吸引力有限"],
                "reasoning": "Legacy 冯柳看空",
            }},
        },
        "investor_shadow": {
            "feng_liu_agent": {"600519": {
                "legacy": {
                    "signal": "bearish",
                    "confidence": 48.4,
                    "key_metrics": {"pe": {"label": "市盈率", "value": 28.5, "format": "ratio"}},
                    "strengths": ["盈利质量较强"],
                    "risks": ["当前估值吸引力有限"],
                },
                "new": {
                    "signal": "bearish",
                    "confidence": 60.0,
                    "profile_version": "v1",
                    "strategy_score": -0.222,
                    "data_coverage": {
                        "implemented_factor_coverage": 0.857,
                        "strategy_evidence_coverage": 0.720,
                        "core_coverage": 1.0,
                        "supporting_coverage": 0.667,
                    },
                    "factor_contributions": [
                        {
                            "factor_id": "low_expectation_proxy",
                            "role": "core",
                            "score": 0.274,
                            "weight": 4.0,
                            "weighted_contribution": 0.078,
                            "status": "AVAILABLE",
                            "raw_value": 0.274,
                        },
                        {
                            "factor_id": "growth_acceleration",
                            "role": "core",
                            "score": -1.0,
                            "weight": 4.0,
                            "weighted_contribution": -0.286,
                            "status": "AVAILABLE",
                            "raw_value": -0.085,
                        },
                    ],
                    "signal_explanation": {
                        "signal": "bearish",
                        "strategy_score": -0.222,
                        "bullish_threshold": 0.22,
                        "bearish_threshold": -0.22,
                        "policy_style": "proxy_plus_improvement",
                        "gate_id": "low_expectation_proxy_and_operating_improvement",
                        "gate_passed": False,
                        "gate_inputs": {
                            "low_expectation_proxy": 0.274,
                            "operating_improvement_mean": -0.5,
                        },
                        "threshold_relation": "profile_gate_bearish",
                        "reason_code": "operating_evidence_deteriorating",
                    },
                    "signal_reason": "低预期代理成立且经营证据恶化，策略门槛判定 bearish。",
                    "confidence_components": {
                        "coverage_score": 0.857,
                        "evidence_quality": 0.88,
                        "unconstrained_confidence": 75.4,
                        "strategy_evidence_cap": 72.0,
                        "proxy_cap": 60.0,
                        "active_cap_name": "proxy_cap",
                        "active_cap_value": 60.0,
                    },
                    "known_missing_dimensions": ["真实市场预期", "分析师一致预期", "业绩预测修正趋势"],
                    "strengths": ["估值与价格位置具备低预期代理特征"],
                    "risks": ["营收增速继续恶化"],
                },
                "signal_changed": False,
                "confidence_changed": True,
            }},
        },
    }

    result = build_analysis_result(
        raw,
        {"冯柳": "Done"},
        {"600519": "贵州茅台"},
        investor_mode="shadow",
        show_reasoning=False,
    )

    stream = StringIO()
    render_analysis(result, Console(file=stream, width=120, force_terminal=False, color_system=None))
    out = stream.getvalue()

    assert "Research Mode · SHADOW" in out
    assert "Production Decision Uses LEGACY" in out
    assert "生产交易决策" in out
    assert "SHORT" in out
    assert "10 位研究投资人 Legacy vs New 快速对比" in out
    assert "冯柳" in out
    assert "--show-reasoning" in out


def test_cli_shadow_mode_expanded_reasoning_structure():
    raw = {
        "decisions": {"600519": {"action": "short", "quantity": 15, "confidence": 48.0, "reasoning": "Legacy short"}},
        "analyst_signals": {
            "feng_liu_agent": {"600519": {
                "signal": "bearish",
                "confidence": 48.4,
                "key_metrics": {"pe": {"label": "市盈率", "value": 28.5, "format": "ratio"}},
                "strengths": ["盈利质量较强"],
                "risks": ["当前估值吸引力有限"],
                "reasoning": "Legacy 冯柳看空",
            }},
        },
        "investor_shadow": {
            "feng_liu_agent": {"600519": {
                "legacy": {
                    "signal": "bearish",
                    "confidence": 48.4,
                    "key_metrics": {"pe": {"label": "市盈率", "value": 28.5, "format": "ratio"}},
                    "strengths": ["盈利质量较强"],
                    "risks": ["当前估值吸引力有限"],
                },
                "new": {
                    "signal": "bearish",
                    "confidence": 60.0,
                    "profile_version": "v1",
                    "strategy_score": -0.222,
                    "data_coverage": {
                        "implemented_factor_coverage": 0.857,
                        "strategy_evidence_coverage": 0.720,
                        "core_coverage": 1.0,
                        "supporting_coverage": 0.667,
                    },
                    "factor_contributions": [
                        {
                            "factor_id": "low_expectation_proxy",
                            "role": "core",
                            "score": 0.274,
                            "weight": 4.0,
                            "weighted_contribution": 0.078,
                            "status": "AVAILABLE",
                            "raw_value": 0.274,
                        },
                        {
                            "factor_id": "growth_acceleration",
                            "role": "core",
                            "score": -1.0,
                            "weight": 4.0,
                            "weighted_contribution": -0.286,
                            "status": "AVAILABLE",
                            "raw_value": -0.085,
                        },
                    ],
                    "signal_explanation": {
                        "signal": "bearish",
                        "strategy_score": -0.222,
                        "bullish_threshold": 0.22,
                        "bearish_threshold": -0.22,
                        "policy_style": "proxy_plus_improvement",
                        "gate_id": "low_expectation_proxy_and_operating_improvement",
                        "gate_passed": False,
                        "gate_inputs": {
                            "low_expectation_proxy": 0.274,
                            "operating_improvement_mean": -0.5,
                        },
                        "threshold_relation": "profile_gate_bearish",
                        "reason_code": "operating_evidence_deteriorating",
                    },
                    "signal_reason": "低预期代理成立且经营证据恶化，策略门槛判定 bearish。",
                    "confidence_components": {
                        "coverage_score": 0.857,
                        "evidence_quality": 0.88,
                        "unconstrained_confidence": 75.4,
                        "strategy_evidence_cap": 72.0,
                        "proxy_cap": 60.0,
                        "active_cap_name": "proxy_cap",
                        "active_cap_value": 60.0,
                    },
                    "known_missing_dimensions": ["真实市场预期", "分析师一致预期", "业绩预测修正趋势"],
                    "strengths": ["估值与价格位置具备低预期代理特征"],
                    "risks": ["营收增速继续恶化"],
                },
                "signal_changed": False,
                "confidence_changed": True,
            }},
        },
    }

    result = build_analysis_result(
        raw,
        {"冯柳": "Done"},
        {"600519": "贵州茅台"},
        investor_mode="shadow",
        show_reasoning=True,
    )

    stream = StringIO()
    render_analysis(result, Console(file=stream, width=120, force_terminal=False, color_system=None))
    out = stream.getvalue()

    # Section 7: Mode header and Production decision
    assert "Research Mode · SHADOW" in out
    assert "Production Decision Uses LEGACY" in out
    assert "生产交易决策" in out
    assert "SHORT" in out

    # Legacy card
    assert "冯柳 · Legacy" in out
    assert "Legacy Key Metrics" in out

    # New card
    assert "冯柳 v1 · New Research Model" in out
    assert "Strategy Score" in out
    assert "-0.222" in out
    assert "CORE Coverage" in out

    # Section 8: Factors by CORE
    assert "CORE (核心因子)" in out
    assert "低预期代理" in out
    assert "增长加速度" in out

    # Section 9: Signal explanation
    assert "判断逻辑 (Signal Explanation)" in out
    assert "operating_evidence_deteriorating" in out
    assert "低预期代理成立" in out
    assert "经营证据恶化" in out

    # Section 10: Confidence breakdown
    assert "置信度拆解 (Confidence Breakdown)" in out
    assert "Proxy Cap" in out
    assert "不代表上涨概率或胜率" in out

    # Section 11: Known missing dimensions
    assert "已知模型缺失维度" in out
    assert "真实市场预期" in out

    # Section 12: Legacy vs New summary
    assert "Legacy → New 对照摘要" in out
    assert "不代表模型优劣评判" in out
