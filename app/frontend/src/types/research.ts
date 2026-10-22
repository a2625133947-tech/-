export interface FactorContributionDTO {
  factor_id: string;
  display_name: string;
  version: string;
  role: 'core' | 'supporting' | 'optional';
  role_display: string;
  score: number | null;
  weight: number;
  weighted_contribution: number | null;
  status: string;
  factor_type: string;
  raw_value: number | null;
  raw_unit: string;
  limitations: string[];
}

export interface SignalExplanationDTO {
  signal: string;
  signal_display: string;
  strategy_score: number | null;
  bullish_threshold: number;
  bearish_threshold: number;
  policy_style: string;
  gate_id: string | null;
  gate_passed: boolean | null;
  gate_checks: string[];
  reason_code: string;
  signal_reason: string;
}

export interface ConfidenceBreakdownDTO {
  final_confidence: number;
  maximum_possible: number;
  core_coverage: number;
  supporting_coverage: number;
  optional_coverage: number;
  coverage_score: number;
  evidence_quality: number;
  unconstrained_confidence: number;
  strategy_evidence_cap: number | null;
  proxy_cap: number | null;
  critical_capability_cap: number | null;
  active_cap_name: string | null;
  active_cap_value: number | null;
  applied_caps: Record<string, number>;
  notice: string;
}

export interface LegacyComparisonDTO {
  legacy_signal: string;
  legacy_signal_display: string;
  legacy_confidence: number;
  legacy_key_metrics: Record<string, any>;
  legacy_strengths: string[];
  legacy_risks: string[];
  new_signal: string;
  new_signal_display: string;
  new_confidence: number;
  signal_changed: boolean;
  confidence_changed: boolean;
  core_difference: string;
  research_disclaimer: string;
}

export interface ShadowInvestorCardDTO {
  profile_id: string;
  display_name: string;
  profile_version: string;
  lens: string;
  signal: string;
  signal_display: string;
  confidence: number;
  strategy_score: number | null;
  strategy_evidence_coverage: number;
  core_coverage: number;
  supporting_coverage: number;
  implemented_factor_coverage: number;
  status: 'READY' | 'NOT_READY';
  not_ready_reason?: string | null;
}

export interface ProductionDecisionDTO {
  mode: string;
  action: string;
  action_display: string;
  confidence: number;
  quantity: number;
  reasoning: string;
  notice: string;
}

export interface StockResearchOverviewDTO {
  ticker: string;
  stock_name: string;
  as_of: string;
  market_data_date: string | null;
  snapshot_id: string | null;
  snapshot_status: string;
  data_quality: string;
  production_decision: ProductionDecisionDTO;
  investor_cards: ShadowInvestorCardDTO[];
  not_ready_cards: ShadowInvestorCardDTO[];
  research_mode_banner: string;
}

export interface InvestorDetailDTO {
  profile_id: string;
  display_name: string;
  profile_version: string;
  description: string;
  time_horizon: string;
  signal: string;
  signal_display: string;
  confidence: number;
  confidence_semantics: string;
  strategy_score: number | null;
  data_coverage: Record<string, number>;
  factor_contributions: FactorContributionDTO[];
  signal_explanation: SignalExplanationDTO | null;
  confidence_breakdown: ConfidenceBreakdownDTO | null;
  strengths: string[];
  risks: string[];
  known_missing_dimensions: string[];
  limitations: string[];
  legacy_comparison: LegacyComparisonDTO | null;
  status: 'READY' | 'NOT_READY';
  not_ready_reason?: string | null;
}

export interface CorpusHealthSummaryDTO {
  generated_at: string;
  snapshot_count: number;
  ticker_count: number;
  date_range: [string, string] | null;
  partial_runs_count: number;
  degraded_snapshots_count: number;
  signal_distribution: Record<string, Record<string, number>>;
  confidence_distribution: Record<string, Record<string, number>>;
  data_drift_warnings: Array<{ warning_type: string; message: string; severity?: string; details?: any }>;
  factor_drift_warnings: Array<{ factor_id: string; warning_type: string; message: string; details?: any }>;
  distribution_warnings: Array<{ profile_id: string; warning_type: string; message: string; details?: any }>;
  health_status: string;
}

export interface SnapshotItemDTO {
  snapshot_id: string;
  ticker: string;
  captured_at: string;
  as_of: string;
  market_data_date: string | null;
  quality_status: string;
  retention_tags: string[];
  evaluation_complete: boolean;
  run_status: string;
  evaluations_summary: Record<string, any>;
}
