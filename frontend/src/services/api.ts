import type {
  Account,
  Asset,
  BackupResult,
  BackupValidation,
  Budget,
  BudgetBakersMapping,
  BudgetBakersPreview,
  BudgetBakersStatus,
  Category,
  CsvImportResult,
  DashboardSummary,
  DataSourceInfo,
  InvestmentThesis,
  InvestmentOperation,
  PanoramaData,
  MonthlyReview,
  MarketDataSyncResult,
  RecurringRule,
  ReconciliationSummary,
  SourceMapping,
  Transaction,
  UnderstandSummary,
  WealthData
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

async function readJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || fallbackMessage || `HTTP error ${response.status}`);
  }
  return response.json();
}

export async function fetchDashboard(exchangeRate: number = 4050): Promise<DashboardSummary> {
  const res = await fetch(`${API_BASE}/dashboard?exchange_rate=${exchangeRate}`);
  return readJson<DashboardSummary>(res, 'Error al cargar el dashboard.');
}

export async function fetchPanorama(): Promise<PanoramaData> {
  const res = await fetch(`${API_BASE}/panorama`);
  return readJson<PanoramaData>(res, 'Error al cargar panorama.');
}

export async function fetchAssets(): Promise<Asset[]> {
  const res = await fetch(`${API_BASE}/assets`);
  return readJson<Asset[]>(res, 'Error al cargar activos.');
}

export async function saveAsset(asset: Partial<Asset>): Promise<Asset> {
  const res = await fetch(`${API_BASE}/assets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(asset)
  });
  return readJson<Asset>(res, 'Error al guardar activo.');
}

export async function deleteAsset(ticker: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/assets/${encodeURIComponent(ticker)}`, { method: 'DELETE' });
  return readJson<unknown>(res, 'Error al eliminar activo.');
}

export async function fetchAccounts(): Promise<Account[]> {
  const res = await fetch(`${API_BASE}/accounts`);
  return readJson<Account[]>(res, 'Error al cargar cuentas.');
}

export async function saveAccount(account: Partial<Account>): Promise<Account> {
  const res = await fetch(`${API_BASE}/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(account)
  });
  return readJson<Account>(res, 'Error al guardar cuenta.');
}

export async function deleteAccount(id: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/accounts/${encodeURIComponent(id)}`, { method: 'DELETE' });
  return readJson<unknown>(res, 'Error al eliminar cuenta.');
}

export async function fetchTransactions(): Promise<Transaction[]> {
  const res = await fetch(`${API_BASE}/transactions?limit=200`);
  return readJson<Transaction[]>(res, 'Error al cargar transacciones.');
}

export async function saveTransaction(transaction: Partial<Transaction>): Promise<Transaction> {
  const res = await fetch(`${API_BASE}/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(transaction)
  });
  return readJson<Transaction>(res, 'Error al guardar transaccion.');
}

export async function deleteTransaction(id: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/transactions/${encodeURIComponent(id)}`, { method: 'DELETE' });
  return readJson<unknown>(res, 'Error al eliminar transaccion.');
}

export async function fetchCategories(): Promise<Category[]> {
  const res = await fetch(`${API_BASE}/categories`);
  return readJson<Category[]>(res, 'Error al cargar categorias.');
}

export async function fetchDataSource(): Promise<DataSourceInfo> {
  const res = await fetch(`${API_BASE}/data-source`);
  return readJson<DataSourceInfo>(res, 'Error al leer fuente de datos.');
}

export async function previewTransactionsCsv(content: string): Promise<CsvImportResult> {
  const res = await fetch(`${API_BASE}/import/transactions/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  });
  return readJson<CsvImportResult>(res, 'Error al previsualizar CSV.');
}

export async function importTransactionsCsv(content: string): Promise<CsvImportResult> {
  const res = await fetch(`${API_BASE}/import/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  });
  return readJson<CsvImportResult>(res, 'Error al importar CSV.');
}

export async function exportBackup(): Promise<BackupResult> {
  const res = await fetch(`${API_BASE}/backup`);
  return readJson<BackupResult>(res, 'Error al exportar backup.');
}

export async function validateBackup(path: string): Promise<BackupValidation> {
  const res = await fetch(`${API_BASE}/backup/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  });
  return readJson<BackupValidation>(res, 'Error al validar backup.');
}

export async function restoreBackup(path: string): Promise<BackupResult> {
  const res = await fetch(`${API_BASE}/backup/restore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path })
  });
  return readJson<BackupResult>(res, 'Error al restaurar backup.');
}

