import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { TopKpiRow } from './components/TopKpiRow';
import { CentralVisualSection } from './components/CentralVisualSection';
import { AssetListTab } from './components/tabs/AssetListTab';
import { InvestmentThesisTab } from './components/tabs/InvestmentThesisTab';
import { WealthTab } from './components/tabs/WealthTab';
import { PersonalDataTab } from './components/tabs/PersonalDataTab';
import { UnderstandTab } from './components/tabs/UnderstandTab';
import { PlanningTab } from './components/tabs/PlanningTab';
import {
  deleteBudget,
  deleteInvestmentOperation,
  deleteAccount,
  deleteAsset,
  deleteTransaction,
  exportBackup,
  fetchAccounts,
  fetchDashboard,
  fetchAssets,
  fetchCategories,
  fetchDataSource,
  fetchEtoroStatus,
  fetchFinancialEvents,
  fetchEtoroMappings,
  fetchTheses,
  fetchTransactions,
  fetchWealth,
  importBenchmarkCsv,
  importInvestmentLedgerCsv,
  importTransactionsCsv,
  importValuationsCsv,
  previewInvestmentLedgerCsv,
  previewTransactionsCsv,
  saveAccount,
  saveAsset,
  saveInvestmentOperation,
  saveOpeningPosition,
  saveThesis,
  saveTransaction,
  restoreBackup,
  runCalculator,
  simulatePurchase,
  fetchBudgetBakersStatus,
  fetchBudgets,
  fetchMonthlyReview,
  fetchRecurring,
  fetchReconciliation,
  fetchUnderstand,
  importBudgetBakersPlan,
  importBudgetBakersPreview,
  importEtoroPreview,
  importMappingConfig,
  exportMappingConfig,
  previewBudgetBakersImport,
  previewEtoroImport,
  saveSourceMapping,
  confirmEtoroMappings,
  markEtoroUnsupported,
  saveBudget,
  saveMonthlyReviewSnapshot,
  saveMarketDataConfig,
  savePriceAuthority,
  setPositionAuthority,
  saveFxRate,
  syncMarketData,
  saveSymbolMapping,
  testBudgetBakersConnection,
  testEtoroConnection,
  validateMappingConfig,
  updateRecurringStatus,
  validateBackup
} from './services/api';
import { Account, Category, DashboardSummary, DataSourceInfo, Asset, InvestmentThesis, Transaction, UnderstandSummary, Budget, RecurringRule, MonthlyReview, WealthData, FinancialEvent } from './types';
import { Compass, AlertTriangle, WalletCards, LineChart, Target } from 'lucide-react';

