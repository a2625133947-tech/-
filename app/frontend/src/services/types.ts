// Shared types for API requests and responses
export enum ModelProvider {
  OPENAI = 'OpenAI',
  ANTHROPIC = 'Anthropic',
  GROQ = 'Groq',
  OLLAMA = 'Ollama',
}

export interface AgentModelConfig {
  agent_id: string;
  model_name?: string;
  model_provider?: ModelProvider;
}

export interface GraphNode {
  id: string;
  type?: string;
  data?: any;
  position?: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  data?: any;
}

export interface PortfolioPosition {
  ticker: string;
  quantity: number;
  trade_price: number;
}

// Base interface for shared fields between HedgeFundRequest and BacktestRequest
export interface BaseHedgeFundRequest {
  flow_id?: number;
  tickers: string[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
  agent_models?: AgentModelConfig[];
  model_name?: string;
  model_provider?: ModelProvider;
  margin_requirement?: number;
  portfolio_positions?: PortfolioPosition[];
}

export interface HedgeFundRequest extends BaseHedgeFundRequest {
  include_research?: boolean;
  research_period?: 'week' | 'month' | 'year';
  end_date?: string;
  start_date?: string;
  initial_cash?: number;
}

export interface BacktestRequest extends BaseHedgeFundRequest {
  start_date: string;
  end_date: string;
  initial_capital?: number;
}

export interface BacktestDayResult {
  date: string;
  portfolio_value: number;
  cash: number;
  decisions: Record<string, any>;
  executed_trades: Record<string, number>;
  analyst_signals: Record<string, any>;
  current_prices: Record<string, number>;
  long_exposure: number;
  short_exposure: number;
  gross_exposure: number;
  net_exposure: number;
  long_short_ratio: number | null;
}

export interface BacktestPerformanceMetrics {
  sharpe_ratio?: number;
  sortino_ratio?: number;
  max_drawdown?: number;
  max_drawdown_date?: string;
  long_short_ratio?: number;
  gross_exposure?: number;
  net_exposure?: number;
}

export type FinancialReportType =
  | 'annual_report'
  | 'semi_annual_report'
  | 'q1_report'
  | 'q3_report'
  | 'other_report';

export interface FinancialReportReference {
  source_id: string;
  title: string;
  report_type: FinancialReportType | string;
  publish_date: string;
  ticker: string;
  company_name: string;
  source: string;
  source_name: string;
  source_url: string;
  pdf_url?: string | null;
  announcement_id?: string | null;
  org_id?: string | null;
} 
