import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { Cloud, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, CatalogStatus } from '@/services/api';
import { invalidateModels } from '@/data/models';
import { useTranslation } from 'react-i18next';

interface CloudModelsProps {
  className?: string;
}

interface CloudModel {
  display_name: string;
  model_name: string;
  provider: string;
  compatibility?: string;
}

interface ModelProvider {
  name: string;
  models: Array<{
    display_name: string;
    model_name: string;
    compatibility?: string;
  }>;
}

export function CloudModels({ className }: CloudModelsProps) {
  const { t } = useTranslation();
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<CatalogStatus[]>([]);

  const fetchProviders = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/language-models/providers`);
      if (response.ok) {
        const data = await response.json();
        setProviders(data.providers);
        setSyncStatus(data.sync_status || []);
        invalidateModels();
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        setError(`Failed to fetch providers: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Failed to fetch cloud model providers:', error);
      setError('Failed to connect to backend service');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.refreshModelCatalog();
      invalidateModels();
      setSyncStatus(result.sync_status);
      await fetchProviders();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Model refresh failed');
    } finally {
      setLoading(false);
    }
  };

  // Flatten all models from all providers into a single array
  const allModels: CloudModel[] = providers.flatMap(provider =>
    provider.models.map(model => ({
      ...model,
      provider: provider.name
    }))
  ).sort((a, b) => a.provider.localeCompare(b.provider));

  return (
    <div className={cn("space-y-6", className)}>

      {error && (
        <div className="bg-red-900/20 border border-red-600/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Cloud className="h-5 w-5 text-red-500 mt-0.5" />
            <div>
              <h4 className="font-medium text-red-300">Error</h4>
              <p className="text-sm text-red-500 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-medium text-primary">
            {t('settings.models.available_models')}
          </h3>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">
              {allModels.length} models from {providers.length} providers
            </span>
            <button type="button" onClick={refresh} disabled={loading} className="text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-50">
              {t('settings.models.refresh_catalog')}
            </button>
          </div>
        </div>

        {syncStatus.filter(status => status.last_error).map(status => (
          <p key={status.provider} className="text-xs text-amber-500">
            {status.provider}: {status.last_error}. {status.source === 'cache' || status.source === 'fallback' ? 'Showing the last available list.' : ''}
          </p>
        ))}

        {loading ? (
          <div className="text-center py-8">
            <RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
          </div>
        ) : allModels.length > 0 ? (
          <div className="space-y-1">
            {allModels.map((model) => (
              <div 
                key={`${model.provider}-${model.model_name}`}
                className="group flex items-center justify-between bg-muted hover-bg rounded-md px-3 py-2.5 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                      <span className="font-medium text-sm truncate text-primary">{model.display_name}</span>
                      {model.compatibility === 'unverified' && <span className="text-xs text-amber-500">{t('settings.models.compatibility_unverified')}</span>}
                    {model.model_name !== model.display_name && (
                      <span className="font-mono text-xs text-muted-foreground">
                        {model.model_name}
                      </span>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Badge className="text-xs text-primary bg-primary/10 border-primary/30 hover:bg-primary/20 hover:border-primary/50">
                    {model.provider}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          !loading && (
            <div className="text-center py-8 text-muted-foreground">
              <Cloud className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No models available</p>
            </div>
          )
        )}
      </div>
    </div>
  );
}
