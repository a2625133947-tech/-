export type ResearchPeriod = 'week' | 'month' | 'year' | 'custom';
export interface ResearchClaim { claim: string; citations: string[]; kind: string }
export interface ResearchValue { metric: string; value: number | string; year: number | null; unit: string; currency: string; citations: string[] }
export interface ResearchCitation {
  citation_id: string; report_id: string; chunk_id: string; page: number | null;
  section: string; source_url: string; quote: string; title: string;
  institution: string; published_at: string; analyst: string[];
}
export interface ResearchReport {
  canonical_report_id: string; title: string; institution: string; analyst: string[];
  published_at: string; provider_published_at?: string; rating: string;
  source_provider: string; source_url: string; pdf_url: string; source_urls: string[];
  content_kind: string; status: string;
}
export interface ResearchIntelligence {
  ticker: string; company_name: string; exchange: string; report_count: number; institutions: string[]; status: string;
  period: { period: ResearchPeriod; start: string; end: string };
  consensus: ResearchClaim[]; disagreements: ResearchClaim[]; themes: ResearchClaim[];
  risks: ResearchClaim[]; catalysts: ResearchClaim[]; changes: ResearchClaim[];
  ratings: ResearchValue[]; target_prices: ResearchValue[]; earnings_forecasts: ResearchValue[];
  target_price_statistics: Record<string, { currency: string; year: number | null; count: number; min: number; max: number; mean: number; median: number; citations: string[] }>;
  timeline: { date: string; institution: string; report_id: string; claims: ResearchClaim[] }[];
  citations: ResearchCitation[]; reports: ResearchReport[];
  errors: { provider?: string; report_id?: string; stage: string; error: string }[];
  coverage: { discovered: number; unique_reports: number; duplicates: number; full_text: number;
    abstract_only: number; failed: number; out_of_period: number; evidence_coverage: number;
    source_diversity: number; source_agreement: number | null; time_coverage: number;
    level: 'HIGH' | 'MEDIUM' | 'LOW'; discovery_complete: boolean; formulas: Record<string, string> };
  limitations: string[]; metrics: Record<string, unknown>;
}
export interface ResearchTask { task_id: string; ticker: string; status: string; progress: { completed: number; total: number }; result: ResearchIntelligence | null; errors: ResearchIntelligence['errors'] }
export interface ResearchOptions { period: ResearchPeriod; start?: string; end?: string; refresh_discovery?: boolean; regenerate_summary?: boolean; use_llm?: boolean }

const BASE = 'http://localhost:8000/api/research/intelligence';

export function safeResearchLink(url: string): string | undefined {
  try {
    const parsed = new URL(url);
    if (!['https:', 'http:'].includes(parsed.protocol) || parsed.username || parsed.password) return;
    return parsed.toString();
  } catch { return; }
}

async function request<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
  const response = await fetch(BASE + path, { signal, method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `研报请求失败 (${response.status})`);
  return data;
}

export const reportIntelligenceApi = {
  start: (query: string, options: ResearchOptions, signal?: AbortSignal) => request<ResearchTask>(`/stocks/${encodeURIComponent(query)}/refresh`, signal, options),
  task: (taskId: string, signal?: AbortSignal) => request<ResearchTask>(`/tasks/${encodeURIComponent(taskId)}`, signal),
};
