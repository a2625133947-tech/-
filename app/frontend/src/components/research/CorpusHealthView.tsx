import React, { useState, useEffect } from 'react';
import { Activity, AlertTriangle, CheckCircle2, RefreshCw, BarChart2, ShieldCheck } from 'lucide-react';
import { CorpusHealthSummaryDTO } from '@/types/research';
import { researchApi } from '@/services/research-api';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';

export const CorpusHealthView: React.FC = () => {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<CorpusHealthSummaryDTO | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = () => {
    setIsLoading(true);
    setError(null);
    researchApi
      .getCorpusSummary()
      .then((data) => {
        setSummary(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || '获取语料库健康度失败');
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-lg bg-zinc-900 border border-zinc-800">
        <div>
          <div className="flex items-center gap-2">
            <Activity size={18} className="text-emerald-400" />
            <h2 className="text-xl font-bold text-zinc-100">{t('research.corpus_health.title')}</h2>
            {summary && (
              <Badge
                className={
                  summary.health_status === 'Healthy'
                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                    : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                }
              >
                <ShieldCheck size={12} className="mr-1" />
                {summary.health_status === 'Healthy' ? t('research.corpus_health.status_healthy') : t('research.corpus_health.status_warning')}
              </Badge>
            )}
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            {t('research.corpus_health.subtitle')}
          </p>
        </div>

        <button
          onClick={fetchSummary}
          disabled={isLoading}
          className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 flex items-center gap-1.5 transition-colors"
        >
          <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
          <span>{t('research.corpus_health.refresh_metrics')}</span>
        </button>
      </div>

      {isLoading && (
        <div className="py-16 text-center text-zinc-400">
          <div className="animate-spin h-7 w-7 border-2 border-emerald-500 border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm">正在聚合语料库统计指标与漂移检测...</p>
        </div>
      )}

      {error && (
        <div className="p-6 rounded-lg bg-rose-500/10 border border-rose-500/30 text-center">
          <p className="text-sm text-rose-400 mb-2">{error}</p>
          <button
            onClick={fetchSummary}
            className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200"
          >
            重试
          </button>
        </div>
      )}

      {summary && !isLoading && (
        <div className="space-y-6">
          {/* Key Metric Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <div className="p-3.5 rounded-lg bg-zinc-900 border border-zinc-800">
              <span className="text-[11px] text-zinc-500 block">累计快照总数 (Snapshots)</span>
              <span className="text-2xl font-bold font-mono text-zinc-100 mt-1 block">
                {summary.snapshot_count}
              </span>
            </div>
            <div className="p-3.5 rounded-lg bg-zinc-900 border border-zinc-800">
              <span className="text-[11px] text-zinc-500 block">覆盖股票标的 (Tickers)</span>
              <span className="text-2xl font-bold font-mono text-zinc-100 mt-1 block">
                {summary.ticker_count}
              </span>
            </div>
            <div className="p-3.5 rounded-lg bg-zinc-900 border border-zinc-800">
              <span className="text-[11px] text-zinc-500 block">快照日期跨度 (Date Range)</span>
              <span className="text-sm font-semibold font-mono text-zinc-300 mt-2 block truncate">
                {summary.date_range ? `${summary.date_range[0]} ~ ${summary.date_range[1]}` : '—'}
              </span>
            </div>
            <div className="p-3.5 rounded-lg bg-zinc-900 border border-zinc-800">
              <span className="text-[11px] text-zinc-500 block">降级快照数 (Degraded)</span>
              <span
                className={`text-2xl font-bold font-mono mt-1 block ${
                  summary.degraded_snapshots_count > 0 ? 'text-amber-400' : 'text-zinc-100'
                }`}
              >
                {summary.degraded_snapshots_count}
              </span>
            </div>
            <div className="p-3.5 rounded-lg bg-zinc-900 border border-zinc-800">
              <span className="text-[11px] text-zinc-500 block">非完整评估批次 (Partial)</span>
              <span
                className={`text-2xl font-bold font-mono mt-1 block ${
                  summary.partial_runs_count > 0 ? 'text-rose-400' : 'text-zinc-100'
                }`}
              >
                {summary.partial_runs_count}
              </span>
            </div>
          </div>

          {/* Section: Operational Warnings */}
          {(summary.data_drift_warnings.length > 0 ||
            summary.factor_drift_warnings.length > 0 ||
            summary.distribution_warnings.length > 0) ? (
            <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-3">
              <div className="flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-400" />
                <h3 className="font-semibold text-sm text-amber-300">
                  语料库漂移与分布告警 (Active Drift & Distribution Warnings)
                </h3>
              </div>
              <div className="space-y-2">
                {summary.data_drift_warnings.map((w, idx) => (
                  <div key={idx} className="p-2.5 rounded bg-zinc-900/80 border border-amber-500/30 text-xs">
                    <span className="font-semibold text-amber-400 mr-2">[{w.warning_type}]</span>
                    <span className="text-zinc-200">{w.message}</span>
                  </div>
                ))}
                {summary.factor_drift_warnings.map((w, idx) => (
                  <div key={idx} className="p-2.5 rounded bg-zinc-900/80 border border-amber-500/30 text-xs">
                    <span className="font-semibold text-amber-400 mr-2">[{w.warning_type}]</span>
                    <span className="text-zinc-200">{w.factor_id}: {w.message}</span>
                  </div>
                ))}
                {summary.distribution_warnings.map((w, idx) => (
                  <div key={idx} className="p-2.5 rounded bg-zinc-900/80 border border-amber-500/30 text-xs">
                    <span className="font-semibold text-amber-400 mr-2">[{w.warning_type}]</span>
                    <span className="text-zinc-200">{w.profile_id}: {w.message}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-2 text-xs text-emerald-300">
              <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" />
              <span>未检测到能力覆盖突降、信号独占或置信度坍塌异常，语料库指标健康。</span>
            </div>
          )}

          {/* Section: Signal Distribution across Profiles */}
          <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-sm text-zinc-100 flex items-center gap-2">
                <BarChart2 size={16} className="text-emerald-400" />
                <span>各投资人策略信号分布 (Signal Distribution Across Profiles)</span>
              </h3>
              <div className="flex items-center gap-3 text-xs text-zinc-400 font-mono">
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" /> 看多 (Bullish)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-amber-500" /> 中性 (Neutral)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-rose-500" /> 看空 (Bearish)
                </span>
              </div>
            </div>

            <div className="rounded-lg border border-zinc-800 overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-zinc-950/80 text-zinc-400 border-b border-zinc-800 font-semibold text-left">
                    <th className="px-3 py-2">Profile ID</th>
                    <th className="px-3 py-2 text-center">看多 (Bullish)</th>
                    <th className="px-3 py-2 text-center">中性 (Neutral)</th>
                    <th className="px-3 py-2 text-center">看空 (Bearish)</th>
                    <th className="px-3 py-2 text-center">总计</th>
                    <th className="px-3 py-2 w-1/3">分布比例</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-850">
                  {Object.entries(summary.signal_distribution).map(([pid, dist]) => {
                    const total = (dist.bullish || 0) + (dist.neutral || 0) + (dist.bearish || 0);
                    const bPct = total > 0 ? ((dist.bullish || 0) / total) * 100 : 0;
                    const nPct = total > 0 ? ((dist.neutral || 0) / total) * 100 : 0;
                    const rPct = total > 0 ? ((dist.bearish || 0) / total) * 100 : 0;

                    return (
                      <tr key={pid} className="hover:bg-zinc-800/20">
                        <td className="px-3 py-2 font-mono font-medium text-zinc-200">{pid}</td>
                        <td className="px-3 py-2 text-center font-mono text-emerald-400">{dist.bullish || 0}</td>
                        <td className="px-3 py-2 text-center font-mono text-amber-300">{dist.neutral || 0}</td>
                        <td className="px-3 py-2 text-center font-mono text-rose-400">{dist.bearish || 0}</td>
                        <td className="px-3 py-2 text-center font-mono text-zinc-400">{total}</td>
                        <td className="px-3 py-2">
                          <div className="h-3 rounded-full bg-zinc-800 flex overflow-hidden">
                            {bPct > 0 && <div style={{ width: `${bPct}%` }} className="h-full bg-emerald-500" />}
                            {nPct > 0 && <div style={{ width: `${nPct}%` }} className="h-full bg-amber-500" />}
                            {rPct > 0 && <div style={{ width: `${rPct}%` }} className="h-full bg-rose-500" />}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section: Confidence Statistics across Profiles */}
          <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800 space-y-3">
            <h3 className="font-bold text-sm text-zinc-100">
              各投资人策略置信度统计 (Confidence Distribution Statistics)
            </h3>
            <div className="rounded-lg border border-zinc-800 overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-zinc-950/80 text-zinc-400 border-b border-zinc-800 font-semibold text-left">
                    <th className="px-3 py-2">Profile ID</th>
                    <th className="px-3 py-2 text-right">均值 (Mean)</th>
                    <th className="px-3 py-2 text-right">中位数 (Median)</th>
                    <th className="px-3 py-2 text-right">最小值 (Min)</th>
                    <th className="px-3 py-2 text-right">最大值 (Max)</th>
                    <th className="px-3 py-2 text-right">标准差 (StDev)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-850">
                  {Object.entries(summary.confidence_distribution).map(([pid, stats]) => (
                    <tr key={pid} className="hover:bg-zinc-800/20 font-mono">
                      <td className="px-3 py-2 font-medium text-zinc-200">{pid}</td>
                      <td className="px-3 py-2 text-right text-zinc-200">{stats.mean?.toFixed(1)}%</td>
                      <td className="px-3 py-2 text-right text-zinc-300">{stats.median?.toFixed(1)}%</td>
                      <td className="px-3 py-2 text-right text-zinc-400">{stats.min?.toFixed(1)}%</td>
                      <td className="px-3 py-2 text-right text-zinc-400">{stats.max?.toFixed(1)}%</td>
                      <td className="px-3 py-2 text-right text-zinc-400">{stats.stdev?.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
