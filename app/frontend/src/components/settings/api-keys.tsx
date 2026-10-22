import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { apiKeysService, CredentialStatus } from '@/services/api-keys-api';
import { api, CatalogStatus } from '@/services/api';
import { invalidateModels } from '@/data/models';
import { Eye, EyeOff, Key, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface ApiKey {
  key: string;
  label: string;
  description: string;
  url: string;
  placeholder: string;
}

const LLM_API_KEYS: ApiKey[] = [
  {
    key: 'ANTHROPIC_API_KEY',
    label: 'Anthropic API',
    description: 'For Claude models (claude-4-sonnet, claude-4.1-opus, etc.)',
    url: 'https://anthropic.com/',
    placeholder: 'your-anthropic-api-key'
  },
  {
    key: 'DEEPSEEK_API_KEY',
    label: 'DeepSeek API',
    description: 'For DeepSeek models (deepseek-chat, deepseek-reasoner, etc.)',
    url: 'https://deepseek.com/',
    placeholder: 'your-deepseek-api-key'
  },
  {
    key: 'GROQ_API_KEY',
    label: 'Groq API',
    description: 'For Groq-hosted models (deepseek, llama3, etc.)',
    url: 'https://groq.com/',
    placeholder: 'your-groq-api-key'
  },
  {
    key: 'GOOGLE_API_KEY',
    label: 'Google API',
    description: 'For Gemini models (gemini-2.5-flash, gemini-2.5-pro)',
    url: 'https://ai.dev/',
    placeholder: 'your-google-api-key'
  },
  {
    key: 'OPENAI_API_KEY',
    label: 'OpenAI API',
    description: 'For OpenAI models (gpt-4o, gpt-4o-mini, etc.)',
    url: 'https://platform.openai.com/',
    placeholder: 'your-openai-api-key'
  },
  {
    key: 'OPENROUTER_API_KEY',
    label: 'OpenRouter API',
    description: 'For OpenRouter models (gpt-4o, gpt-4o-mini, etc.)',
    url: 'https://openrouter.ai/',
    placeholder: 'your-openrouter-api-key'
  },
  {
    key: 'GIGACHAT_API_KEY',
    label: 'GigaChat API',
    description: 'For GigaChat models (GigaChat-2-Max, etc.)',
    url: 'https://github.com/ai-forever/gigachat',
    placeholder: 'your-gigachat-api-key'
  },
  {
    key: 'XAI_API_KEY',
    label: 'xAI API',
    description: 'For Grok models',
    url: 'https://console.x.ai/',
    placeholder: 'your-xai-api-key'
  },
  {
    key: 'AZURE_OPENAI_API_KEY',
    label: 'Azure OpenAI API',
    description: 'Also set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME in .env.',
    url: 'https://portal.azure.com/',
    placeholder: 'your-azure-openai-api-key'
  }
];

export function ApiKeysSettings() {
  const { t } = useTranslation();
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [keyStatus, setKeyStatus] = useState<CredentialStatus[]>([]);
  const [syncStatus, setSyncStatus] = useState<CatalogStatus[]>([]);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadApiKeys();
  }, []);

  const loadApiKeys = async () => {
    try {
      setLoading(true);
      setError(null);
      const [statuses, catalog] = await Promise.all([
        apiKeysService.getCredentialStatus(),
        api.getModelCatalog()
      ]);
      setKeyStatus(statuses);
      setSyncStatus(catalog.sync_status);
    } catch (err) {
      setError('Failed to load provider status. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const saveKey = async (key: string) => {
    const value = draftKeys[key]?.trim();
    if (!value) return;
    setSavingKey(key);
    setError(null);
    let saved = false;
    try {
      await apiKeysService.createOrUpdateApiKey({ provider: key, key_value: value, is_active: true });
      saved = true;
      setDraftKeys(prev => ({ ...prev, [key]: '' }));
      invalidateModels();
      const [statuses, catalog] = await Promise.all([apiKeysService.getCredentialStatus(), api.getModelCatalog()]);
      setKeyStatus(statuses);
      setSyncStatus(catalog.sync_status);
    } catch (err) {
      setError(saved ? `${key} was saved, but its model status could not be loaded.` : `Failed to save ${key}. Please try again.`);
    } finally {
      setSavingKey(null);
    }
  };

  const toggleKeyVisibility = (key: string) => {
    setVisibleKeys(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const clearKey = async (key: string) => {
    try {
      await apiKeysService.deleteApiKey(key);
      setKeyStatus(await apiKeysService.getCredentialStatus());
      invalidateModels();
    } catch (err) {
      setError(`Failed to delete ${key}. Please try again.`);
    }
  };

  const renderApiKeySection = (title: string, description: string, keys: ApiKey[], icon: React.ReactNode) => (
    <Card className="bg-panel border-gray-700 dark:border-gray-700">
      <CardHeader>
        <CardTitle className="text-lg font-medium text-primary flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {keys.map((apiKey) => (
          <div key={apiKey.key} className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <button type="button" className="text-sm font-medium text-primary hover:text-blue-500 text-left" onClick={() => window.open(apiKey.url, '_blank')}>
                {apiKey.label}
              </button>
              <span className="text-xs text-muted-foreground">
                {keyStatus.find(status => status.key_name === apiKey.key)?.source === 'database' ? 'Saved locally' :
                  keyStatus.find(status => status.key_name === apiKey.key)?.source === 'environment' ? 'Configured in .env' : 'Not configured'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{apiKey.description}</p>
            <div className="flex items-center gap-2">
              <Input
                type={visibleKeys[apiKey.key] ? 'text' : 'password'}
                placeholder={keyStatus.find(status => status.key_name === apiKey.key)?.has_key ? 'Enter a new key to replace the saved key' : apiKey.placeholder}
                value={draftKeys[apiKey.key] || ''}
                onChange={(e) => setDraftKeys(prev => ({ ...prev, [apiKey.key]: e.target.value }))}
              />
              <Button variant="ghost" size="icon" onClick={() => toggleKeyVisibility(apiKey.key)} aria-label="Toggle key visibility">
                {visibleKeys[apiKey.key] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
              <Button size="sm" disabled={!draftKeys[apiKey.key]?.trim() || savingKey === apiKey.key} onClick={() => saveKey(apiKey.key)}>
                {savingKey === apiKey.key ? t('common.loading') : t('common.save')}
              </Button>
              {keyStatus.find(status => status.key_name === apiKey.key)?.source === 'database' && (
                <Button variant="ghost" size="icon" onClick={() => clearKey(apiKey.key)} aria-label={t('common.delete')}><Trash2 className="h-4 w-4" /></Button>
              )}
            </div>
            {syncStatus.find(status => status.provider === keyStatus.find(item => item.key_name === apiKey.key)?.provider)?.last_error && (
              <p className="text-xs text-amber-500">Model sync: {syncStatus.find(status => status.provider === keyStatus.find(item => item.key_name === apiKey.key)?.provider)?.last_error}</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-primary mb-2">{t('settings.api_keys.title')}</h2>
          <p className="text-sm text-muted-foreground">
            {t('common.loading')}
          </p>
        </div>
        <Card className="bg-panel border-gray-700 dark:border-gray-700">
          <CardContent className="p-6">
            <div className="text-sm text-muted-foreground">
              {t('common.loading')}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-primary mb-2">{t('settings.api_keys.title')}</h2>
        <p className="text-sm text-muted-foreground">
          {t('settings.api_keys.desc')}
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <Card className="bg-red-500/5 border-red-500/20">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Key className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
              <div className="space-y-1">
                <h4 className="text-sm font-medium text-red-500">Error</h4>
                <p className="text-xs text-muted-foreground">{error}</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setError(null);
                    loadApiKeys();
                  }}
                  className="text-xs mt-2 p-0 h-auto text-red-500 hover:text-red-400"
                >
                  Try again
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* LLM API Keys */}
      {renderApiKeySection(
        'Language Models',
        'API keys for accessing various large language model providers.',
        LLM_API_KEYS,
        <Key className="h-4 w-4" />
      )}

      {/* Security Note */}
      <Card className="bg-amber-500/5 border-amber-500/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Key className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <h4 className="text-sm font-medium text-amber-500">Security Note</h4>
              <p className="text-xs text-muted-foreground">
                Saved keys are kept in the local database. Their values are not loaded back into this page.
                Azure OpenAI also needs an endpoint and deployment name in .env.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
