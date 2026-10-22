import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zhCN from './locales/zh-CN.json';
import enUS from './locales/en-US.json';

export const LANGUAGE_STORAGE_KEY = 'ai-hedge-fund-language';
export const ONBOARDING_COMPLETED_KEY = 'ai-hedge-fund-onboarding-completed';

export type SupportedLanguage = 'zh-CN' | 'en-US';

export const getInitialLanguage = (): SupportedLanguage => {
  try {
    const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (saved === 'zh-CN' || saved === 'en-US') {
      return saved;
    }
  } catch (e) {
    console.warn('Unable to access localStorage for language preference', e);
  }

  // Detect browser language
  if (typeof navigator !== 'undefined' && navigator.language) {
    const browserLang = navigator.language.toLowerCase();
    if (browserLang.startsWith('zh')) {
      return 'zh-CN';
    }
    return 'en-US';
  }

  return 'zh-CN';
};

i18n
  .use(initReactI18next)
  .init({
    resources: {
      'zh-CN': { translation: zhCN },
      'en-US': { translation: enUS },
    },
    lng: getInitialLanguage(),
    fallbackLng: 'zh-CN',
    interpolation: {
      escapeValue: false, // React already escapes values
    },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: LANGUAGE_STORAGE_KEY,
    },
  });

export const changeAppLanguage = async (lng: SupportedLanguage): Promise<void> => {
  await i18n.changeLanguage(lng);
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, lng);
    window.dispatchEvent(new CustomEvent('ai-hedge-fund-language-changed', { detail: lng }));
  } catch (e) {
    console.warn('Unable to save language preference to localStorage', e);
  }
};

export default i18n;