export const App: React.FC = () => {
  const [currency, setCurrency] = useState<'USD' | 'COP'>('USD');
  const [activeTab, setActiveTab] = useState<'overview' | 'plan' | 'invest' | 'datos'>('overview');
  const [privacyMode, setPrivacyModeState] = useState<boolean>(() => localStorage.getItem('finance_privacy_mode') === '1');
  const [understandPeriod, setUnderstandPeriod] = useState<string>('current_month');
  const [selectedTickerForSim, setSelectedTickerForSim] = useState<string | undefined>(undefined);

  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [dataSource, setDataSource] = useState<DataSourceInfo | undefined>(undefined);
  const [theses, setTheses] = useState<InvestmentThesis[]>([]);
  const [understand, setUnderstand] = useState<UnderstandSummary | null>(null);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [recurring, setRecurring] = useState<RecurringRule[]>([]);
  const [financialEvents, setFinancialEvents] = useState<FinancialEvent[]>([]);
  const [monthlyReview, setMonthlyReview] = useState<MonthlyReview | null>(null);
  const [wealth, setWealth] = useState<WealthData | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const exchangeRate = dashboard?.kpis?.net_worth?.exchange_rate || 4050;
  const formatMoney = (value: number | undefined, currencyCode?: string | null) => {
    if (privacyMode) return '••••';
    return `${currencyCode || currency} ${(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  };
  const hasCurrencySafeOverview = !!understand?.what_changed.primary_currency;

  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [dashData, assetsData, thesesData, accountsData, transactionsData, categoriesData, sourceData, understandData, budgetsData, recurringData, eventsData, reviewData, wealthData] = await Promise.all([
        fetchDashboard(exchangeRate),
        fetchAssets(),
        fetchTheses(),
        fetchAccounts(),
        fetchTransactions(),
        fetchCategories(),
        fetchDataSource(),
        fetchUnderstand(understandPeriod),
        fetchBudgets(),
        fetchRecurring(),
        fetchFinancialEvents(),
        fetchMonthlyReview(),
        fetchWealth()
      ]);
      setDashboard(dashData);
      setAssets(assetsData);
      setTheses(thesesData);
      setAccounts(accountsData);
      setTransactions(transactionsData);
      setCategories(categoriesData);
      setDataSource(sourceData);
      setUnderstand(understandData);
      setBudgets(budgetsData);
      setRecurring(recurringData);
      setFinancialEvents(eventsData.events);
      setMonthlyReview(reviewData);
      setWealth(wealthData);
    } catch (err: any) {
      console.error('Error loading data:', err);
      setErrorMsg('No se pudo conectar al servidor local. Verifique que el backend de FastAPI esté en ejecución.');
    } finally {
      setIsLoading(false);
    }
  }, [exchangeRate, understandPeriod]);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  const handleSelectAssetForSimulation = (ticker: string) => {
    setSelectedTickerForSim(ticker);
    setActiveTab('invest');
  };

  const handleSaveThesis = async (thesisData: Partial<InvestmentThesis>) => {
    await saveThesis(thesisData);
    const updatedTheses = await fetchTheses();
    setTheses(updatedTheses);
  };

  const handleSimulatePurchase = async (ticker: string, amountUsd: number) => {
    return await simulatePurchase(ticker, amountUsd);
  };

  const refreshWealth = async (contributionUsd: number = 0, benchmarkKey?: string) => {
    setWealth(await fetchWealth(contributionUsd, benchmarkKey));
    const updatedAssets = await fetchAssets();
    setAssets(updatedAssets);
    const updatedDashboard = await fetchDashboard(exchangeRate);
    setDashboard(updatedDashboard);
  };

  const refreshAfterMutation = async () => {
    await loadAllData();
  };

  const setPrivacyMode = (value: boolean) => {
    setPrivacyModeState(value);
    localStorage.setItem('finance_privacy_mode', value ? '1' : '0');
  };

  return (
    <div className="min-h-screen bg-[#080C15] text-gray-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* HEADER SECTION */}
      <Header
        currency={currency}
        setCurrency={setCurrency}
        exchangeRate={exchangeRate}
        onRefresh={loadAllData}
        isLoading={isLoading}
        privacyMode={privacyMode}
        setPrivacyMode={setPrivacyMode}
      />

      {/* ERROR BANNER */}
      {errorMsg && (
        <div className="max-w-7xl mx-auto px-4 lg:px-8 mt-4 w-full">
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-300 text-xs flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button
              onClick={loadAllData}
              className="px-2.5 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-200 font-mono text-[11px] rounded"
            >
              Reintentar
            </button>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 lg:px-8 mt-4 w-full">
        <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-200 text-xs">
          Fuente activa: <strong>{dataSource?.profile || dataSource?.mode || 'DEMO'}</strong>. MANUAL y CSV son datos personales locales; DEMO son datos semilla/simulados.
        </div>
      </div>

      {/* MAIN THREE-TIER CONTAINER */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-6 space-y-7">
        {activeTab === 'overview' && dashboard && (
          <>
            {/* TIER 1: TOP KPI ROW (High-Level Summary) */}
            <TopKpiRow
              netWorth={dashboard.kpis.net_worth}
              savingsRate={dashboard.kpis.savings_rate}
              twrPct={dashboard.kpis.twr_pct}
              mwrPct={dashboard.kpis.mwr_pct}
              riskMetrics={dashboard.kpis.risk_metrics}
              currency={currency}
              privacyMode={privacyMode}
            />

            {understand && (
              <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                  <div>
                    <h2 className="text-sm font-bold text-white">Overview inteligente</h2>
                    <p className="text-xs text-gray-400">Calculado desde datos locales persistidos. Sin IA.</p>
                  </div>
                  <div className={`text-[11px] font-bold px-2 py-1 rounded border w-fit ${
                    understand.data_confidence?.level === 'HIGH'
                      ? 'text-emerald-200 border-emerald-500/40 bg-emerald-500/10'
                      : understand.data_confidence?.level === 'LOW'
                        ? 'text-red-200 border-red-500/40 bg-red-500/10'
                        : 'text-amber-200 border-amber-500/40 bg-amber-500/10'
                  }`}>
                    Confianza: {understand.data_confidence?.level || 'MEDIUM'}
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="bg-gray-900/60 rounded-lg p-3">
                    <div className="text-gray-500">Cómo estoy</div>
                    <div className="text-white font-bold mt-1">
                      {hasCurrencySafeOverview
                        ? `Cashflow ${formatMoney(understand.what_changed.metrics?.net_cash_flow?.current, understand.what_changed.primary_currency)}`
                        : 'Múltiples monedas'}
                    </div>
                    <div className="text-gray-400 mt-1">
                      {hasCurrencySafeOverview ? `Ahorro ${understand.what_changed.metrics?.savings_rate?.current}%` : 'Ver detalle por moneda en Understand'}
                    </div>
                  </div>
                  <div className="bg-gray-900/60 rounded-lg p-3">
                    <div className="text-gray-500">Qué cambió</div>
                    <div className={`font-bold mt-1 ${(understand.what_changed.metrics?.net_cash_flow?.delta || 0) >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                      {hasCurrencySafeOverview
                        ? formatMoney(understand.what_changed.metrics?.net_cash_flow?.delta, understand.what_changed.primary_currency)
                        : `${Object.keys(understand.what_changed.by_currency || {}).length} monedas`}
                    </div>
                    <div className="text-gray-400 mt-1">vs periodo anterior</div>
                  </div>
                  <details className="bg-gray-900/60 rounded-lg p-3">
                    <summary className="text-gray-300 font-bold cursor-pointer">Por qué cambió</summary>
                    <div className="mt-2 space-y-1 text-gray-400">
                      {(understand.what_changed.explain?.reasons || understand.what_changed.interpretation).slice(0, 3).map((reason, index) => (
                        <div key={`${reason}-${index}`}>{reason}</div>
                      ))}
                      {understand.what_changed.category_contributors?.slice(0, 3).map((item) => (
                        <div key={item.category} className="flex justify-between border-t border-gray-800 pt-1">
                          <span>{item.category}</span>
                          <span className={item.delta > 0 ? 'text-red-300' : 'text-emerald-300'}>{formatMoney(item.delta, item.currency)}</span>
                        </div>
                      ))}
                    </div>
                  </details>
                </div>
              </section>
            )}

            {/* TIER 2: CENTRAL VISUAL SECTION (Asset Allocation & Temporal Evolution) */}
            <CentralVisualSection
              treemapData={dashboard.allocation_treemap}
              evolutionData={dashboard.temporal_evolution}
              currency={currency}
              exchangeRate={exchangeRate}
              privacyMode={privacyMode}
            />
            <UnderstandTab
              data={understand}
              period={understandPeriod}
              setPeriod={setUnderstandPeriod}
              privacyMode={privacyMode}
            />
          </>
        )}

        {/* TIER 3: BOTTOM TAB SECTION & GRANULAR CONTROLS */}
        <section className="space-y-4">
          {/* Tabs Navigation Bar */}
          <div className="flex items-center space-x-2 border-b border-gray-800 pb-2 overflow-x-auto">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'overview'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <Compass className="w-4 h-4" />
              <span>Overview</span>
            </button>

            <button
              onClick={() => setActiveTab('plan')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'plan'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <Target className="w-4 h-4" />
              <span>Plan</span>
            </button>

            <button
              onClick={() => setActiveTab('invest')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'invest'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <LineChart className="w-4 h-4" />
              <span>Invest</span>
            </button>

            <button
              onClick={() => setActiveTab('datos')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'datos'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <WalletCards className="w-4 h-4" />
              <span>Datos</span>
            </button>

          </div>

          {/* Active Tab Content Container */}
          <div className="pt-2">
            {activeTab === 'datos' && (
              <PersonalDataTab
                accounts={accounts}
                assets={assets}
                transactions={transactions}
                categories={categories}
                dataSource={dataSource}
                onSaveAccount={async (account) => { await saveAccount(account); await refreshAfterMutation(); }}
                onDeleteAccount={async (id) => { await deleteAccount(id); await refreshAfterMutation(); }}
                onSaveAsset={async (asset) => { await saveAsset(asset); await refreshAfterMutation(); }}
                onDeleteAsset={async (ticker) => { await deleteAsset(ticker); await refreshAfterMutation(); }}
                onSaveTransaction={async (transaction) => { await saveTransaction(transaction); await refreshAfterMutation(); }}
                onDeleteTransaction={async (id) => { await deleteTransaction(id); await refreshAfterMutation(); }}
                onPreviewCsv={previewTransactionsCsv}
                onImportCsv={async (content) => { const result = await importTransactionsCsv(content); await refreshAfterMutation(); return result; }}
                onBackup={exportBackup}
                onValidateBackup={validateBackup}
                onRestoreBackup={async (path) => { const result = await restoreBackup(path); await refreshAfterMutation(); return result; }}
                onFetchWalletStatus={fetchBudgetBakersStatus}
                onTestWallet={testBudgetBakersConnection}
                onPreviewWallet={previewBudgetBakersImport}
                onImportWallet={async (preview) => { const result = await importBudgetBakersPreview(preview); await importBudgetBakersPlan(preview); await refreshAfterMutation(); return result; }}
                onFetchEtoroStatus={fetchEtoroStatus}
                onTestEtoro={testEtoroConnection}
                onPreviewEtoro={previewEtoroImport}
                onImportEtoro={async (preview) => { const result = await importEtoroPreview(preview); await refreshAfterMutation(); return result; }}
                onFetchEtoroMappings={fetchEtoroMappings}
                onConfirmEtoroMappings={confirmEtoroMappings}
                onMarkEtoroUnsupported={markEtoroUnsupported}
                onExportMappingConfig={exportMappingConfig}
                onValidateMappingConfig={validateMappingConfig}
                onImportMappingConfig={async (config) => { const result = await importMappingConfig(config); await refreshAfterMutation(); return result; }}
                onFetchReconciliation={fetchReconciliation}
                onSaveSourceMapping={saveSourceMapping}
                onSaveOpeningPosition={async (position) => { await saveOpeningPosition(position); await refreshAfterMutation(); }}
                privacyMode={privacyMode}
              />
            )}

            {activeTab === 'plan' && (
              <PlanningTab
                budgets={budgets}
                categories={categories}
                recurring={recurring}
                financialEvents={financialEvents}
                review={monthlyReview}
                privacyMode={privacyMode}
                onSaveBudget={async (budget) => { await saveBudget(budget); await refreshAfterMutation(); }}
                onDeleteBudget={async (id) => { await deleteBudget(id); await refreshAfterMutation(); }}
                onUpdateRecurring={async (id, status) => { await updateRecurringStatus(id, status); await refreshAfterMutation(); }}
                onSaveSnapshot={async () => { await saveMonthlyReviewSnapshot(monthlyReview?.period); await refreshAfterMutation(); }}
                onRunCalculator={runCalculator}
              />
            )}

            {activeTab === 'invest' && (
              <div className="space-y-5">
                <WealthTab
                  data={wealth}
                  privacyMode={privacyMode}
                  onRefresh={refreshWealth}
                  onImportValuations={importValuationsCsv}
                  onImportBenchmark={importBenchmarkCsv}
                  onSaveInvestmentOperation={async (operation) => { await saveInvestmentOperation(operation); await refreshWealth(); }}
                  onDeleteInvestmentOperation={async (id) => { await deleteInvestmentOperation(id); await refreshWealth(); }}
                  onPreviewInvestmentCsv={previewInvestmentLedgerCsv}
                  onImportInvestmentCsv={async (content) => { const result = await importInvestmentLedgerCsv(content); await refreshWealth(); return result; }}
                  onSaveOpeningPosition={async (position) => { await saveOpeningPosition(position); await refreshWealth(); }}
                  onSetPositionAuthority={async (ticker, state, notes) => { await setPositionAuthority(ticker, state, notes); await refreshWealth(); }}
                  onSyncMarketData={async (benchmarkSymbol, mode) => { const result = await syncMarketData(benchmarkSymbol, mode); await refreshWealth(undefined, benchmarkSymbol); return result; }}
                  onSaveSymbolMapping={async (mapping) => { await saveSymbolMapping(mapping); await refreshWealth(); }}
                  onSavePriceAuthority={async (authority) => { await savePriceAuthority(authority); await refreshWealth(); }}
                  onSaveMarketDataConfig={async (config) => { await saveMarketDataConfig(config); await refreshWealth(); }}
                  onSaveFxRate={async (rate) => { await saveFxRate(rate); await refreshWealth(); }}
                />
                <AssetListTab
                  assets={assets}
                  currency={currency}
                  exchangeRate={exchangeRate}
                  onSelectForSimulation={handleSelectAssetForSimulation}
                  privacyMode={privacyMode}
                />
                <InvestmentThesisTab
                  theses={theses}
                  assets={assets}
                  onSaveThesis={handleSaveThesis}
                  onSimulatePurchase={handleSimulatePurchase}
                  selectedTickerForSim={selectedTickerForSim}
                />
              </div>
            )}

          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer className="border-t border-gray-800/80 bg-[#0B0F19] py-4 px-4 text-center text-xs text-gray-500 font-mono">
        Finanzas Inteligentes &bull; SQLite local &bull; Fuentes: DEMO / MANUAL / CSV / BUDGETBAKERS / ETORO
      </footer>
    </div>
  );
};
export default App;
