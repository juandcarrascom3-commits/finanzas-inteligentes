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
  beta: number | null;
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  annualized_volatility_pct?: number;
  status?: Record<string, string>;
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
    twr_pct: number | null;
    mwr_pct: number | null;
    risk_metrics: RiskMetrics;
  };
  allocation_treemap: TreemapCategory[];
  temporal_evolution: EvolutionPoint[];
  geopolitical_risk: GeopoliticalRisk[];
  daily_api_quota: DailyQuota;
  data_source?: DataSourceInfo;
  cashflow?: CashflowSummary;
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
  source?: DataSource;
  unrealized_pnl_pct?: number;
  unrealized_pnl_usd?: number;
  market_value_usd?: number;
}

export type DataSource = 'DEMO' | 'MANUAL' | 'CSV' | 'BUDGETBAKERS' | 'ETORO' | 'GOOGLE' | 'MARKET_DATA';

export interface DataSourceInfo {
  db_path: string;
  mode: 'DEMO' | 'REAL';
  profile?: 'DEMO' | 'PERSONAL';
  seed_demo: boolean;
  schema?: {
    latest_version?: string | null;
    migrations?: Array<{ version: string; filename: string; checksum?: string; applied_at?: string }>;
  };
}

export interface BackupValidation {
  valid: boolean;
  path: string;
  tables: string[];
  latest_version?: string | null;
  migrations: Array<{ version: string; filename: string; applied_at?: string }>;
}

export interface BackupResult {
  generated_at?: string;
  db_backup_path?: string;
  status?: string;
  restored_from?: string;
  pre_restore_backup_path?: string | null;
  validation?: BackupValidation;
}

export interface CashflowSummary {
  income: number;
  expenses: number;
  cashflow: number;
}

export interface Account {
  id: string;
  name: string;
  account_type: string;
  currency: string;
  opening_balance: number;
  current_balance: number;
  source: DataSource;
  external_id?: string;
  last_synced_at?: string;
  is_active: boolean | number;
}

export interface Transaction {
  id: string;
  account_id?: string;
  account_name?: string;
  amount: number;
  category: string;
  date: string;
  description: string;
  currency: string;
  source: DataSource;
  external_id?: string;
}

export interface Category {
  id: string;
  name: string;
  flow_type: 'INCOME' | 'EXPENSE' | 'TRANSFER';
  source: DataSource;
}

export interface Budget {
  id: string;
  category: string;
  monthly_limit: number;
  currency: string;
  source: DataSource;
  period: string;
  is_active: boolean | number;
  external_id?: string;
}

