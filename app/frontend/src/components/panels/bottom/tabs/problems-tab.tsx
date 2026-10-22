import { useTranslation } from 'react-i18next';

interface ProblemsTabProps {
  className?: string;
}

export function ProblemsTab({ className }: ProblemsTabProps) {
  const { t } = useTranslation();

  return (
    <div className={className}>
      <div className="h-full bg-background/50 rounded-md p-3 text-sm overflow-auto">
        <div className="text-muted-foreground">
          {t('bottom_panel.problems.no_problems')}
        </div>
      </div>
    </div>
  );
}
