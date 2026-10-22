import i18n from '@/i18n';

/**
 * Format a number according to the current locale
 */
export function formatNumber(
  value: number | string | null | undefined,
  options: Intl.NumberFormatOptions = { maximumFractionDigits: 2 }
): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '—';

  const locale = i18n.language === 'en-US' ? 'en-US' : 'zh-CN';
  return new Intl.NumberFormat(locale, options).format(num);
}

/**
 * Format currency according to the current locale while preserving the correct currency symbol.
 * Defaults to USD ($) or CNY (¥) based on currency parameter.
 */
export function formatCurrency(
  value: number | string | null | undefined,
  currency: 'CNY' | 'USD' = 'CNY',
  decimals = 2
): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '—';

  const locale = i18n.language === 'en-US' ? 'en-US' : 'zh-CN';
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(num);
  } catch {
    const symbol = currency === 'USD' ? '$' : '¥';
    return `${symbol}${formatNumber(num, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
  }
}

/**
 * Format percentage
 */
export function formatPercent(
  value: number | string | null | undefined,
  decimals = 1
): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '—';

  return `${num > 0 ? '+' : ''}${num.toFixed(decimals)}%`;
}

/**
 * Format date according to current locale
 */
export function formatDate(
  dateInput: string | number | Date | null | undefined,
  formatStyle: 'full' | 'short' | 'time' | 'datetime' = 'short'
): string {
  if (!dateInput) return '—';
  const date = new Date(dateInput);
  if (isNaN(date.getTime())) return String(dateInput);

  const locale = i18n.language === 'en-US' ? 'en-US' : 'zh-CN';

  if (formatStyle === 'time') {
    return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  if (formatStyle === 'datetime') {
    return date.toLocaleString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  if (formatStyle === 'full') {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'full' }).format(date);
  }

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

/**
 * Translate dynamic Signal enum (bullish / bearish / neutral)
 */
export function translateSignal(signal: string | null | undefined): string {
  if (!signal) return i18n.t('signals.unknown', { defaultValue: '未知' });
  const key = signal.toLowerCase().trim();
  switch (key) {
    case 'bullish':
      return i18n.t('signals.bullish', { defaultValue: '看多' });
    case 'bearish':
      return i18n.t('signals.bearish', { defaultValue: '看空' });
    case 'neutral':
      return i18n.t('signals.neutral', { defaultValue: '中性' });
    default:
      return signal;
  }
}

/**
 * Translate dynamic Trading Action enum (BUY / SELL / HOLD / SHORT / COVER)
 */
export function translateAction(action: string | null | undefined): string {
  if (!action) return '—';
  const key = action.toLowerCase().trim();
  switch (key) {
    case 'buy':
      return i18n.t('actions.buy', { defaultValue: '买入' });
    case 'sell':
      return i18n.t('actions.sell', { defaultValue: '卖出' });
    case 'hold':
      return i18n.t('actions.hold', { defaultValue: '持有' });
    case 'short':
      return i18n.t('actions.short', { defaultValue: '做空' });
    case 'cover':
      return i18n.t('actions.cover', { defaultValue: '平仓' });
    default:
      return action.toUpperCase();
  }
}

/**
 * Translate status (idle / in_progress / completed / failed)
 */
export function translateStatus(status: string | null | undefined): string {
  if (!status) return '—';
  const key = status.toLowerCase().replace(/_/g, '');
  if (key === 'idle') return i18n.t('status_labels.idle', { defaultValue: '空闲' });
  if (key === 'inprogress' || key === 'running') return i18n.t('status_labels.in_progress', { defaultValue: '分析中' });
  if (key === 'completed' || key === 'complete' || key === 'done') return i18n.t('status_labels.completed', { defaultValue: '已完成' });
  if (key === 'failed' || key === 'error') return i18n.t('status_labels.failed', { defaultValue: '失败' });
  return status;
}
