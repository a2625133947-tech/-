import React, { useState, useEffect } from 'react';
import { AlertCircle, Database, CheckCircle2, ShieldAlert } from 'lucide-react';
import { StockResearchOverviewDTO } from '@/types/research';
import { researchApi } from '@/services/research-api';
import { securityApi } from '@/services/security-api';
import { SecuritySearchInput } from '@/components/common/SecuritySearchInput';
import { InvestorCard } from './InvestorCard';
import { InvestorDetailModal } from './InvestorDetailModal';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';
import { formatDate, formatPercent } from '@/utils/formatters';

const POPULAR_TICKERS = ['600519', '000001', '300750', '600036', '000858', '601127', '002594'];

export const StockAnalysisView: React.FC = () => {
  const { t } = useTranslation();
  const [tickerInput, setTickerInput] = useState<string>('600519');
  const [currentTicker, setCurrentTicker] = useState<string>('600519');
  const [overview, setOverview] = useState<StockResearchOverviewDTO | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Selected investor for detail modal
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState<boolean>(false);

  const fetchStock = (ticker: string) => {
    setIsLoading(true);
    setError(null);
    setCurrentTicker(ticker);

    researchApi
      .getStockOverview(ticker)
      .then((data) => {
        setOverview(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || t('research.stock_analysis.query_failed'));
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchStock('600519');
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = tickerInput.trim();
    if (!query) return;

    // Deterministic symbol resolution: if input is a name, resolve to code first
    try {
      const res = await securityApi.resolve(query);
      if (res.resolved && res.security) {
        setTickerInput(res.security.canonical_symbol);
        fetchStock(res.security.canonical_symbol);
        return;
      }
    } catch {
      // Fallback to raw input
    }
    fetchStock(query);
  };

  const handleOpenDetail = (profileId: string) => {
    setSelectedProfileId(profileId);
    setIsDetailOpen(true);
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Search Header */}
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-4">
        <form onSubmit={handleSearch} className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[240px] max-w-md">
            <SecuritySearchInput
              id="tour-research-search"
              value={tickerInput}
              onChange={setTickerInput}
              onSelectSecurity={(sec) => {
                setTickerInput(sec.canonical_symbol);
                fetchStock(sec.canonical_symbol);
              }}
              placeholder={t('research.stock_analysis.search_placeholder')}
            />
          </div>
          <button
            id="tour-research-submit"
            type="submit"
            disabled={isLoading}
            className="px-4 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            {isLoading ? t('common.loading') : t('research.stock_analysis.search_btn')}
          </button>

          {/* Quick ticker tags */}
          <div className="flex items-center gap-1.5 ml-auto text-xs text-zinc-400">
            <span>{t('research.stock_analysis.examples')}</span>
            {POPULAR_TICKERS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => {
                  setTickerInput(t);
                  fetchStock(t);
                }}
                className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                  currentTicker === t
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </form>
      </div>

      {/* Investor Strategy Section - Always in DOM for Tour Anchor */}
      <div id="tour-investor-grid" className="space-y-6 min-h-[160px]">
        {/* Loading state */}
        {isLoading && (
          <div className="py-16 text-center text-zinc-400">
            <div className="animate-spin h-7 w-7 border-2 border-emerald-500 border-t-transparent rounded-full mx-auto mb-3" />
            <p className="text-sm">{t('research.stock_analysis.loading_calc')}</p>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="p-6 rounded-lg bg-rose-500/10 border border-rose-500/30 text-center">
            <AlertCircle size={24} className="mx-auto mb-2 text-rose-400" />
            <h3 className="font-semibold text-rose-400 text-base mb-1">{t('research.stock_analysis.query_failed')}</h3>
            <p className="text-xs text-zinc-300 max-w-md mx-auto">{error}</p>
            <button
              onClick={() => fetchStock(currentTicker)}
              className="mt-3 px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200"
            >
              {t('research.stock_analysis.retry')}
            </button>
          </div>
        )}

        {/* Main Content Area */}
        {overview && !isLoading && (
          <div className="space-y-6">
            {/* Stock Info Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-lg bg-zinc-900 border border-zinc-800">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold text-zinc-100">{overview.stock_name}</h2>
                  <span className="font-mono text-sm px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                    {overview.ticker}
                  </span>
                  <Badge
                    className={
                      overview.data_quality === 'HEALTHY'
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                    }
                  >
                    <CheckCircle2 size={12} className="mr-1" />
                    {overview.data_quality}
                  </Badge>
                </div>
                <div className="flex items-center gap-4 text-xs text-zinc-400 mt-1.5 font-mono">
                  <span>as_of: {overview.as_of ? formatDate(overview.as_of, 'datetime') : '—'}</span>
                  <span>{overview.market_data_date ? `${overview.market_data_date}` : '—'}</span>
                  <span>{overview.snapshot_status}</span>
                  {overview.snapshot_id && (
                    <span className="truncate max-w-[180px]">
                      ID: {overview.snapshot_id.slice(0, 12)}...
                    </span>
                  )}
                </div>
              </div>

              {/* Production Decision Card (LEGACY) */}
              <div className="p-3 rounded-md bg-zinc-950 border border-zinc-800 flex items-center gap-4 min-w-[280px]">
                <div>
                  <div className="flex items-center gap-1.5 text-[11px] text-zinc-400 font-mono">
                    <ShieldAlert size={12} className="text-emerald-400" />
                    <span>{t('research.banner.decision_engine')} (LEGACY)</span>
                  </div>
                  <div className="flex items-baseline gap-2 mt-0.5">
                    <span className="text-base font-bold text-zinc-100 font-mono">
                      {overview.production_decision.action_display}
                    </span>
                    <span className="text-xs text-zinc-400 font-mono">
                      {t('research.stock_analysis.confidence')}: {formatPercent(overview.production_decision.confidence, 1)}
                    </span>
                    <span className="text-xs text-zinc-400 font-mono">
                      {overview.production_decision.quantity}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Section 1: 10 Shadow Ready Investors */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Database size={16} className="text-emerald-400" />
                  <h3 className="font-bold text-base text-zinc-100">
                    {t('research.stock_analysis.title')} · 10 Shadow Profiles
                  </h3>
                </div>
                <span className="text-xs text-zinc-400">{t('research.stock_analysis.view_detail')}</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {overview.investor_cards.map((card) => (
                  <InvestorCard
                    key={card.profile_id}
                    card={card}
                    onClick={() => handleOpenDetail(card.profile_id)}
                  />
                ))}
              </div>
            </div>

            {/* Section 2: NOT_READY Investors */}
            {overview.not_ready_cards.length > 0 && (
              <div className="pt-4 border-t border-zinc-800/80">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-bold text-sm text-zinc-400">
                    Legacy Only / Not Ready
                  </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {overview.not_ready_cards.map((card) => (
                    <InvestorCard
                      key={card.profile_id}
                      card={card}
                      onClick={() => handleOpenDetail(card.profile_id)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Investor Detail Modal */}
      <InvestorDetailModal
        ticker={currentTicker}
        profileId={selectedProfileId}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
      />
    </div>
  );
};
