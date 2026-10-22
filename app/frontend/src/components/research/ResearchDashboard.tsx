import React, { useState } from 'react';
import { ResearchBanner } from './ResearchBanner';
import { StockAnalysisView } from './StockAnalysisView';
import { CorpusHealthView } from './CorpusHealthView';
import { SnapshotHistoryView } from './SnapshotHistoryView';
import { ReportIntelligenceView } from './ReportIntelligenceView';
import { LineChart, Activity, History } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type SubView = 'stocks' | 'reports' | 'corpus' | 'snapshots';

export const ResearchDashboard: React.FC = () => {
  const { t } = useTranslation();
  const [activeView, setActiveView] = useState<SubView>('reports');

  return (
    <div className="dark flex flex-col h-full w-full bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* 1. Prominent Research Mode Banner */}
      {activeView !== 'reports' && <ResearchBanner />}

      {/* 2. Top Navigation Bar */}
      <div className="flex items-center justify-between px-6 py-2.5 border-b border-zinc-800 bg-zinc-900/60">
        <div className="flex items-center gap-1">
          <button onClick={() => setActiveView('reports')} className={`px-3.5 py-1.5 rounded-md text-xs font-medium ${activeView === 'reports' ? 'bg-zinc-800 text-emerald-400' : 'text-zinc-400 hover:text-zinc-200'}`}>研报分析</button>
          <button
            id="tour-stock-analysis-tab"
            onClick={() => setActiveView('stocks')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeView === 'stocks'
                ? 'bg-zinc-800 text-emerald-400 border border-zinc-700 shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-850'
            }`}
          >
            <LineChart size={14} className={activeView === 'stocks' ? 'text-emerald-400' : ''} />
            <span>{t('research.tabs.stock_analysis')}</span>
          </button>

          <button
            id="tour-corpus-health-tab"
            onClick={() => setActiveView('corpus')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeView === 'corpus'
                ? 'bg-zinc-800 text-emerald-400 border border-zinc-700 shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-850'
            }`}
          >
            <Activity size={14} className={activeView === 'corpus' ? 'text-emerald-400' : ''} />
            <span>{t('research.tabs.corpus_health')}</span>
          </button>

          <button
            id="tour-snapshot-history-tab"
            onClick={() => setActiveView('snapshots')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeView === 'snapshots'
                ? 'bg-zinc-800 text-emerald-400 border border-zinc-700 shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-850'
            }`}
          >
            <History size={14} className={activeView === 'snapshots' ? 'text-emerald-400' : ''} />
            <span>{t('research.tabs.snapshot_history')}</span>
          </button>
        </div>

        <div className="text-[11px] font-mono text-zinc-500 hidden md:block">
          {activeView === 'reports' ? 'Research Intelligence · Cited Sources' : 'A-Share Factor Engine · Shadow Model Replay'}
        </div>
      </div>

      {/* 3. Main Viewport Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {activeView === 'stocks' && <StockAnalysisView />}
        {activeView === 'reports' && <ReportIntelligenceView />}
        {activeView === 'corpus' && <CorpusHealthView />}
        {activeView === 'snapshots' && <SnapshotHistoryView />}
      </div>
    </div>
  );
};
