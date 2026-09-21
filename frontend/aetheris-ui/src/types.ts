export interface NetWorthData {
  net_worth_usd: number;
  net_worth_cop: number;
  exchange_rate: number;
}

export interface SavingsRateData {
  savings_rate_pct: number;
  net_savings: number;
  monthly_income: number;
  monthly_expenses: number;
  status: 'OPTIMAL' | 'MODERATE' | 'DEFICIT';
}

export interface RiskMetrics {
  beta: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  annualized_volatility_pct?: number;
}

export interface TreemapChildItem {
  ticker: string;
  name: string;
  country: string;
  value_usd: number;
  allocation_pct: number;
}

export interface TreemapSector {
  name: string;
  value: number;
  items: TreemapChildItem[];
}

export interface TreemapCategory {
  name: string;
  value: number;
  percentage: number;
  children: TreemapSector[];
}

export interface EvolutionPoint {
  date: string;
  portfolio_growth: number;
  benchmark_growth: number;
  alpha_spread: number;
  portfolio_usd: number;
}

export interface DailyQuota {
  date: string;
  used_requests: number;
  max_quota: number;
  remaining_requests: number;
  is_quota_exhausted: boolean;
}

export interface GeopoliticalRisk {
  region: string;
  active_risk_score: number;
  anomaly_alert: boolean | number;
  headline?: string;
  last_assessed?: string;
}

export interface DashboardSummary {
  kpis: {
    net_worth: NetWorthData;
    savings_rate: SavingsRateData;
    twr_pct: number;
    mwr_pct: number;
    risk_metrics: RiskMetrics;
  };
  allocation_treemap: TreemapCategory[];
  temporal_evolution: EvolutionPoint[];
  geopolitical_risk: GeopoliticalRisk[];
  daily_api_quota: DailyQuota;
}

export interface Asset {
  ticker: string;
  name: string;
  asset_type: string;
  sector: string;
  country: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  currency: string;
  is_watchlist: boolean | number;
  logo_url?: string;
  target_allocation_pct?: number;
  unrealized_pnl_pct?: number;
  unrealized_pnl_usd?: number;
  market_value_usd?: number;
}

export interface InvestmentThesis {
  id: string;
  ticker: string;
  asset_name?: string;
  current_price?: number;
  asset_type?: string;
  sector?: string;
  thesis_text: string;
  valuation_grade: number;
  timing_context: string;
  safety_margin: number;
  checklist_passed: boolean | number;
  criteria_details: {
    knows_business_model: boolean;
    debt_ebitda_healthy: boolean;
    margin_safety_above_20: boolean;
    timing_not_overbought: boolean;
    emotional_bias_checked: boolean;
  };
}

export interface ChecklistItem {
  id: string;
  title: string;
  value: string;
  status: 'GREEN' | 'ORANGE' | 'RED';
  message: string;
}

export interface ProjectionTimelineMonth {
  month: number;
  projected_income: number;
  projected_expenses: number;
  monthly_net: number;
  cumulative_savings: number;
  total_liquidity: number;
}

export interface PanoramaData {
  monthly_net_savings: number;
  runway_months: number;
  projections_summary: {
    '3_months_net': number;
    '6_months_net': number;
    '12_months_net': number;
  };
  monthly_timeline: ProjectionTimelineMonth[];
  checklist: ChecklistItem[];
}

export interface BudgetBakersMapping {
  id: string;
  bb_category_name: string;
  local_category: string;
  flow_type: 'INCOME' | 'EXPENSE' | 'TRANSFER';
  is_active: boolean | number;
}
