const API_BASE_URL = 'http://localhost:8000';

export interface SecurityItem {
  symbol: string;
  canonical_symbol: string;
  name: string;
  pinyin: string;
  exchange: string;
  exchange_name: string;
  board: string;
  market: string;
  asset_type: string;
}

export interface SecuritySearchResponse {
  query: string;
  results: SecurityItem[];
  total_matches: number;
  has_more: boolean;
  cached: boolean;
  last_updated: string;
}

export interface SecurityResolveResponse {
  query: string;
  resolved: boolean;
  security?: SecurityItem | null;
  ambiguous: boolean;
  candidates: SecurityItem[];
  message: string;
}

export const securityApi = {
  async search(query: string, limit: number = 10): Promise<SecuritySearchResponse> {
    const url = new URL(`${API_BASE_URL}/api/securities/search`);
    if (query) url.searchParams.set('q', query.trim());
    url.searchParams.set('limit', String(limit));

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Search securities failed with status ${response.status}`);
    }

    return response.json();
  },

  async resolve(query: string): Promise<SecurityResolveResponse> {
    const url = new URL(`${API_BASE_URL}/api/securities/resolve`);
    url.searchParams.set('q', query.trim());

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Resolve security failed with status ${response.status}`);
    }

    return response.json();
  },
};