export interface CsvImportResult {
  accepted_rows: Partial<Transaction>[];
  rejected_rows: Array<{ row_number: number; row: Record<string, string>; error: string }>;
  accepted_count: number;
  rejected_count: number;
  imported_count?: number;
  duplicate_count?: number;
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

export interface BudgetBakersStatus {
  source: 'BUDGETBAKERS';
  configured: boolean;
  status: string;
  message?: string;
  last_success_at?: string;
  last_error?: string;
  last_data_change_at?: string;
  sync_in_progress?: string;
}

export interface BudgetBakersPreview {
  source: 'BUDGETBAKERS';
  accounts_detected: number;
  new_accounts: number;
  existing_accounts: number;
  records_found: number;
  accepted_rows: Partial<Transaction>[];
  rejected_rows: Array<{ row_number: number; row: Record<string, unknown>; error: string }>;
  accepted_count: number;
  rejected_count: number;
  duplicate_count: number;
  new_transaction_count: number;
  unmapped_accounts: string[];
  unknown_currencies: string[];
  date_range: { from?: string | null; to?: string | null };
  accounts: Partial<Account>[];
  transactions: Partial<Transaction>[];
  budgets?: Partial<Budget>[];
  standing_orders?: Partial<RecurringRule>[];
  meta: Record<string, unknown>;
  imported_count?: number;
  account_imported_count?: number;
  updated_count?: number;
}

export interface SourceMapping {
  id?: string;
  source: DataSource;
  external_type: 'account' | 'category';
  external_id: string;
  external_name?: string;
  local_id?: string;
  local_type?: string;
  is_active?: boolean | number;
}

export interface ReconciliationSummary {
  source: DataSource;
  unmapped_accounts: Array<{ external_id: string; external_name: string; local_id?: string }>;
  unmapped_categories: Array<{ external_name: string; count: number }>;
  no_category_count: number;
  transaction_count: number;
}

export interface UnderstandSummary {
  what_changed: {
    period: string;
    range: { from: string; to: string };
    facts: { income: number; expenses: number; cashflow: number; savings_rate_pct: number };
    variation: { income: number; expenses: number; cashflow: number; savings_rate_pct: number };
    category_changes: Array<{ category: string; delta: number; current: number; previous: number }>;
    largest_transactions: Transaction[];
    interpretation: string[];
  };
  recurring: Array<{ merchant: string; category: string; typical_amount: number; frequency: string; confidence: string; occurrences: number; last_seen: string; next_expected?: string }>;
  budget_burn: Array<{ category: string; budget: number; spent: number; remaining: number; spent_pct: number; month_elapsed_pct: number; projected_close: number; status: string }>;
  cashflow_forecast: { starting_balance: number; expected_inflows: number; expected_outflows: number; projected_balance: number; uncertainty: string; range: { from: string; to: string } };
  action_items: Array<{ type: string; severity: string; title: string; why: string; action: string }>;
  reconciliation: ReconciliationSummary;
}

export interface RecurringRule {
  id: string;
  merchant: string;
  category: string;
  account_id?: string;
  typical_amount: number;
  frequency: string;
  status: 'detected' | 'confirmed' | 'rejected' | 'ignored';
  source: string;
  external_id?: string;
  next_expected?: string;
  last_seen?: string;
}

export interface MonthlyReview {
  period: string;
  range: { from: string; to: string };
  facts: {
    income: number;
    expenses: number;
    cashflow: number;
    savings_rate_pct: number;
    available_net_worth: number;
    previous_income: number;
    previous_expenses: number;
    previous_cashflow: number;
  };
  budget_variances: Array<{ category: string; budget: number; spent: number; variance: number; variance_pct: number; status: string; source: string }>;
  recurring: { confirmed: RecurringRule[]; detected: Array<{ merchant: string; typical_amount: number; confidence: string; frequency: string; next_expected?: string }> };
  upcoming_obligations: Array<{ merchant: string; amount: number; category: string; date: string; source: string }>;
  forecast: UnderstandSummary['cashflow_forecast'];
  action_items: Array<{ type: string; severity: string; reason: string; action: string; reference: Record<string, unknown> }>;
}

export interface MetricState {
  status: 'AVAILABLE' | 'INSUFFICIENT_DATA';
  value_pct?: number | null;
  value?: number | null;
  value_usd?: number | null;
  reason?: string | null;
}

export interface WealthData {
  summary: { total_value_usd: number; unrealized_pnl_usd: number; unrealized_pnl_status: string };
  history: {
    status: string;
    policy: string;
    series: Array<{ date: string; portfolio_value_usd: number; external_cash_flow_usd: number; coverage_pct: number }>;
    data_quality: { valuation_dates: number; missing_valuation_dates: number; coverage_pct: number };
  };
  performance: {
    twr: MetricState;
    mwr: MetricState;
    cumulative_return: MetricState;
    period_return: MetricState;
    realized_pnl: MetricState;
    risk: { volatility: MetricState; max_drawdown: MetricState; sharpe: MetricState; beta: MetricState };
  };
  allocation: {
    total_value_usd: number;
    dimensions: Record<string, Array<{ name: string; value_usd: number; allocation_pct: number }>>;
    holdings: Array<{ ticker: string; value_usd: number; allocation_pct: number }>;
  };
  concentration: {
    top_asset?: { ticker: string; allocation_pct: number; value_usd: number };
    top3_pct: number;
    top5_pct: number;
    alerts: Array<{ type: string; severity: string; message: string; action: string }>;
  };
  data_quality: {
    history_coverage_pct: number;
    assets_with_history: number;
    total_assets: number;
    issues: Array<{ type: string; ticker: string; message: string; action: string }>;
  };
  attribution: {
    status: string;
    reason?: string;
    initial_value_usd?: number;
    final_value_usd?: number;
    change_usd?: number;
    top_winners?: Array<{ ticker: string; contribution_usd: number }>;
    top_detractors?: Array<{ ticker: string; contribution_usd: number }>;
  };
  rebalancing: {
    status: string;
    reason?: string | null;
    traditional: Array<{ ticker: string; current_pct: number; target_pct: number; drift_pct: number; trade_usd: number; contribution_usd?: number }>;
    new_contribution: Array<{ ticker: string; contribution_usd: number; drift_pct: number; target_pct: number; current_pct: number }>;
    contribution_usd: number;
  };
  benchmark: {
    status: string;
    reason?: string;
    portfolio_return_pct?: number;
    benchmark_return_pct?: number;
    excess_return_pct?: number | null;
    coverage?: { portfolio_observations: number; benchmark_observations: number; aligned_observations: number; common_period?: { from: string; to: string } | null };
    beta?: MetricState;
  };
  market_data: {
    provider: string;
    benchmark_symbol?: string;
    last_sync_at?: string;
    last_success_at?: string;
    last_error?: string;
    updated_assets: number;
    fx_pairs: number;
    stale_tickers: string[];
    missing_tickers: string[];
    status: string;
    provider_health: 'AVAILABLE' | 'DEGRADED' | 'OFFLINE';
    pricing_status: string;
    price_policy: string;
    history_policy: string;
    coverage: {
      rows: Array<{
        ticker: string;
        provider: string;
        provider_symbol?: string | null;
        symbol_status: string;
        mapping_source: string;
        current_price: number;
        currency: string;
        freshness: string;
        price_source: string;
        price_authority: string;
        history_count: number;
        fx_status: string;
        status: string;
      }>;
      summary: {
        holdings_total: number;
        holdings_ok: number;
        fresh_value_pct: number;
        stale_count: number;
        unresolved_symbols: string[];
        missing_fx: string[];
        benchmark_status: string;
        benchmark_observations: number;
      };
    };
    issues: Array<{ type: string; ticker?: string; message: string; action: string }>;
    config: Record<string, unknown>;
  };
  ledger: {
    operations: InvestmentOperation[];
    positions: Array<{ ticker: string; quantity: number; remaining_cost_basis: number; avg_cost: number; currency: string }>;
    open_lots: Array<{ ticker: string; buy_transaction_id: string; acquired_at: string; original_quantity: number; remaining_quantity: number; unit_cost: number; total_cost: number; currency: string }>;
    realized_trades: Array<{ sell_transaction_id: string; ticker: string; occurred_at: string; quantity: number; proceeds: number; cost_basis: number; fee: number; realized_pnl: number; currency: string }>;
    issues: Array<{ type: string; ticker?: string; message: string; action: string }>;
    reconciliation: {
      rows: Array<{ ticker: string; registered_quantity: number; derived_quantity: number; quantity_diff: number; registered_avg_price: number; derived_avg_price: number; avg_price_diff: number; status: 'MATCH' | 'QUANTITY_MISMATCH' | 'COST_BASIS_MISMATCH' | 'BOTH_MISMATCH' | 'INSUFFICIENT_HISTORY'; coverage: string; authority_state: string; source: string }>;
      issues: Array<{ type: string; ticker: string; message: string; action: string }>;
    };
    effective_holdings: { status: string; holdings: Array<Asset & { provenance: string; reconciliation_state: string; coverage: string }> };
    authority: Array<{ ticker: string; account_id?: string; authority_state: string; notes?: string }>;
    opening_positions: Array<{ id: string; ticker: string; opened_at: string; quantity: number; unit_cost: number; total_cost: number; currency: string; source: DataSource; notes?: string }>;
    total_return_breakdown: {
      status: string;
      realized_pnl: { total_realized_pnl: number; status: string };
      unrealized_pnl: { total_unrealized_pnl: number; status: string };
      dividends: number;
      interest: number;
      fees: number;
      external_contributions: number;
    };
  };
  action_items: Array<{ type: string; severity: string; title: string; why: string; action: string }>;
}

export interface MarketDataSyncResult {
  provider: string;
  mode: string;
  status: string;
  started_at: string;
  completed_at: string;
  assets: Array<{ ticker: string; status: string; history_rows?: number; error?: string }>;
  fx: Array<{ pair: string; status: string; rows?: number; error?: string }>;
  benchmark?: { symbol: string; status: string; rows?: number; error?: string } | null;
  errors: Array<{ symbol: string; error: string }>;
}

export interface InvestmentOperation {
  id: string;
  occurred_at: string;
  ticker?: string;
  account_id?: string;
  operation_type: 'CONTRIBUTION' | 'WITHDRAWAL' | 'BUY' | 'SELL' | 'DIVIDEND' | 'INTEREST' | 'FEE' | 'TRANSFER_IN' | 'TRANSFER_OUT' | 'SPLIT' | 'ADJUSTMENT';
  quantity: number;
  price: number;
  amount: number;
  fee: number;
  currency: string;
  source: DataSource;
  external_id?: string;
  notes?: string;
  metadata?: Record<string, unknown>;
}