export async function fetchTheses(): Promise<InvestmentThesis[]> {
  const res = await fetch(`${API_BASE}/theses`);
  return readJson<InvestmentThesis[]>(res, 'Error al cargar tesis.');
}

export async function saveThesis(thesis: Partial<InvestmentThesis>): Promise<unknown> {
  const res = await fetch(`${API_BASE}/theses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(thesis)
  });
  return readJson<unknown>(res, 'Error al guardar la tesis.');
}

export async function simulatePurchase(ticker: string, targetAmountUsd: number): Promise<unknown> {
  const res = await fetch(`${API_BASE}/simulate-purchase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, target_amount_usd: targetAmountUsd })
  });
  return readJson<unknown>(res, 'Operacion bloqueada por el Filtro Humano.');
}

export async function fetchBudgetBakersMappings(): Promise<BudgetBakersMapping[]> {
  const res = await fetch(`${API_BASE}/budgetbakers/mappings`);
  return readJson<BudgetBakersMapping[]>(res, 'Error al cargar mappings.');
}

export async function updateBudgetBakersMapping(
  mappingId: string,
  localCategory: string,
  isActive: boolean
): Promise<unknown> {
  const res = await fetch(`${API_BASE}/budgetbakers/mappings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mapping_id: mappingId, local_category: localCategory, is_active: isActive })
  });
  return readJson<unknown>(res, 'Error al actualizar mapping.');
}

export async function triggerBudgetBakersSync(forceRefresh: boolean = false): Promise<unknown> {
  const res = await fetch(`${API_BASE}/budgetbakers/sync?force_refresh=${forceRefresh}`, {
    method: 'POST'
  });
  return readJson<unknown>(res, 'La sincronización demo ya no está disponible.');
}

export async function fetchBudgetBakersStatus(): Promise<BudgetBakersStatus> {
  const res = await fetch(`${API_BASE}/budgetbakers/status`);
  return readJson<BudgetBakersStatus>(res, 'Error al leer estado de Wallet.');
}

export async function testBudgetBakersConnection(): Promise<unknown> {
  const res = await fetch(`${API_BASE}/budgetbakers/test`, { method: 'POST' });
  return readJson<unknown>(res, 'Error al probar Wallet.');
}

export async function previewBudgetBakersImport(): Promise<BudgetBakersPreview> {
  const res = await fetch(`${API_BASE}/budgetbakers/preview`, { method: 'POST' });
  return readJson<BudgetBakersPreview>(res, 'Error al previsualizar Wallet.');
}

export async function importBudgetBakersPreview(preview: BudgetBakersPreview): Promise<BudgetBakersPreview> {
  const res = await fetch(`${API_BASE}/budgetbakers/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ accounts: preview.accounts, transactions: preview.transactions, meta: preview.meta })
  });
  return readJson<BudgetBakersPreview>(res, 'Error al importar Wallet.');
}

export async function fetchReconciliation(): Promise<ReconciliationSummary> {
  const res = await fetch(`${API_BASE}/reconciliation?source=BUDGETBAKERS`);
  return readJson<ReconciliationSummary>(res, 'Error al cargar reconciliacion.');
}

export async function saveSourceMapping(mapping: SourceMapping): Promise<SourceMapping> {
  const res = await fetch(`${API_BASE}/source-mappings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(mapping)
  });
  return readJson<SourceMapping>(res, 'Error al guardar mapping.');
}

export async function fetchUnderstand(period: string = 'current_month'): Promise<UnderstandSummary> {
  const res = await fetch(`${API_BASE}/understand?period=${encodeURIComponent(period)}`);
  return readJson<UnderstandSummary>(res, 'Error al cargar analisis.');
}

export async function fetchBudgets(): Promise<Budget[]> {
  const res = await fetch(`${API_BASE}/budgets`);
  return readJson<Budget[]>(res, 'Error al cargar presupuestos.');
}

export async function saveBudget(budget: Partial<Budget>): Promise<Budget> {
  const res = await fetch(`${API_BASE}/budgets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(budget)
  });
  return readJson<Budget>(res, 'Error al guardar presupuesto.');
}

