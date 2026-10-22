import { useTranslation } from 'react-i18next';

interface ComponentActionsProps {
}

export function ComponentActions({ }: ComponentActionsProps) {
  const { t } = useTranslation();
  return (
    <div className="p-2 flex justify-between flex-shrink-0 items-center border-b mt-4">
      <span className="text-primary text-sm font-medium ml-4">{t('flow.components')}</span>
    </div>
  );
}
