import React from 'react';
import { ExternalLink, FileText, Calendar, Building2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useTranslation } from 'react-i18next';
import { FinancialReportReference } from '@/services/types';

interface FinancialReportLinkProps {
  report?: FinancialReportReference | string | null;
  mode?: 'full' | 'compact' | 'badge';
  className?: string;
}

export const FinancialReportLink: React.FC<FinancialReportLinkProps> = ({
  report,
  mode = 'full',
  className = '',
}) => {
  const { t, i18n } = useTranslation();

  if (!report) return null;

  // Backward compatibility: If report is a legacy string
  if (typeof report === 'string') {
    return <span className={`text-muted-foreground font-medium ${className}`}>{report}</span>;
  }

  const {
    title,
    report_type,
    publish_date,
    company_name,
    source_name = '巨潮资讯',
    source_url,
    pdf_url,
  } = report;

  // Security check: Only allow http / https protocols
  const isSafeUrl = (url?: string | null) => {
    if (!url) return false;
    return /^https?:\/\//i.test(url.trim());
  };

  const safeSourceUrl = isSafeUrl(source_url) && source_url ? source_url.trim() : null;
  const safePdfUrl = isSafeUrl(pdf_url) && pdf_url ? pdf_url.trim() : null;

  // Format date according to current locale
  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      const locale = i18n.language.startsWith('zh') ? 'zh-CN' : 'en-US';
      return new Intl.DateTimeFormat(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      }).format(d);
    } catch {
      return dateStr;
    }
  };

  const getReportTypeLabel = (type: string) => {
    switch (type) {
      case 'annual_report':
        return t('reports.annual_report', { defaultValue: '年报' });
      case 'semi_annual_report':
        return t('reports.semi_annual_report', { defaultValue: '半年报' });
      case 'q1_report':
        return t('reports.q1_report', { defaultValue: '一季报' });
      case 'q3_report':
        return t('reports.q3_report', { defaultValue: '三季报' });
      default:
        return t('reports.other_report', { defaultValue: '定期报告' });
    }
  };

  const formattedDate = formatDate(publish_date);
  const typeLabel = getReportTypeLabel(report_type);

  // Compact Mode: Just title with external link icon
  if (mode === 'compact') {
    return (
      <TooltipProvider>
        <Tooltip delayDuration={200}>
          <TooltipTrigger asChild>
            <span className={`inline-flex items-center gap-1.5 ${className}`}>
              {safeSourceUrl ? (
                <a
                  href={safeSourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 transition-colors"
                >
                  <span className="truncate max-w-[280px]">{title}</span>
                  <ExternalLink size={12} className="flex-shrink-0" />
                </a>
              ) : (
                <span className="font-medium text-foreground truncate">{title}</span>
              )}
              {safePdfUrl && (
                <a
                  href={safePdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/30 hover:bg-red-500/25 transition-colors"
                  title={t('reports.view_pdf', { defaultValue: '查看官方 PDF' })}
                >
                  <FileText size={10} />
                  <span>PDF</span>
                </a>
              )}
            </span>
          </TooltipTrigger>
          <TooltipContent side="top" className="text-xs p-2.5 space-y-1">
            <div className="font-semibold">{title}</div>
            <div className="text-[11px] text-muted-foreground flex items-center gap-2">
              <span>{t('reports.data_source', { defaultValue: '来源' })}: {source_name}</span>
              <span>•</span>
              <span>{t('reports.publish_date', { defaultValue: '发布日期' })}: {formattedDate}</span>
            </div>
            <div className="text-[10px] text-emerald-400 pt-0.5">
              {t('reports.click_view_original', { defaultValue: '点击在新标签页打开官方公告原文' })}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // Full Mode: Rich card with Title, Badges, Date, and action buttons
  return (
    <div className={`p-3 rounded-lg border border-border bg-card/60 hover:bg-card/90 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${className}`}>
      <div className="space-y-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          {safeSourceUrl ? (
            <a
              href={safeSourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-semibold text-foreground hover:text-emerald-500 flex items-center gap-1.5 transition-colors group"
            >
              <FileText size={15} className="text-emerald-500 flex-shrink-0" />
              <span className="truncate group-hover:underline">{title}</span>
              <ExternalLink size={13} className="text-muted-foreground group-hover:text-emerald-400 flex-shrink-0" />
            </a>
          ) : (
            <span className="text-sm font-semibold text-foreground flex items-center gap-1.5">
              <FileText size={15} className="text-muted-foreground flex-shrink-0" />
              <span>{title}</span>
            </span>
          )}
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-medium">
            {typeLabel}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {company_name && (
            <span className="flex items-center gap-1">
              <Building2 size={12} />
              {company_name}
            </span>
          )}
          {formattedDate && (
            <span className="flex items-center gap-1 font-mono">
              <Calendar size={12} />
              {formattedDate}
            </span>
          )}
          <span className="text-zinc-500">
            {t('reports.data_source', { defaultValue: '来源' })}: {source_name}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {safeSourceUrl && (
          <a
            href={safeSourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-muted hover:bg-muted/80 text-foreground border border-border/80 transition-colors"
          >
            <span>{t('reports.view_original', { defaultValue: '查看原文' })}</span>
            <ExternalLink size={11} />
          </a>
        )}
        {safePdfUrl && (
          <a
            href={safePdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-red-500/10 hover:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/30 transition-colors"
          >
            <FileText size={12} />
            <span>PDF</span>
            <ExternalLink size={11} />
          </a>
        )}
      </div>
    </div>
  );
};
