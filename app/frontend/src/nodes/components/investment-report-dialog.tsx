import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { extractBaseAgentKey } from '@/data/node-mappings';
import { createAgentDisplayNames } from '@/utils/text-utils';
import {
  ArrowDown,
  ArrowUp,
  Minus,
  Scale,
  ShieldAlert,
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  AlertOctagon,
  Activity,
  Layers,
  Database,
  Compass,
  Zap,
  FileText,
} from 'lucide-react';
import { AnalystDossierCard } from './analyst-dossier-card';
import { FinancialReportLink } from '@/components/common/FinancialReportLink';
import { safeResearchLink } from '@/services/report-intelligence-api';

interface InvestmentReportDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  outputNodeData: any;
  connectedAgentIds: Set<string>;
}

export function InvestmentReportDialog({
  isOpen,
  onOpenChange,
  outputNodeData,
  connectedAgentIds,
}: InvestmentReportDialogProps) {

  if (outputNodeData?.decisions?.backtest?.type === 'backtest_complete') {
    return null;
  }

  if (!outputNodeData || !outputNodeData.decisions) {
    return null;
  }

  const getActionBadge = (action: string) => {
    switch (action.toLowerCase()) {
      case 'buy':
      case 'long':
        return (
          <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/40 text-sm py-1 px-2.5 gap-1.5 font-semibold">
            <ArrowUp className="h-4 w-4" /> 买入 / 多头 (BUY)
          </Badge>
        );
      case 'sell':
      case 'short':
        return (
          <Badge className="bg-rose-500/20 text-rose-400 border-rose-500/40 text-sm py-1 px-2.5 gap-1.5 font-semibold">
            <ArrowDown className="h-4 w-4" /> 卖出 / 空头 (SELL)
          </Badge>
        );
      case 'hold':
      default:
        return (
          <Badge className="bg-amber-500/20 text-amber-300 border-amber-500/40 text-sm py-1 px-2.5 gap-1.5 font-semibold">
            <Minus className="h-4 w-4" /> 观望持有 (HOLD)
          </Badge>
        );
    }
  };

  const tickers = Object.keys(outputNodeData.decisions || {});
  const connectedUniqueAgentIds = Array.from(connectedAgentIds);
  const agents = Object.keys(outputNodeData.analyst_signals || {})
    .filter(agent =>
      extractBaseAgentKey(agent) !== 'risk_management_agent' && (connectedUniqueAgentIds.length === 0 || connectedUniqueAgentIds.includes(agent))
    );

  const agentDisplayNames = createAgentDisplayNames(agents);

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[92vh] overflow-y-auto bg-background/95 backdrop-blur-xl border border-border shadow-2xl p-6 sm:p-8">
        <DialogHeader className="border-b border-border/50 pb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <DialogTitle className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                <Compass className="h-6 w-6 text-emerald-400" />
                投资决策与深度综合研报
              </DialogTitle>
              <p className="text-xs text-muted-foreground mt-1">
                多智能体证据综合引擎（Evidence Synthesis）· 规则化风控约束 · 观点冲突仲裁
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <Badge variant="outline" className="gap-1 bg-muted/40">
                <Layers size={12} className="text-blue-400" />
                {agents.length} 位专业分析师协同
              </Badge>
              <Badge variant="outline" className="gap-1 bg-muted/40 text-emerald-400 border-emerald-500/30">
                <Activity size={12} />
                量化风控硬约束已生效
              </Badge>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-8 my-4">
          {tickers.map(ticker => {
            const decision = outputNodeData.decisions[ticker] || {};
            const currentPrice = outputNodeData.current_prices?.[ticker] || 'N/A';
            const riskBoundary = decision.risk_boundary || {};
            const keyDebates = decision.key_debates || [];
            const bullCase = decision.bull_case || [];
            const bearCase = decision.bear_case || [];
            const risks = decision.risks || [];
            const evidenceMatrix = decision.evidence_matrix || [];
            const changeConditions = decision.change_conditions || {};
            const dataQuality = decision.data_quality || {};

            // Extract company name and exchange from sources or recent reports
            const primaryRef = (decision.sources && decision.sources[0]) || (decision.recent_reports && decision.recent_reports[0]);
            const companyName = primaryRef?.company_name || '';
            const exchangeDisplay = primaryRef?.source_name ? `${primaryRef.source_name} · A股` : 'A股市场';

            return (
              <div key={ticker} className="space-y-8">
                {/* 1. Header Banner & Executive Action */}
                <Card className="border-border/80 bg-gradient-to-br from-card/90 via-card/50 to-muted/20 overflow-hidden shadow-md">
                  <div className="p-5 sm:p-6 flex flex-col lg:flex-row lg:items-center justify-between gap-6 border-b border-border/40">
                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-baseline gap-2">
                          <span className="text-3xl font-extrabold tracking-tight font-mono text-foreground">
                            {ticker}
                          </span>
                          {companyName && (
                            <span className="text-2xl font-bold tracking-tight text-foreground">
                              {companyName}
                            </span>
                          )}
                        </div>
                        <Badge variant="secondary" className="text-xs px-2 py-0.5 text-muted-foreground font-normal">
                          {exchangeDisplay}
                        </Badge>
                        {getActionBadge(decision.action || 'hold')}
                        <Badge variant="outline" className="font-mono text-sm py-0.5">
                          综合置信度 {decision.confidence ?? 50}%
                        </Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground pt-1">
                        <span>当前参考价：<strong className="text-foreground font-mono font-semibold">{typeof currentPrice === 'number' ? `¥${currentPrice.toFixed(2)}` : currentPrice}</strong></span>
                        <span>•</span>
                        <span>建议操作方向：<strong className="text-emerald-400 font-medium">{decision.position_action || (decision.action === 'hold' ? '保持当前观望仓位' : '按风控上限建仓')}</strong></span>
                        <span>•</span>
                        <span>买卖股数：<strong className="text-foreground font-mono">{decision.quantity ?? 0} 股</strong></span>
                      </div>
                    </div>

                    {/* Risk Management Metrics Pill */}
                    <div className="p-3.5 rounded-xl bg-muted/60 dark:bg-zinc-950/70 border border-border/80 text-xs space-y-1.5 min-w-[280px]">
                      <div className="flex items-center justify-between font-medium text-muted-foreground border-b border-border/60 pb-1">
                        <span className="flex items-center gap-1.5 text-foreground font-semibold">
                          <ShieldAlert size={14} className="text-amber-500" /> 量化风控硬约束
                        </span>
                        <span className="text-emerald-600 dark:text-emerald-400 font-mono font-medium">
                          {riskBoundary.max_position_pct ? `${(riskBoundary.max_position_pct * 100).toFixed(1)}% 组合限额` : '动态约束'}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                        <div>
                          <span className="text-muted-foreground">年化波动率：</span>
                          <span className="font-mono text-foreground font-medium">
                            {riskBoundary.volatility_ann ? `${(riskBoundary.volatility_ann * 100).toFixed(1)}%` : '适中'}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">允许买入上限：</span>
                          <span className="font-mono text-foreground font-medium">
                            {riskBoundary.max_shares ? `${riskBoundary.max_shares} 股` : '受限于净值'}
                          </span>
                        </div>
                      </div>
                      {riskBoundary.rationale && (
                        <p className="text-[10px] text-muted-foreground pt-0.5 leading-normal line-clamp-1">
                          {riskBoundary.rationale}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* 2. Core Investment Thesis */}
                  {decision.research_opinions?.report_count > 0 && <div className="p-5 border-b border-border space-y-3">
                    <h3 className="text-sm font-semibold">券商研报观点 · 独立来源证据</h3>
                    <p className="text-xs text-muted-foreground">原始金融数据来自行情及财务接口；以下是机构研报观点；下方投资主线是 AI 综合分析。</p>
                    <p className="text-xs">{decision.research_opinions.period?.start} ～ {decision.research_opinions.period?.end} · {decision.research_opinions.report_count} 篇 · Evidence Coverage: {decision.research_opinions.evidence_coverage?.level}</p>
                    {['consensus', 'themes', 'risks', 'disagreements'].map(field => (decision.research_opinions[field] || []).map((claim: { claim: string; citations: string[] }, index: number) => <div key={`${field}-${index}`} className="text-sm">
                      <p>{claim.claim}</p>{claim.citations.map(id => { const c = decision.research_opinions.citations?.find((ref: { citation_id: string }) => ref.citation_id === id); return c ? <details key={id} className="text-xs text-muted-foreground mt-1"><summary className="cursor-pointer text-emerald-400">来源 · {c.institution} · {c.published_at}{c.page ? ` · 第${c.page}页` : ''}</summary><p className="whitespace-pre-wrap mt-1">{c.quote}</p><a href={safeResearchLink(c.source_url + (c.page ? `#page=${c.page}` : ''))} target="_blank" rel="noopener noreferrer" className="underline">{c.title}</a></details> : null; })}
                    </div>))}
                  </div>}
                  <div className="p-5 sm:p-6 space-y-4">
                    <div className="space-y-2">
                      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                        <Compass size={15} className="text-emerald-500" />
                        核心投资研判主线 (Investment Thesis)
                      </h3>
                      <div className="p-4 rounded-xl bg-muted/50 border border-border text-sm sm:text-base leading-relaxed text-foreground">
                        <p className="whitespace-pre-line font-medium leading-relaxed">
                          {decision.thesis || decision.reasoning || "多智能体信号出现分歧，建议保持中性观望。"}
                        </p>
                      </div>
                    </div>

                    {/* Attribution Rationale Cards: Why This vs Why Not Others */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                      <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs space-y-1.5">
                        <span className="font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                          <CheckCircle2 size={14} /> 采纳当前决策的核心依据：
                        </span>
                        <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed font-normal">
                          {decision.why_this_action || decision.reasoning || "多空核心指标互相对冲，缺乏足够胜率。"}
                        </p>
                      </div>
                      <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs space-y-1.5">
                        <span className="font-semibold text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                          <AlertOctagon size={14} /> 未采纳相反操作的考量：
                        </span>
                        <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed font-normal">
                          {decision.why_not_others || "估值偏高压制做多空间，经营质地韧性限制做空动力。"}
                        </p>
                      </div>
                    </div>
                  </div>
                </Card>

                {/* 3. Key Debates Section (核心争议剖析) */}
                {keyDebates.length > 0 && (
                  <section className="space-y-3">
                    <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                      <Scale className="h-5 w-5 text-amber-500" />
                      当前核心观点冲突与争议 (Key Debates)
                    </h3>
                    <div className="grid grid-cols-1 gap-3">
                      {keyDebates.map((debate: any, idx: number) => (
                        <Card key={idx} className="border-border bg-card">
                          <CardHeader className="py-2.5 px-4 bg-muted/40 border-b border-border/40">
                            <CardTitle className="text-sm font-semibold flex items-center gap-2">
                              <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-600 dark:text-amber-400 font-mono font-medium">
                                焦点 #{idx + 1}
                              </span>
                              {debate.title}
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="p-4 space-y-3 text-xs">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <div className="p-3 rounded-md bg-emerald-500/10 border border-emerald-500/30">
                                <span className="font-semibold text-emerald-700 dark:text-emerald-400 block mb-1">多方视角与论据：</span>
                                <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed">{debate.bull_perspective}</p>
                              </div>
                              <div className="p-3 rounded-md bg-rose-500/10 border border-rose-500/30">
                                <span className="font-semibold text-rose-700 dark:text-rose-400 block mb-1">空方视角与论据：</span>
                                <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed">{debate.bear_perspective}</p>
                              </div>
                            </div>
                            <div className="p-3 rounded-md bg-muted/60 dark:bg-zinc-900 border border-border text-foreground">
                              <strong className="text-blue-600 dark:text-blue-400 block mb-0.5">投资总监（Portfolio Manager）研判结论：</strong>
                              <p className="leading-relaxed font-normal">{debate.pm_take}</p>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </section>
                )}

                {/* 4. Bull Case vs Bear Case vs Key Risks */}
                <section className="space-y-3">
                  <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                    <Zap className="h-5 w-5 text-blue-500" />
                    多空综合逻辑对比与风险清单
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    {/* Bull Case */}
                    <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-2">
                      <h4 className="font-semibold text-sm text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                        <TrendingUp size={16} /> 多头核心逻辑 (Bull Case)
                      </h4>
                      <ul className="space-y-1.5 text-zinc-800 dark:text-zinc-200">
                        {bullCase.length > 0 ? (
                          bullCase.map((item: string, i: number) => (
                            <li key={i} className="flex items-start gap-1.5">
                              <span className="text-emerald-600 font-bold">•</span>
                              <span>{item}</span>
                            </li>
                          ))
                        ) : (
                          <li className="text-muted-foreground">暂无显著多头驱动</li>
                        )}
                      </ul>
                    </div>

                    {/* Bear Case */}
                    <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 space-y-2">
                      <h4 className="font-semibold text-sm text-rose-700 dark:text-rose-400 flex items-center gap-1.5">
                        <TrendingDown size={16} /> 空头核心逻辑 (Bear Case)
                      </h4>
                      <ul className="space-y-1.5 text-zinc-800 dark:text-zinc-200">
                        {bearCase.length > 0 ? (
                          bearCase.map((item: string, i: number) => (
                            <li key={i} className="flex items-start gap-1.5">
                              <span className="text-rose-600 font-bold">•</span>
                              <span>{item}</span>
                            </li>
                          ))
                        ) : (
                          <li className="text-muted-foreground">暂无显著空头驱动</li>
                        )}
                      </ul>
                    </div>

                    {/* Key Risks */}
                    <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2">
                      <h4 className="font-semibold text-sm text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                        <ShieldAlert size={16} /> 需严密监控的风险 (Key Risks)
                      </h4>
                      <ul className="space-y-1.5 text-zinc-800 dark:text-zinc-200">
                        {risks.length > 0 ? (
                          risks.map((item: string, i: number) => (
                            <li key={i} className="flex items-start gap-1.5">
                              <span className="text-amber-600 font-bold">•</span>
                              <span>{item}</span>
                            </li>
                          ))
                        ) : (
                          <li className="text-muted-foreground">保持常规波动监控</li>
                        )}
                      </ul>
                    </div>
                  </div>
                </section>

                {/* 5. Evidence Matrix (证据矩阵) */}
                {evidenceMatrix.length > 0 && (
                  <section className="space-y-3">
                    <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                      <Layers className="h-5 w-5 text-indigo-500" />
                      投资主题证据矩阵 (Evidence Matrix)
                    </h3>
                    <div className="rounded-xl border border-border overflow-hidden bg-card">
                      <Table>
                        <TableHeader className="bg-muted/60">
                          <TableRow>
                            <TableHead className="w-1/5 text-foreground font-semibold">投资主题维度</TableHead>
                            <TableHead className="w-2/5 text-emerald-700 dark:text-emerald-400 font-semibold">支持看多证据</TableHead>
                            <TableHead className="w-2/5 text-rose-700 dark:text-rose-400 font-semibold">审慎/看空证据</TableHead>
                            <TableHead className="text-right text-foreground font-semibold">综合强度</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody className="text-xs">
                          {evidenceMatrix.map((row: any, i: number) => (
                            <TableRow key={i}>
                              <TableCell className="font-semibold text-foreground">{row.theme}</TableCell>
                              <TableCell className="text-emerald-800 dark:text-emerald-300">{row.bull_evidence || '—'}</TableCell>
                              <TableCell className="text-rose-800 dark:text-rose-300">{row.bear_evidence || '—'}</TableCell>
                              <TableCell className="text-right">
                                <Badge variant="outline" className="text-foreground">
                                  {row.assessment || '中性'}
                                </Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </section>
                )}

                {/* 6. What Would Change Our View (判断触发条件) */}
                {(changeConditions.upgrade_to_buy?.length > 0 || changeConditions.downgrade_to_sell?.length > 0) && (
                  <section className="space-y-3">
                    <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                      <Activity className="h-5 w-5 text-purple-500" />
                      什么会改变当前判断 (What Would Change Our View)
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 space-y-1.5">
                        <span className="font-semibold text-emerald-700 dark:text-emerald-400 block">
                          判断可能升级为【买入 (BUY)】的条件：
                        </span>
                        <ul className="space-y-1 text-zinc-800 dark:text-zinc-200">
                          {changeConditions.upgrade_to_buy.map((cond: string, i: number) => (
                            <li key={i} className="flex items-start gap-1">
                              <span className="text-emerald-600 font-bold">↑</span> {cond}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 space-y-1.5">
                        <span className="font-semibold text-rose-700 dark:text-rose-400 block">
                          判断可能降级为【卖出 (SELL)】的条件：
                        </span>
                        <ul className="space-y-1 text-zinc-800 dark:text-zinc-200">
                          {changeConditions.downgrade_to_sell.map((cond: string, i: number) => (
                            <li key={i} className="flex items-start gap-1">
                              <span className="text-rose-600 font-bold">↓</span> {cond}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </section>
                )}

                {/* 7. Data Quality & Limitations */}
                {dataQuality && (
                  <section className="p-3.5 rounded-xl bg-muted/20 border border-border/50 text-xs flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <Database size={15} className="text-zinc-400" />
                      <span className="font-semibold text-foreground">底层数据完备性评估：</span>
                      <Badge variant="outline" className="text-emerald-400 border-emerald-500/40">
                        {dataQuality.status || '完整验证'}
                      </Badge>
                      {dataQuality.verified_sources?.length > 0 && (
                        <span className="text-muted-foreground">
                          （来源：{dataQuality.verified_sources.join(', ')}）
                        </span>
                      )}
                    </div>
                    {dataQuality.limitations?.length > 0 && (
                      <div className="text-zinc-400 text-[11px]">
                        已知局限：{dataQuality.limitations.join('；')}
                      </div>
                    )}
                  </section>
                )}

                {/* 8. Key Sources & Statutory Filings (法定披露财报原文追踪) */}
                {((decision.sources && decision.sources.length > 0) || (decision.recent_reports && decision.recent_reports.length > 0)) && (
                  <section className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
                        <FileText className="h-5 w-5 text-emerald-500" />
                        主要资料来源与法定财报原文 (Official Filing Sources)
                      </h3>
                      <Badge variant="outline" className="text-xs text-muted-foreground">
                        来源认证：中国证监会法定信息披露平台 · 巨潮资讯 (CNINFO)
                      </Badge>
                    </div>

                    <div className="space-y-2">
                      {/* Priority key sources cited */}
                      {decision.sources && decision.sources.length > 0 && (
                        <div className="space-y-2">
                          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block">
                            核心研判引用财报：
                          </span>
                          <div className="grid grid-cols-1 gap-2">
                            {decision.sources.map((srcReport: any, i: number) => (
                              <FinancialReportLink
                                key={srcReport.source_id || i}
                                report={srcReport}
                                mode="full"
                              />
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Recent reports list if more available */}
                      {decision.recent_reports && decision.recent_reports.length > (decision.sources?.length || 0) && (
                        <div className="pt-2">
                          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-2">
                            上市公司最近定期报告归档：
                          </span>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {decision.recent_reports.slice(decision.sources?.length || 0, 6).map((recReport: any, j: number) => (
                              <FinancialReportLink
                                key={recReport.source_id || j}
                                report={recReport}
                                mode="full"
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </section>
                )}

                {/* 9. Detailed Analyst Research Section */}
                <section className="space-y-4 pt-4 border-t border-border/60">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
                        各分析师专业研判细则与证据档案
                      </h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        由各专业 Agent 独立产出的量化事实与推论，默认展示人类可读研报，原始 JSON 数据已收纳在各卡片底部
                      </p>
                    </div>
                    <Badge variant="secondary" className="font-mono text-xs">
                      共 {agents.length} 个分析节点
                    </Badge>
                  </div>

                  <div className="grid grid-cols-1 gap-4">
                    {agents.map(agent => {
                      const signalData = outputNodeData.analyst_signals[agent]?.[ticker];
                      if (!signalData) return null;
                      const displayName = agentDisplayNames.get(agent) || agent;

                      return (
                        <AnalystDossierCard
                          key={agent}
                          agentName={displayName}
                          signalData={signalData}
                        />
                      );
                    })}
                  </div>
                </section>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
