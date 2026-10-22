import React from 'react';
import { ArrowUpRight, ArrowDownRight, Minus, ChevronRight, Lock } from 'lucide-react';
import { ShadowInvestorCardDTO } from '@/types/research';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';
import { translateSignal } from '@/utils/formatters';

interface InvestorCardProps {
  card: ShadowInvestorCardDTO;
  onClick: () => void;
}

export const InvestorCard: React.FC<InvestorCardProps> = ({ card, onClick }) => {
  const { t } = useTranslation();
  const isNotReady = card.status === 'NOT_READY';

  const getSignalBadge = () => {
    if (isNotReady) {
      return (
        <Badge variant="outline" className="bg-zinc-800 text-zinc-400 border-zinc-700 gap-1 font-mono">
          <Lock size={11} />
          {t('research.stock_analysis.not_ready')}
        </Badge>
      );
    }

    const s = card.signal.toLowerCase();
    if (s === 'bullish') {
      return (
        <Badge className="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 gap-1 font-medium hover:bg-emerald-500/20">
          <ArrowUpRight size={13} className="text-emerald-400" />
          ↑ {translateSignal('bullish')}
        </Badge>
      );
    }
    if (s === 'bearish') {
      return (
        <Badge className="bg-rose-500/15 text-rose-400 border border-rose-500/30 gap-1 font-medium hover:bg-rose-500/20">
          <ArrowDownRight size={13} className="text-rose-400" />
          ↓ {translateSignal('bearish')}
        </Badge>
      );
    }
    return (
      <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/30 gap-1 font-medium hover:bg-amber-500/20">
        <Minus size={13} className="text-amber-300" />
        — {translateSignal('neutral')}
      </Badge>
    );
  };

  return (
    <div
      onClick={onClick}
      className={`group relative rounded-lg border transition-all duration-200 cursor-pointer overflow-hidden p-4 ${
        isNotReady
          ? 'bg-zinc-900/40 border-zinc-800/80 opacity-75 hover:opacity-100 hover:border-zinc-700'
          : 'bg-zinc-900/90 border-zinc-800 hover:border-zinc-600 hover:bg-zinc-850 shadow-sm hover:shadow-md'
      }`}
    >
      {/* Top Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-base text-zinc-100 group-hover:text-emerald-400 transition-colors">
              {card.display_name}
            </h3>
            <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700/50">
              {card.profile_version}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 line-clamp-1">{card.lens}</p>
        </div>
        <div>{getSignalBadge()}</div>
      </div>

      {/* Metrics Row */}
      {!isNotReady ? (
        <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-zinc-800/80">
          <div>
            <div className="text-[11px] text-zinc-500">{t('research.stock_analysis.confidence')}</div>
            <div className="text-sm font-semibold text-zinc-200 font-mono">
              {card.confidence.toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-[11px] text-zinc-500">{t('research.stock_analysis.strategy_score')}</div>
            <div
              className={`text-sm font-semibold font-mono ${
                (card.strategy_score ?? 0) > 0
                  ? 'text-emerald-400'
                  : (card.strategy_score ?? 0) < 0
                  ? 'text-rose-400'
                  : 'text-zinc-300'
              }`}
            >
              {card.strategy_score !== null && card.strategy_score !== undefined
                ? (card.strategy_score > 0 ? `+${card.strategy_score.toFixed(3)}` : card.strategy_score.toFixed(3))
                : '—'}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-zinc-500">{t('research.stock_analysis.evidence_coverage')}</div>
            <div className="text-sm font-semibold text-zinc-200 font-mono">
              {(card.strategy_evidence_coverage * 100).toFixed(0)}%
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-3 pt-3 border-t border-zinc-800/80 text-xs text-zinc-400 bg-zinc-950/40 p-2 rounded">
          <span className="text-amber-400 font-medium">{t('common.info')}: </span>
          <span>{card.not_ready_reason}</span>
        </div>
      )}

      {/* Footer link */}
      <div className="mt-3 flex items-center justify-end gap-1 text-[11px] text-zinc-500 group-hover:text-zinc-300 transition-colors">
        <span>{t('research.stock_analysis.view_detail')}</span>
        <ChevronRight size={13} className="group-hover:translate-x-0.5 transition-transform" />
      </div>
    </div>
  );
};
