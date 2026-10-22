import { useTranslation } from 'react-i18next';

interface TerminalTabProps {
  className?: string;
}

export function TerminalTab({ className }: TerminalTabProps) {
  const { t } = useTranslation();

  return (
    <div className={className}>
      <div className="h-full rounded-md p-3 font-mono text-sm text-green-500 overflow-auto">
        <div className="whitespace-pre-wrap">
          <span className="text-blue-500">$ </span>
          <span className="text-primary">{t('bottom_panel.terminal.welcome')}</span>
          {'\n'}
          <span className="text-muted-foreground">{t('bottom_panel.terminal.hint')}</span>
          {'\n'}
          <span className="text-blue-500">$ </span>
          <span className="animate-pulse">_</span>
        </div>
      </div>
    </div>
  );
}
