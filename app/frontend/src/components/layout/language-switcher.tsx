import { Button } from '@/components/ui/button';
import { changeAppLanguage, SupportedLanguage } from '@/i18n';
import { cn } from '@/lib/utils';
import { Languages } from 'lucide-react';
import React from 'react';
import { useTranslation } from 'react-i18next';

interface LanguageSwitcherProps {
  className?: string;
  variant?: 'compact' | 'full';
}

export const LanguageSwitcher: React.FC<LanguageSwitcherProps> = ({
  className = '',
  variant = 'compact',
}) => {
  const { i18n } = useTranslation();
  const currentLang = (i18n.language === 'en-US' ? 'en-US' : 'zh-CN') as SupportedLanguage;

  const toggleLanguage = () => {
    const nextLang = currentLang === 'zh-CN' ? 'en-US' : 'zh-CN';
    changeAppLanguage(nextLang);
  };

  if (variant === 'full') {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <Button
          variant={currentLang === 'zh-CN' ? 'default' : 'outline'}
          size="sm"
          onClick={() => changeAppLanguage('zh-CN')}
          className="text-xs h-8 px-3"
        >
          简体中文
        </Button>
        <Button
          variant={currentLang === 'en-US' ? 'default' : 'outline'}
          size="sm"
          onClick={() => changeAppLanguage('en-US')}
          className="text-xs h-8 px-3"
        >
          English
        </Button>
      </div>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleLanguage}
      id="tour-language-switcher"
      className={cn(
        "h-8 px-2 gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors border border-transparent hover:border-border",
        className
      )}
      title={currentLang === 'zh-CN' ? 'Switch to English' : '切换为简体中文'}
      aria-label="Toggle language"
    >
      <Languages size={14} className="text-muted-foreground" />
      <span className="font-medium">{currentLang === 'zh-CN' ? '中文' : 'EN'}</span>
    </Button>
  );
};
