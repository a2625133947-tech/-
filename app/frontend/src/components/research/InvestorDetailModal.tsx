import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, ArrowDownRight, ArrowUpRight, CheckCircle2, Minus, XCircle } from 'lucide-react';
import { InvestorDetailDTO } from '@/types/research';
import { researchApi } from '@/services/research-api';
import { useTranslation } from 'react-i18next';

interface InvestorDetailModalProps {
  ticker: string;
  profileId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export const InvestorDetailModal: React.FC<InvestorDetailModalProps> = ({
  ticker,
  profileId,
  isOpen,
  onClose,
}) => {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<InvestorDetailDTO | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'factors' | 'gate' | 'confidence' | 'comparison' | 'limitations'>('factors');

  useEffect(() => {
    if (!isOpen || !profileId || !ticker) {
      setDetail(null);
      setError(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    researchApi
      .getInvestorDetail(ticker, profileId)
      .then((data) => {
        if (isMounted) {
          setDetail(data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || '加载策略详细数据失败');
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, profileId, ticker]);

  const renderFactorBar = (contrib: number | null) => {
    if (contrib === null || contrib === undefined) return <span className="text-zinc-500 text-xs">—</span>;
    const absVal = Math.min(Math.abs(contrib) * 200, 100);
    const isPositive = contrib >= 0;

    return (
      <div className="flex items-center gap-1.5 w-full">
        <div className="w-20 text-right text-xs font-mono">
          <span className={isPositive ? 'text-emerald-400' : 'text-rose-400'}>
            {isPositive ? `+${contrib.toFixed(3)}` : contrib.toFixed(3)}
          </span>
        </div>
        <div className="flex-1 h-3 bg-zinc-800 rounded relative overflow-hidden flex items-center">
          {/* Center line */}
          <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-zinc-600 z-10" />
          {isPositive ? (
            <div
              className="h-full bg-emerald-500/70 rounded-r"
              style={{
                marginLeft: '50%',
                width: `${absVal / 2}%`,
              }}
            />
          ) : (
            <div
              className="h-full bg-rose-500/70 rounded-l ml-auto"
              style={{
                marginRight: '50%',
                width: `${absVal / 2}%`,
              }}
            />
          )}
        </div>
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-zinc-950 border-zinc-800 text-zinc-100 p-6">
        <DialogHeader className="border-b border-zinc-800 pb-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <DialogTitle className="text-xl font-bold flex items-center gap-2">
                <span>{detail?.display_name || profileId}</span>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                  {detail?.profile_version || 'v1'}
                </span>
                <span className="text-xs text-zinc-400 font-normal">· {ticker}</span>
              </DialogTitle>
              <p className="text-xs text-zinc-400 mt-1">{detail?.description}</p>
            </div>

            {detail && (
              <div className="flex items-center gap-2">
                {detail.status === 'NOT_READY' ? (
                  <Badge variant="outline" className="bg-zinc-800 text-zinc-400 border-zinc-700 font-mono">
                    NOT READY
                  </Badge>
                ) : (
                  <>
                    <Badge
                      className={`gap-1 font-mono text-xs ${
                        detail.signal === 'bullish'
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : detail.signal === 'bearish'
                          ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                          : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                      }`}
                    >
                      {detail.signal === 'bullish' ? (
                        <ArrowUpRight size={13} />
                      ) : detail.signal === 'bearish' ? (
                        <ArrowDownRight size={13} />
                      ) : (
                        <Minus size={13} />
                      )}
                      {detail.signal_display}
                    </Badge>
                    <div className="px-2.5 py-1 rounded bg-zinc-900 border border-zinc-800 text-xs font-mono">
                      置信度: <span className="font-semibold text-zinc-200">{detail.confidence.toFixed(1)}%</span>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </DialogHeader>

        {isLoading && (
          <div className="py-12 text-center text-zinc-400">
            <div className="animate-spin h-6 w-6 border-2 border-emerald-500 border-t-transparent rounded-full mx-auto mb-3" />
            <p className="text-xs">加载深度策略因子与门槛数据中...</p>
          </div>
        )}

        {error && (
          <div className="py-8 text-center text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded p-4 my-4">
            <AlertCircle size={20} className="mx-auto mb-2 text-rose-400" />
            <p className="text-sm font-medium">{error}</p>
          </div>
        )}

        {detail && !isLoading && (
          <div className="mt-4 space-y-6">
            {/* Top Sub-tabs */}
            <div className="flex border-b border-zinc-800 text-xs gap-1">
              <button
                onClick={() => setActiveTab('factors')}
                className={`px-3 py-2 font-medium border-b-2 transition-colors ${
                  activeTab === 'factors'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {t('research.investor_detail.factors')}
              </button>
              <button
                onClick={() => setActiveTab('gate')}
                className={`px-3 py-2 font-medium border-b-2 transition-colors ${
                  activeTab === 'gate'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {t('research.investor_detail.gate_check')}
              </button>
              <button
                onClick={() => setActiveTab('confidence')}
                className={`px-3 py-2 font-medium border-b-2 transition-colors ${
                  activeTab === 'confidence'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {t('research.investor_detail.confidence_tab')}
              </button>
              <button
                onClick={() => setActiveTab('comparison')}
                className={`px-3 py-2 font-medium border-b-2 transition-colors ${
                  activeTab === 'comparison'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {t('research.investor_detail.model_comparison')}
              </button>
              <button
                onClick={() => setActiveTab('limitations')}
                className={`px-3 py-2 font-medium border-b-2 transition-colors ${
                  activeTab === 'limitations'
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {t('research.investor_detail.limitations')}
              </button>
            </div>

            {/* TAB 1: Factor Contributions */}
            {activeTab === 'factors' && (
              <div className="space-y-5">
                {detail.status === 'NOT_READY' ? (
                  <div className="p-6 rounded bg-zinc-900/50 border border-zinc-800 text-center">
                    <p className="text-amber-400 font-medium text-sm mb-1">该策略原型目前为 NOT READY 状态</p>
                    <p className="text-xs text-zinc-400">{detail.not_ready_reason}</p>
                    <p className="text-xs text-zinc-500 mt-2">暂无 New Factor 引擎评估结果，仅保留 Legacy 视角。</p>
                  </div>
                ) : (
                  (['core', 'supporting', 'optional'] as const).map((role) => {
                    const factors = detail.factor_contributions.filter((f) => f.role === role);
                    if (factors.length === 0) return null;
                    const roleTitle =
                      role === 'core'
                        ? 'CORE (核心因子 - 决定策略主方向)'
                        : role === 'supporting'
                        ? 'SUPPORTING (支撑因子 - 辅助印证与安全垫)'
                        : 'OPTIONAL (辅助观察因子)';

                    return (
                      <div key={role} className="space-y-2">
                        <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                          <span
                            className={`w-1.5 h-3 rounded-full ${
                              role === 'core' ? 'bg-emerald-500' : role === 'supporting' ? 'bg-sky-500' : 'bg-zinc-500'
                            }`}
                          />
                          {roleTitle}
                        </h4>
                        <div className="rounded-lg border border-zinc-800 overflow-hidden bg-zinc-900/40">
                          <div className="grid grid-cols-12 gap-2 px-3 py-2 bg-zinc-900/90 text-[11px] font-semibold text-zinc-400 border-b border-zinc-800">
                            <div className="col-span-4">因子名称 (Factor)</div>
                            <div className="col-span-2 text-right">评分 (Score)</div>
                            <div className="col-span-1 text-right">权重</div>
                            <div className="col-span-4 text-center">加权贡献 (Contribution)</div>
                            <div className="col-span-1 text-center">状态</div>
                          </div>
                          {factors.map((f) => (
                            <div
                              key={f.factor_id}
                              className="grid grid-cols-12 gap-2 px-3 py-2.5 text-xs border-b border-zinc-850 last:border-0 hover:bg-zinc-800/30 items-center"
                            >
                              <div className="col-span-4">
                                <span className="font-medium text-zinc-200">{f.display_name}</span>
                                <span className="block text-[10px] font-mono text-zinc-500">{f.factor_id}</span>
                              </div>
                              <div className="col-span-2 text-right font-mono text-zinc-300">
                                {f.score !== null ? (f.score > 0 ? `+${f.score.toFixed(3)}` : f.score.toFixed(3)) : '—'}
                              </div>
                              <div className="col-span-1 text-right font-mono text-zinc-400">{f.weight.toFixed(1)}</div>
                              <div className="col-span-4">{renderFactorBar(f.weighted_contribution)}</div>
                              <div className="col-span-1 text-center">
                                <span
                                  className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                                    f.status === 'AVAILABLE'
                                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                      : 'bg-zinc-800 text-zinc-400'
                                  }`}
                                >
                                  {f.status}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* TAB 2: Signal Gate & Explanation */}
            {activeTab === 'gate' && (
              <div className="space-y-4">
                {detail.signal_explanation ? (
                  <div className="space-y-4">
                    <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 space-y-3">
                      <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                        策略门槛与决策流 (Policy Gate Flow)
                      </h4>
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="text-zinc-500">策略样式 (Policy Style):</span>
                          <span className="ml-2 font-mono text-zinc-200">{detail.signal_explanation.policy_style}</span>
                        </div>
                        <div>
                          <span className="text-zinc-500">门槛判定器 (Gate ID):</span>
                          <span className="ml-2 font-mono text-zinc-200">
                            {detail.signal_explanation.gate_id || '无门槛'}
                          </span>
                        </div>
                        <div>
                          <span className="text-zinc-500">看多阈值 (Bullish):</span>
                          <span className="ml-2 font-mono text-emerald-400">
                            &gt;= +{detail.signal_explanation.bullish_threshold.toFixed(3)}
                          </span>
                        </div>
                        <div>
                          <span className="text-zinc-500">看空阈值 (Bearish):</span>
                          <span className="ml-2 font-mono text-rose-400">
                            &lt;= {detail.signal_explanation.bearish_threshold.toFixed(3)}
                          </span>
                        </div>
                        <div className="col-span-2">
                          <span className="text-zinc-500">门槛通过状态:</span>
                          <span className="ml-2">
                            {detail.signal_explanation.gate_passed === true ? (
                              <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 gap-1">
                                <CheckCircle2 size={12} /> 门槛通过 (PASSED)
                              </Badge>
                            ) : detail.signal_explanation.gate_passed === false ? (
                              <Badge className="bg-rose-500/20 text-rose-400 border border-rose-500/30 gap-1">
                                <XCircle size={12} /> 门槛未通过 (FAILED)
                              </Badge>
                            ) : (
                              <Badge variant="outline">无单独门槛</Badge>
                            )}
                          </span>
                        </div>
                      </div>

                      {/* Gate Checks List */}
                      {detail.signal_explanation.gate_checks.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-zinc-800 space-y-1.5">
                          <span className="text-xs font-medium text-zinc-400 block mb-1">分项门槛检验结果:</span>
                          {detail.signal_explanation.gate_checks.map((chk, idx) => (
                            <div
                              key={idx}
                              className={`text-xs px-2.5 py-1.5 rounded flex items-center gap-2 ${
                                chk.startsWith('✓')
                                  ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                                  : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                              }`}
                            >
                              <span>{chk}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="mt-3 pt-3 border-t border-zinc-800 text-xs">
                        <span className="text-zinc-500">判定原因代码 (Reason Code):</span>
                        <code className="ml-2 px-1.5 py-0.5 rounded bg-zinc-800 text-amber-300 font-mono text-[11px]">
                          {detail.signal_explanation.reason_code}
                        </code>
                      </div>

                      {detail.signal_explanation.signal_reason && (
                        <div className="p-3 rounded bg-zinc-950 border border-zinc-800/80 text-xs text-zinc-300 mt-2">
                          <span className="font-semibold text-zinc-400 block mb-1">综合信号解释:</span>
                          {detail.signal_explanation.signal_reason}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-zinc-400">暂无门槛数据</p>
                )}
              </div>
            )}

            {/* TAB 3: Confidence Breakdown */}
            {activeTab === 'confidence' && (
              <div className="space-y-4">
                {detail.confidence_breakdown ? (
                  <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 space-y-4">
                    <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
                      <div>
                        <div className="text-xs text-zinc-400">最终置信度 (Final Confidence)</div>
                        <div className="text-2xl font-bold font-mono text-zinc-100">
                          {detail.confidence_breakdown.final_confidence.toFixed(1)}%
                        </div>
                      </div>
                      {detail.confidence_breakdown.active_cap_name && (
                        <div className="text-right">
                          <span className="text-xs text-amber-400 block font-medium">生效封顶约束 (Active Cap):</span>
                          <span className="text-xs font-mono text-zinc-300">
                            {detail.confidence_breakdown.active_cap_name} (
                            {detail.confidence_breakdown.active_cap_value?.toFixed(1)}%)
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
                      <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800">
                        <span className="text-zinc-500 block text-[11px]">证据覆盖分 (Coverage Score)</span>
                        <span className="font-mono text-sm font-semibold text-zinc-200">
                          {(detail.confidence_breakdown.coverage_score * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800">
                        <span className="text-zinc-500 block text-[11px]">证据质量分 (Evidence Quality)</span>
                        <span className="font-mono text-sm font-semibold text-zinc-200">
                          {(detail.confidence_breakdown.evidence_quality * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800">
                        <span className="text-zinc-500 block text-[11px]">无约束置信度 (Unconstrained)</span>
                        <span className="font-mono text-sm font-semibold text-zinc-200">
                          {detail.confidence_breakdown.unconstrained_confidence.toFixed(1)}%
                        </span>
                      </div>
                      {detail.confidence_breakdown.strategy_evidence_cap !== null && (
                        <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800">
                          <span className="text-zinc-500 block text-[11px]">策略证据封顶 (Strategy Cap)</span>
                          <span className="font-mono text-sm font-semibold text-amber-300">
                            {detail.confidence_breakdown.strategy_evidence_cap.toFixed(1)}%
                          </span>
                        </div>
                      )}
                      {detail.confidence_breakdown.proxy_cap !== null && (
                        <div className="p-2.5 rounded bg-zinc-950/60 border border-zinc-800">
                          <span className="text-zinc-500 block text-[11px]">低预期代理封顶 (Proxy Cap)</span>
                          <span className="font-mono text-sm font-semibold text-amber-300">
                            {detail.confidence_breakdown.proxy_cap.toFixed(1)}%
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="p-3 rounded bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
                      <span className="font-semibold block mb-0.5">置信度定义与边界原则:</span>
                      {detail.confidence_breakdown.notice}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-zinc-400">暂无置信度拆解数据</p>
                )}
              </div>
            )}

            {/* TAB 4: Legacy vs New Comparison */}
            {activeTab === 'comparison' && (
              <div className="space-y-4">
                {detail.legacy_comparison ? (
                  <div className="rounded-lg border border-zinc-800 overflow-hidden">
                    <div className="grid grid-cols-2 divide-x divide-zinc-800">
                      {/* Left: Legacy */}
                      <div className="p-4 bg-zinc-900/30 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="font-semibold text-sm text-zinc-300">Legacy 模型视角</span>
                          <Badge variant="outline" className="text-xs">
                            {detail.legacy_comparison.legacy_signal_display}
                          </Badge>
                        </div>
                        <div className="text-xs space-y-1">
                          <div className="text-zinc-400">
                            置信度: <span className="font-mono text-zinc-200">{detail.legacy_comparison.legacy_confidence.toFixed(1)}%</span>
                          </div>
                          <div className="text-zinc-400">因子算法: 离散财务指标硬阈值打分</div>
                        </div>

                        {/* Legacy Key metrics */}
                        {Object.keys(detail.legacy_comparison.legacy_key_metrics).length > 0 && (
                          <div className="pt-2 border-t border-zinc-850">
                            <span className="text-[11px] font-semibold text-zinc-400 block mb-1">关键指标:</span>
                            <div className="grid grid-cols-2 gap-1 text-[11px]">
                              {Object.entries(detail.legacy_comparison.legacy_key_metrics).map(([k, v]: [string, { label?: string; value?: string | number }]) => (
                                <div key={k} className="flex justify-between bg-zinc-950/40 px-2 py-1 rounded">
                                  <span className="text-zinc-500">{v?.label || k}:</span>
                                  <span className="font-mono text-zinc-300">{v?.value ?? String(v)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Legacy Strengths & Risks */}
                        {detail.legacy_comparison.legacy_strengths.length > 0 && (
                          <div className="pt-2 border-t border-zinc-850 text-xs">
                            <span className="text-[11px] font-semibold text-emerald-400 block mb-0.5">优势:</span>
                            <ul className="list-disc list-inside text-zinc-400 text-[11px] space-y-0.5">
                              {detail.legacy_comparison.legacy_strengths.map((s, idx) => (
                                <li key={idx}>{s}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {detail.legacy_comparison.legacy_risks.length > 0 && (
                          <div className="pt-2 border-t border-zinc-850 text-xs">
                            <span className="text-[11px] font-semibold text-rose-400 block mb-0.5">风险:</span>
                            <ul className="list-disc list-inside text-zinc-400 text-[11px] space-y-0.5">
                              {detail.legacy_comparison.legacy_risks.map((r, idx) => (
                                <li key={idx}>{r}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>

                      {/* Right: New */}
                      <div className="p-4 bg-zinc-900/60 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="font-semibold text-sm text-emerald-400">New Research Model</span>
                          <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs">
                            {detail.legacy_comparison.new_signal_display}
                          </Badge>
                        </div>
                        <div className="text-xs space-y-1">
                          <div className="text-zinc-400">
                            置信度: <span className="font-mono text-zinc-200">{detail.legacy_comparison.new_confidence.toFixed(1)}%</span>
                          </div>
                          <div className="text-zinc-400">
                            策略评分: <span className="font-mono text-zinc-200">{detail.strategy_score?.toFixed(3) ?? '—'}</span>
                          </div>
                          <div className="text-zinc-400">因子算法: 连续因子引擎 + 策略门槛验证</div>
                        </div>

                        {detail.strengths.length > 0 && (
                          <div className="pt-2 border-t border-zinc-850 text-xs">
                            <span className="text-[11px] font-semibold text-emerald-400 block mb-0.5">新模型优势判断:</span>
                            <ul className="list-disc list-inside text-zinc-300 text-[11px] space-y-0.5">
                              {detail.strengths.map((s, idx) => (
                                <li key={idx}>{s}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {detail.risks.length > 0 && (
                          <div className="pt-2 border-t border-zinc-850 text-xs">
                            <span className="text-[11px] font-semibold text-rose-400 block mb-0.5">新模型风险判断:</span>
                            <ul className="list-disc list-inside text-zinc-300 text-[11px] space-y-0.5">
                              {detail.risks.map((r, idx) => (
                                <li key={idx}>{r}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="p-3 bg-zinc-950 border-t border-zinc-800 text-xs text-zinc-400">
                      <p className="font-medium text-zinc-300 mb-0.5">核心机制差异说明:</p>
                      <p>{detail.legacy_comparison.core_difference}</p>
                      <p className="text-[11px] text-zinc-500 mt-1 italic">{detail.legacy_comparison.research_disclaimer}</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-zinc-400">暂无对比数据</p>
                )}
              </div>
            )}

            {/* TAB 5: Limitations & Known Missing Dimensions */}
            {activeTab === 'limitations' && (
              <div className="space-y-4">
                {/* Known Missing Dimensions */}
                {detail.known_missing_dimensions.length > 0 && (
                  <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-2">
                    <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                      <AlertCircle size={14} />
                      模型当前无法观察的维度 (Known Missing Dimensions)
                    </h4>
                    <p className="text-xs text-zinc-400">
                      以下维度属于公开量化模型当前无法观测的客观局限，并非数据缺失故障，已在置信度模型中设置严格上限约束：
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                      {detail.known_missing_dimensions.map((dim, idx) => (
                        <div key={idx} className="p-2 rounded bg-zinc-900/60 border border-amber-500/30 text-xs text-amber-200 flex items-center gap-2">
                          <span className="text-amber-400 font-bold">⚠</span>
                          <span>{dim}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Strategy Limitations */}
                {detail.limitations.length > 0 && (
                  <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 space-y-2">
                    <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                      策略原型局限性声明 (Strategy Limitations)
                    </h4>
                    <ul className="list-disc list-inside text-xs text-zinc-400 space-y-1">
                      {detail.limitations.map((lim, idx) => (
                        <li key={idx}>{lim}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
