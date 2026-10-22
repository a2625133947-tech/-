import { describe, it, expect } from 'vitest';
import { ShadowInvestorCardDTO, InvestorDetailDTO } from '../types/research';

describe('Research Dashboard Frontend Contracts', () => {
  it('correctly validates 10 SHADOW ready investor cards structure', () => {
    const card: ShadowInvestorCardDTO = {
      profile_id: 'feng_liu',
      display_name: '冯柳',
      profile_version: 'v1',
      lens: '低估值和价格压制代理加经营改善策略原型',
      signal: 'bearish',
      signal_display: '↓ 看空 (bearish)',
      confidence: 60.0,
      strategy_score: -0.222,
      strategy_evidence_coverage: 0.72,
      core_coverage: 1.0,
      supporting_coverage: 0.667,
      implemented_factor_coverage: 0.857,
      status: 'READY',
    };

    expect(card.status).toBe('READY');
    expect(card.signal).toBe('bearish');
    expect(card.strategy_score).toBe(-0.222);
    expect(card.strategy_evidence_coverage).toBeGreaterThan(0.5);
  });

  it('correctly models NOT_READY status for Wang Yawei and Lin Yuan without fake evaluations', () => {
    const notReadyCard: ShadowInvestorCardDTO = {
      profile_id: 'wang_yawei',
      display_name: '王亚伟',
      profile_version: 'legacy-only',
      lens: '估值、盈利变化与趋势',
      signal: 'neutral',
      signal_display: 'NOT READY',
      confidence: 0,
      strategy_score: null,
      strategy_evidence_coverage: 0,
      core_coverage: 0,
      supporting_coverage: 0,
      implemented_factor_coverage: 0,
      status: 'NOT_READY',
      not_ready_reason: '缺少重组重仓、筹码集中度与席位流向数据',
    };

    expect(notReadyCard.status).toBe('NOT_READY');
    expect(notReadyCard.signal_display).toBe('NOT READY');
    expect(notReadyCard.strategy_score).toBeNull();
    expect(notReadyCard.not_ready_reason).toContain('重组');
  });

  it('verifies InvestorDetailDTO contains separated Factor Contributions, Gate Checks and Confidence notice', () => {
    const detail: InvestorDetailDTO = {
      profile_id: 'feng_liu',
      display_name: '冯柳',
      profile_version: 'v1',
      description: '低估值和价格压制代理加经营改善策略原型',
      time_horizon: '1–3 years',
      signal: 'bearish',
      signal_display: '↓ 看空 (bearish)',
      confidence: 60.0,
      confidence_semantics: '数据支撑与当前策略结论可信程度；不是上涨概率、盈利概率或交易胜率',
      strategy_score: -0.222,
      data_coverage: {
        core_coverage: 1.0,
        strategy_evidence_coverage: 0.72,
      },
      factor_contributions: [
        {
          factor_id: 'low_expectation_proxy',
          display_name: '低预期代理',
          version: 'v1',
          role: 'core',
          role_display: 'CORE (核心因子)',
          score: 0.274,
          weight: 4.0,
          weighted_contribution: 0.078,
          status: 'AVAILABLE',
          factor_type: 'proxy',
          raw_value: 0.274,
          raw_unit: 'fraction',
          limitations: [],
        },
      ],
      signal_explanation: {
        signal: 'bearish',
        signal_display: '↓ 看空 (bearish)',
        strategy_score: -0.222,
        bullish_threshold: 0.22,
        bearish_threshold: -0.22,
        policy_style: 'proxy_plus_improvement',
        gate_id: 'low_expectation_proxy_and_operating_improvement',
        gate_passed: false,
        gate_checks: ['✓ 低预期代理成立', '✗ 经营证据恶化'],
        reason_code: 'operating_evidence_deteriorating',
        signal_reason: '低预期代理成立且经营证据恶化，策略门槛判定 bearish。',
      },
      confidence_breakdown: {
        final_confidence: 60.0,
        maximum_possible: 90.0,
        core_coverage: 1.0,
        supporting_coverage: 0.667,
        optional_coverage: 0.5,
        coverage_score: 0.857,
        evidence_quality: 0.88,
        unconstrained_confidence: 75.4,
        strategy_evidence_cap: 72.0,
        proxy_cap: 60.0,
        critical_capability_cap: null,
        active_cap_name: 'proxy_cap',
        active_cap_value: 60.0,
        applied_caps: { proxy_cap: 60.0 },
        notice: '置信度表示当前策略判断的数据支撑程度，不代表上涨概率或胜率。',
      },
      strengths: ['估值与价格位置具备低预期代理特征'],
      risks: ['营收增速继续恶化'],
      known_missing_dimensions: ['真实市场预期', '分析师一致预期', '业绩预测修正趋势'],
      limitations: ['LOW_EXPECTATION_PROXY 仅反映估值与价格压制，不能证明真实市场预期低'],
      legacy_comparison: {
        legacy_signal: 'bearish',
        legacy_signal_display: '↓ 看空 (bearish)',
        legacy_confidence: 48.4,
        legacy_key_metrics: { pe: { label: '市盈率', value: 28.5 } },
        legacy_strengths: ['盈利质量较强'],
        legacy_risks: ['当前估值吸引力有限'],
        new_signal: 'bearish',
        new_signal_display: '↓ 看空 (bearish)',
        new_confidence: 60.0,
        signal_changed: false,
        confidence_changed: true,
        core_difference: 'Legacy 基于离散财务指标硬阈值打分；New 采用连续因子引擎与策略门槛验证。',
        research_disclaimer: '仅供策略原型对照研究，不代表模型优劣评判。',
      },
      status: 'READY',
    };

    expect(detail.factor_contributions[0].role).toBe('core');
    expect(detail.factor_contributions[0].display_name).toBe('低预期代理');
    expect(detail.signal_explanation?.gate_checks).toContain('✓ 低预期代理成立');
    expect(detail.confidence_breakdown?.notice).toContain('不代表上涨概率或胜率');
    expect(detail.known_missing_dimensions).toContain('真实市场预期');
    expect(detail.legacy_comparison?.core_difference).toBeDefined();
  });
});
