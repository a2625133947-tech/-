import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { changeAppLanguage, SupportedLanguage } from '@/i18n';
import { cn } from '@/lib/utils';
import { Check, Languages, Sparkles } from 'lucide-react';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

export const LanguageSettings: React.FC = () => {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.language === 'en-US' ? 'en-US' : 'zh-CN') as SupportedLanguage;

  const [aiReportLang, setAiReportLang] = useState<string>(() => {
    return localStorage.getItem('ai-hedge-fund-report-language') || 'follow_ui';
  });

  const handleSelectLanguage = (lng: SupportedLanguage) => {
    changeAppLanguage(lng);
  };

  const handleSelectReportLang = (val: string) => {
    setAiReportLang(val);
    localStorage.setItem('ai-hedge-fund-report-language', val);
  };

  const languageOptions = [
    {
      id: 'zh-CN',
      name: t('settings.language.zh_cn'),
      nativeName: '简体中文',
      region: '中国大陆 (CN)',
    },
    {
      id: 'en-US',
      name: t('settings.language.en_us'),
      nativeName: 'English (US)',
      region: 'United States',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-primary mb-2">
          {t('settings.language.title')}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t('settings.language.desc')}
        </p>
      </div>

      {/* Interface Language Card */}
      <Card className="bg-panel border-border">
        <CardHeader>
          <CardTitle className="text-lg font-medium text-primary flex items-center gap-2">
            <Languages size={18} className="text-emerald-400" />
            <span>{t('settings.language.select')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {languageOptions.map((opt) => {
              const isSelected = currentLang === opt.id;
              return (
                <Button
                  key={opt.id}
                  variant="outline"
                  className={cn(
                    "flex items-center justify-between h-auto p-4 bg-panel border-border hover:border-primary transition-all text-left",
                    isSelected && "border-emerald-500 bg-emerald-500/10 text-emerald-400"
                  )}
                  onClick={() => handleSelectLanguage(opt.id as SupportedLanguage)}
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="font-semibold text-sm text-primary">{opt.nativeName}</span>
                    <span className="text-xs text-muted-foreground">{opt.region}</span>
                  </div>
                  {isSelected && <Check size={18} className="text-emerald-400" />}
                </Button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* AI Output Language Card */}
      <Card className="bg-panel border-border">
        <CardHeader>
          <CardTitle className="text-lg font-medium text-primary flex items-center gap-2">
            <Sparkles size={18} className="text-blue-400" />
            <span>{t('settings.language.ai_response_lang')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {t('settings.language.ai_response_desc')}
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Button
              variant="outline"
              className={cn(
                "flex items-center justify-between h-auto p-3.5 bg-panel border-border hover:border-primary text-left",
                aiReportLang === 'follow_ui' && "border-blue-500 bg-blue-500/10 text-blue-400"
              )}
              onClick={() => handleSelectReportLang('follow_ui')}
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-primary">{t('settings.language.ai_follow_ui')}</span>
                <span className="text-xs text-muted-foreground">Auto</span>
              </div>
              {aiReportLang === 'follow_ui' && <Check size={16} className="text-blue-400" />}
            </Button>

            <Button
              variant="outline"
              className={cn(
                "flex items-center justify-between h-auto p-3.5 bg-panel border-border hover:border-primary text-left",
                aiReportLang === 'zh-CN' && "border-blue-500 bg-blue-500/10 text-blue-400"
              )}
              onClick={() => handleSelectReportLang('zh-CN')}
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-primary">{t('settings.language.ai_zh')}</span>
                <span className="text-xs text-muted-foreground">中文报告</span>
              </div>
              {aiReportLang === 'zh-CN' && <Check size={16} className="text-blue-400" />}
            </Button>

            <Button
              variant="outline"
              className={cn(
                "flex items-center justify-between h-auto p-3.5 bg-panel border-border hover:border-primary text-left",
                aiReportLang === 'en-US' && "border-blue-500 bg-blue-500/10 text-blue-400"
              )}
              onClick={() => handleSelectReportLang('en-US')}
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-primary">{t('settings.language.ai_en')}</span>
                <span className="text-xs text-muted-foreground">English Reports</span>
              </div>
              {aiReportLang === 'en-US' && <Check size={16} className="text-blue-400" />}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
