import {
  CorpusHealthSummaryDTO,
  InvestorDetailDTO,
  SnapshotItemDTO,
  StockResearchOverviewDTO,
} from '@/types/research';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const researchApi = {
  /**
   * Fetch complete stock research overview across all 10 Shadow profiles
   */
  getStockOverview: async (ticker: string, asOf?: string): Promise<StockResearchOverviewDTO> => {
    const url = new URL(`${API_BASE_URL}/api/research/stocks/${ticker}`);
    if (asOf) {
      url.searchParams.append('as_of', asOf);
    }
    const response = await fetch(url.toString());
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '请求失败' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },

  /**
   * Fetch full investor detail (factor contributions, gate checks, confidence breakdown)
   */
  getInvestorDetail: async (
    ticker: string,
    profileId: string,
    asOf?: string
  ): Promise<InvestorDetailDTO> => {
    const url = new URL(`${API_BASE_URL}/api/research/stocks/${ticker}/investors/${profileId}`);
    if (asOf) {
      url.searchParams.append('as_of', asOf);
    }
    const response = await fetch(url.toString());
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '请求失败' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },

  /**
   * Fetch prospective shadow corpus operational health summary
   */
  getCorpusSummary: async (): Promise<CorpusHealthSummaryDTO> => {
    const response = await fetch(`${API_BASE_URL}/api/research/corpus/summary`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '获取语料库健康度失败' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },

  /**
   * Fetch snapshots from temporal replay catalog
   */
  getCorpusSnapshots: async (ticker?: string, limit: number = 50): Promise<SnapshotItemDTO[]> => {
    const url = new URL(`${API_BASE_URL}/api/research/corpus/snapshots`);
    if (ticker) {
      url.searchParams.append('ticker', ticker);
    }
    url.searchParams.append('limit', limit.toString());
    const response = await fetch(url.toString());
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '获取快照列表失败' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },

  /**
   * Fetch evaluations for a specific snapshot
   */
  getCorpusSnapshotDetail: async (snapshotId: string): Promise<Record<string, unknown>> => {
    const response = await fetch(`${API_BASE_URL}/api/research/corpus/snapshots/${snapshotId}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '获取快照详情失败' }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    return response.json();
  },
};
