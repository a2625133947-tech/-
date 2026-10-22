import { api } from '@/services/api';

export interface LanguageModel {
  display_name: string;
  model_name: string;
  provider: string;
  compatibility?: 'verified' | 'unverified';
}

let languageModels: LanguageModel[] | null = null;
let fetchedAt = 0;
let pending: Promise<LanguageModel[]> | null = null;
let generation = 0;

export const modelIdentity = (model: Pick<LanguageModel, 'provider' | 'model_name'>): string =>
  `${model.provider}\u0000${model.model_name}`;

export const invalidateModels = (): void => {
  generation += 1;
  languageModels = null;
  fetchedAt = 0;
  pending = null;
  window.dispatchEvent(new Event('model-catalog-updated'));
};

/**
 * Get the list of models from the backend API
 * Uses caching to avoid repeated API calls
 */
export const getModels = async (): Promise<LanguageModel[]> => {
  if (languageModels && Date.now() - fetchedAt < 5 * 60 * 1000) {
    return languageModels;
  }
  if (!pending) {
    const requestGeneration = generation;
    pending = api.getLanguageModels().then(models => {
      if (requestGeneration !== generation) return getModels();
      languageModels = models;
      fetchedAt = Date.now();
      return models;
    }).finally(() => { if (requestGeneration === generation) pending = null; });
  }
  return pending;
};

/**
 * Get the default model (GPT-4.1) from the models list
 */
export const getDefaultModel = async (): Promise<LanguageModel | null> => {
  try {
    const models = await getModels();
    return (
      models.find(model => model.provider === 'DeepSeek' && (model.model_name === 'deepseek-chat' || model.model_name === 'deepseek-flash')) ||
      models.find(model => model.provider === 'OpenAI' && model.model_name === 'gpt-4.1') ||
      models[0] ||
      null
    );
  } catch (error) {
    console.error('Failed to get default model:', error);
    return null;
  }
};
