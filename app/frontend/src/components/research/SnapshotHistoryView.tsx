import React, { useState, useEffect } from 'react';
import { History, Search, RefreshCw, Eye } from 'lucide-react';
import { SnapshotItemDTO } from '@/types/research';
import { researchApi } from '@/services/research-api';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';

interface SnapshotDetailPayload {
  snapshot_id: string;
  ticker: string;
  stock_name: string;
  captured_at: string;
  as_of: string;
  market_data_date: string | null;
  quality_status: string;
  retention_tags: string[];
  evaluations: Record<string, {
    display_name: string;
    version: string;
    signal: string;
    confidence: number;
    strategy_score: number | null;
    strategy_evidence_coverage: number;
    quality_status: string;
  }>;
}

export const SnapshotHistoryView: React.FC = () => {
  const { t } = useTranslation();
  const [snapshots, setSnapshots] = useState<SnapshotItemDTO[]>([]);
  const [tickerFilter, setTickerFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Snapshot detail dialog
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const [snapshotDetail, setSnapshotDetail] = useState<SnapshotDetailPayload | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);

  const fetchSnapshots = (ticker?: string) => {
    setIsLoading(true);
    setError(null);
    researchApi
      .getCorpusSnapshots(ticker || undefined)
      .then((data) => {
        setSnapshots(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || '获取快照列表失败');
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchSnapshots();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchSnapshots(tickerFilter.trim());
  };

  const handleOpenSnapshot = (snapshotId: string) => {
    setSelectedSnapshotId(snapshotId);
    setIsDetailLoading(true);
    researchApi
      .getCorpusSnapshotDetail(snapshotId)
      .then((data) => {
        setSnapshotDetail(data as unknown as SnapshotDetailPayload);
        setIsDetailLoading(false);
      })
      .catch(() => {
        setIsDetailLoading(false);
      });
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header and Filter */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-lg bg-zinc-900 border border-zinc-800">
        <div>
          <div className="flex items-center gap-2">
            <History size={18} className="text-emerald-400" />
            <h2 className="text-xl font-bold text-zinc-100">{t('research.snapshots.title')}</h2>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            {t('research.snapshots.subtitle')}
          </p>
        </div>

        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              value={tickerFilter}
              onChange={(e) => setTickerFilter(e.target.value)}
              placeholder={t('research.snapshots.filter_placeholder')}
              className="bg-zinc-950 border border-zinc-700 rounded pl-8 pr-3 py-1 text-xs text-zinc-100 placeholder-zinc-500 w-44"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 transition-colors"
          >
            {t('research.snapshots.search')}
          </button>
          <button
            type="button"
            onClick={() => {
              setTickerFilter('');
              fetchSnapshots();
            }}
            className="p-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
            title={t('common.refresh')}
          >
            <RefreshCw size={14} />
          </button>
        </form>
      </div>

      {/* Prospective Timeseries Notice */}
      <div className="p-3 rounded-lg bg-zinc-900/50 border border-zinc-800 text-xs text-zinc-400 flex items-center gap-2">
        <span className="text-amber-400 font-bold">ℹ</span>
        <span>
          纵向时间序列追踪说明：当前已有快照代表首批 prospective 采样基准，系统正持续按既定 retention policy 积累 prospective snapshots。
        </span>
      </div>

      {isLoading && (
        <div className="py-16 text-center text-zinc-400">
          <div className="animate-spin h-7 w-7 border-2 border-emerald-500 border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-sm">正在读取快照元数据索引...</p>
        </div>
      )}

      {error && (
        <div className="p-6 rounded-lg bg-rose-500/10 border border-rose-500/30 text-center text-rose-400 text-sm">
          {error}
        </div>
      )}

      {/* Snapshot Table */}
      {!isLoading && snapshots.length === 0 && (
        <div className="p-8 text-center text-zinc-500 bg-zinc-900/30 border border-zinc-800 rounded-lg text-sm">
          暂无匹配快照数据
        </div>
      )}

      {!isLoading && snapshots.length > 0 && (
        <div className="rounded-lg border border-zinc-800 overflow-hidden bg-zinc-900">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-zinc-950/80 text-zinc-400 border-b border-zinc-800 font-semibold text-left">
                  <th className="px-3 py-2.5">股票代码</th>
                  <th className="px-3 py-2.5">采集时间 (Captured At)</th>
                  <th className="px-3 py-2.5">行情基准日</th>
                  <th className="px-3 py-2.5">快照 ID</th>
                  <th className="px-3 py-2.5">质量状态</th>
                  <th className="px-3 py-2.5">留存标签</th>
                  <th className="px-3 py-2.5">评估完成</th>
                  <th className="px-3 py-2.5 text-center">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-850">
                {snapshots.map((s) => (
                  <tr key={s.snapshot_id} className="hover:bg-zinc-800/30 font-mono">
                    <td className="px-3 py-2.5 font-bold text-zinc-200">{s.ticker}</td>
                    <td className="px-3 py-2.5 text-zinc-300">{s.captured_at.slice(0, 19).replace('T', ' ')}</td>
                    <td className="px-3 py-2.5 text-zinc-400">{s.market_data_date || '—'}</td>
                    <td className="px-3 py-2.5 text-zinc-400 truncate max-w-[140px]">{s.snapshot_id}</td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          s.quality_status === 'HEALTHY'
                            ? 'bg-emerald-500/15 text-emerald-400'
                            : 'bg-amber-500/15 text-amber-300'
                        }`}
                      >
                        {s.quality_status}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-zinc-400">
                      {s.retention_tags?.join(', ') || 'prospective'}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="text-emerald-400">✓ 10 Profiles</span>
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <button
                        onClick={() => handleOpenSnapshot(s.snapshot_id)}
                        className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-[11px] flex items-center gap-1 mx-auto"
                      >
                        <Eye size={12} />
                        <span>查看评估</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Snapshot Detail Dialog */}
      <Dialog open={!!selectedSnapshotId} onOpenChange={(open) => !open && setSelectedSnapshotId(null)}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto bg-zinc-950 border-zinc-800 text-zinc-100 p-6">
          <DialogHeader className="border-b border-zinc-800 pb-3">
            <DialogTitle className="text-lg font-bold flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span>快照评估详情: {snapshotDetail?.ticker}</span>
                <span className="text-xs text-zinc-400 font-normal">({snapshotDetail?.stock_name})</span>
              </div>
              <Badge variant="outline" className="font-mono text-xs">
                {snapshotDetail?.snapshot_id?.slice(0, 16)}...
              </Badge>
            </DialogTitle>
          </DialogHeader>

          {isDetailLoading ? (
            <div className="py-8 text-center text-zinc-400">加载快照评估数据中...</div>
          ) : snapshotDetail ? (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-3 rounded bg-zinc-900 border border-zinc-800 text-xs font-mono">
                <div>
                  <span className="text-zinc-500 block">采集时间:</span>
                  <span className="text-zinc-200">{snapshotDetail.captured_at?.slice(0, 19).replace('T', ' ')}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block">行情基准日:</span>
                  <span className="text-zinc-200">{snapshotDetail.market_data_date}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block">质量状态:</span>
                  <span className="text-emerald-400">{snapshotDetail.quality_status}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block">留存标签:</span>
                  <span className="text-zinc-300">{snapshotDetail.retention_tags?.join(', ')}</span>
                </div>
              </div>

              <h4 className="font-semibold text-xs text-zinc-300 uppercase tracking-wider">
                10 位投资人策略原型评定明细 (Evaluations)
              </h4>

              <div className="rounded-lg border border-zinc-800 overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-zinc-950 text-zinc-400 border-b border-zinc-800 text-left">
                      <th className="px-3 py-2">投资人</th>
                      <th className="px-3 py-2">版本</th>
                      <th className="px-3 py-2 text-center">信号 (Signal)</th>
                      <th className="px-3 py-2 text-right">置信度 (Conf)</th>
                      <th className="px-3 py-2 text-right">策略评分 (Score)</th>
                      <th className="px-3 py-2 text-right">证据覆盖 (Cov)</th>
                      <th className="px-3 py-2">状态</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-850">
                    {Object.entries(snapshotDetail.evaluations || {}).map(([pid, ev]) => (
                      <tr key={pid} className="hover:bg-zinc-900/40">
                        <td className="px-3 py-2 font-medium text-zinc-200">{ev.display_name}</td>
                        <td className="px-3 py-2 font-mono text-zinc-400">{ev.version}</td>
                        <td className="px-3 py-2 text-center">
                          <span
                            className={`font-semibold ${
                              ev.signal === 'bullish'
                                ? 'text-emerald-400'
                                : ev.signal === 'bearish'
                                ? 'text-rose-400'
                                : 'text-amber-300'
                            }`}
                          >
                            {ev.signal}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-zinc-300">{ev.confidence?.toFixed(1)}%</td>
                        <td className="px-3 py-2 text-right font-mono text-zinc-300">
                          {ev.strategy_score !== null && ev.strategy_score !== undefined
                            ? ev.strategy_score > 0
                              ? `+${ev.strategy_score.toFixed(3)}`
                              : ev.strategy_score.toFixed(3)
                            : '—'}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-zinc-400">
                          {((ev.strategy_evidence_coverage || 0) * 100).toFixed(0)}%
                        </td>
                        <td className="px-3 py-2">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
                            {ev.quality_status || 'HEALTHY'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
};
