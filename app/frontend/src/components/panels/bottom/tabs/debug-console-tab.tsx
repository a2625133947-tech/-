import { useTranslation } from 'react-i18next';

interface DebugConsoleTabProps {
  className?: string;
}

export function DebugConsoleTab({ className }: DebugConsoleTabProps) {
  const { t } = useTranslation();

  return (
    <div className={className}>
      <div className="h-full bg-background/50 rounded-md p-3 text-sm overflow-auto">
        <div className="text-muted-foreground">
          {t('bottom_panel.debug_console.ready')}
        </div>
      </div>
    </div>
  );
}
