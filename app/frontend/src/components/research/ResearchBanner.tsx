import React from 'react';
import { AlertTriangle, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface ResearchBannerProps {
  className?: string;
}

export const ResearchBanner: React.FC<ResearchBannerProps> = ({ className = '' }) => {
  const { t } = useTranslation();

  return (
    <div
      className={`w-full bg-amber-500/10 border-b border-amber-500/30 px-4 py-2.5 text-xs text-amber-200 flex flex-wrap items-center justify-between gap-2 ${className}`}
    >
      <div className="flex items-center gap-2">
        <span className="flex h-2 w-2 relative">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
        </span>
        <span className="font-bold tracking-wider text-amber-400">{t('research.banner.research_mode')}</span>
        <span className="text-zinc-400">|</span>
        <span className="text-amber-200/90 font-medium">
          {t('research.banner.disclaimer')}
        </span>
        <span className="hidden sm:inline text-amber-300/70">
          {t('research.banner.disclaimer_sub')}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/60 text-zinc-300 font-mono text-[11px]">
          <ShieldCheck size={13} className="text-emerald-400" />
          <span>{t('research.banner.decision_engine')}</span>
          <span className="font-semibold text-emerald-400">LEGACY</span>
        </div>
        <div className="flex items-center gap-1 text-[11px] text-amber-300/80">
          <AlertTriangle size={12} />
          <span>{t('research.banner.confidence_note')}</span>
        </div>
      </div>
    </div>
  );
};