export async function deleteBudget(id: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/budgets/${encodeURIComponent(id)}`, { method: 'DELETE' });
  return readJson<unknown>(res, 'Error al eliminar presupuesto.');
}

export async function fetchRecurring(): Promise<RecurringRule[]> {
  const res = await fetch(`${API_BASE}/recurring`);
  return readJson<RecurringRule[]>(res, 'Error al cargar recurrentes.');
}

export async function updateRecurringStatus(id: string, status: RecurringRule['status']): Promise<RecurringRule> {
  const res = await fetch(`${API_BASE}/recurring/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  });
  return readJson<RecurringRule>(res, 'Error al actualizar recurrente.');
}

export async function fetchMonthlyReview(period?: string): Promise<MonthlyReview> {
  const suffix = period ? `?period=${encodeURIComponent(period)}` : '';
  const res = await fetch(`${API_BASE}/monthly-review${suffix}`);
  return readJson<MonthlyReview>(res, 'Error al cargar revision mensual.');
}

export async function saveMonthlyReviewSnapshot(period?: string): Promise<unknown> {
  const suffix = period ? `?period=${encodeURIComponent(period)}` : '';
  const res = await fetch(`${API_BASE}/monthly-review/snapshot${suffix}`, { method: 'POST' });
  return readJson<unknown>(res, 'Error al guardar cierre mensual.');
}

export async function importBudgetBakersPlan(preview: BudgetBakersPreview): Promise<unknown> {
  const res = await fetch(`${API_BASE}/budgetbakers/import-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ budgets: preview.budgets || [], standing_orders: preview.standing_orders || [] })
  });
  return readJson<unknown>(res, 'Error al importar plan Wallet.');
}

export async function fetchWealth(contributionUsd: number = 0, benchmarkKey?: string): Promise<WealthData> {
  const params = new URLSearchParams({ contribution_usd: String(contributionUsd) });
  if (benchmarkKey) params.set('benchmark_key', benchmarkKey);
  const res = await fetch(`${API_BASE}/wealth?${params.toString()}`);
  return readJson<WealthData>(res, 'Error al cargar Wealth.');
}

export async function importValuationsCsv(content: string, source: string = 'MANUAL'): Promise<CsvImportResult> {
  const res = await fetch(`${API_BASE}/valuations/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, source })
  });
  return readJson<CsvImportResult>(res, 'Error al importar valoraciones.');
}

export async function importBenchmarkCsv(content: string, benchmarkKey: string, label?: string): Promise<CsvImportResult> {
  const res = await fetch(`${API_BASE}/benchmarks/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, benchmark_key: benchmarkKey, label })
  });
  return readJson<CsvImportResult>(res, 'Error al importar benchmark.');
}

export async function saveInvestmentOperation(operation: Partial<InvestmentOperation>): Promise<InvestmentOperation> {
  const res = await fetch(`${API_BASE}/investment-ledger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(operation)
  });
  return readJson<InvestmentOperation>(res, 'Error al guardar operación de inversión.');
}

export async function deleteInvestmentOperation(id: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}/investment-ledger/${encodeURIComponent(id)}`, { method: 'DELETE' });
  return readJson<unknown>(res, 'Error al eliminar operación de inversión.');
}

export async function previewInvestmentLedgerCsv(content: string, source: string = 'CSV'): Promise<CsvImportResult> {
  const res = await fetch(`${API_BASE}/investment-ledger/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, source })
  });
  return readJson<CsvImportResult>(res, 'Error al previsualizar ledger.');
}

export async function importInvestmentLedgerCsv(content: string, source: string = 'CSV'): Promise<CsvImportResult> {
  const res = await fetch(`${API_BASE}/investment-ledger/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, source })
  });
  return readJson<CsvImportResult>(res, 'Error al importar ledger.');
}

export async function saveOpeningPosition(position: {
  ticker: string;
  opened_at: string;
  quantity: number;
  unit_cost?: number;
  total_cost?: number;
  currency: string;
  notes?: string;
}): Promise<unknown> {
  const res = await fetch(`${API_BASE}/opening-positions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(position)
  });
  return readJson<unknown>(res, 'Error al guardar posición inicial.');
}

export async function setPositionAuthority(ticker: string, authorityState: string, notes: string = ''): Promise<unknown> {
  const res = await fetch(`${API_BASE}/position-authority`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, authority_state: authorityState, notes })
  });
  return readJson<unknown>(res, 'Error al actualizar autoridad de posición.');
}

export async function syncMarketData(benchmarkSymbol?: string): Promise<MarketDataSyncResult> {
  const res = await fetch(`${API_BASE}/market-data/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ benchmark_symbol: benchmarkSymbol || undefined })
  });
  return readJson<MarketDataSyncResult>(res, 'Error al actualizar datos de mercado.');
}
