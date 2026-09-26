import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Header } from './components/Header';
import { AssetListTab } from './components/tabs/AssetListTab';
import { InvestmentThesisTab } from './components/tabs/InvestmentThesisTab';
import { WealthTab } from './components/tabs/WealthTab';
import type { InvestTool } from './components/tabs/WealthTab';
import { PersonalDataTab } from './components/tabs/PersonalDataTab';
import { PlanningTab } from './components/tabs/PlanningTab';
import { ResearchTab } from './components/tabs/ResearchTab';
import { AetherisShell, AetherisTab } from './aetheris/AetherisShell';
import { AetherisOverview } from './aetheris/AetherisOverview';
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
  fetchPortfolioExposure,
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
  refreshFundCompositions,
  saveAccount,
  saveAsset,
  saveInvestmentOperation,
  saveOpeningPosition,
  saveThesis,
  saveTransaction,
  restoreBackup,
  runCashProjection,
  runCalculator,
  runRunway,
  runSafeToSpend,
  evaluateScenario,
  evaluateFinancialInbox,
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
import { Account, Category, DashboardSummary, DataSourceInfo, Asset, InvestmentThesis, Transaction, UnderstandSummary, Budget, RecurringRule, MonthlyReview, WealthData, FinancialEvent, FinancialInboxResult, PortfolioExposureResult } from './types';
import { AlertTriangle } from 'lucide-react';

export const App: React.FC = () => {
  const [currency, setCurrency] = useState<'USD' | 'COP'>('USD');
  const [activeTab, setActiveTab] = useState<AetherisTab>('overview');
  const [privacyMode, setPrivacyModeState] = useState<boolean>(() => localStorage.getItem('finance_privacy_mode') === '1');
  const [understandPeriod, setUnderstandPeriod] = useState<string>('current_month');
  const [selectedTickerForSim, setSelectedTickerForSim] = useState<string | undefined>(undefined);
  // Una sola familia de herramienta activa por contexto Invest (dueño común: App).
  const [investTool, setInvestTool] = useState<InvestTool | null>(null);
  const thesisLauncherRef = useRef<HTMLButtonElement>(null);

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
  const [financialInbox, setFinancialInbox] = useState<FinancialInboxResult | null>(null);
  const [monthlyReview, setMonthlyReview] = useState<MonthlyReview | null>(null);
  const [wealth, setWealth] = useState<WealthData | null>(null);
  const [portfolioExposure, setPortfolioExposure] = useState<PortfolioExposureResult | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const exchangeRate = dashboard?.kpis?.net_worth?.exchange_rate || 4050;
  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [dashData, assetsData, thesesData, accountsData, transactionsData, categoriesData, sourceData, understandData, budgetsData, recurringData, eventsData, reviewData, wealthData, exposureData, inboxData] = await Promise.all([
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
        fetchWealth(),
        fetchPortfolioExposure().catch(() => null),
        evaluateFinancialInbox({ currency, horizon_days: 30 }).catch(() => null)
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
      setPortfolioExposure(exposureData);
      setFinancialInbox(inboxData);
    } catch (err: any) {
      console.error('Error loading data:', err);
      setErrorMsg('No se pudo conectar al servidor local. Verifique que el backend de FastAPI esté en ejecución.');
    } finally {
      setIsLoading(false);
    }
  }, [exchangeRate, understandPeriod, currency]);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  const handleSelectAssetForSimulation = (ticker: string) => {
    setSelectedTickerForSim(ticker);
    setInvestTool('thesis');
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
    setPortfolioExposure(await fetchPortfolioExposure().catch(() => null));
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

  const header = (
    <Header
      currency={currency}
      setCurrency={setCurrency}
      exchangeRate={exchangeRate}
      onRefresh={loadAllData}
      isLoading={isLoading}
      privacyMode={privacyMode}
      setPrivacyMode={setPrivacyMode}
    />
  );

  return (
    <AetherisShell
      activeTab={activeTab}
      onSelectTab={setActiveTab}
      header={header}
      sourceLabel={`${dataSource?.profile || dataSource?.mode || 'DEMO'} · MANUAL / CSV / BUDGETBAKERS / ETORO`}
    >
      {errorMsg && (
        <div className="mb-5 w-full">
          <div className="a-surface flex items-center justify-between gap-3 p-3 text-xs text-[var(--a-negative)]">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button
              onClick={loadAllData}
              className="a-motion rounded-full border border-[var(--a-line)] px-3 py-1 text-[11px] text-[var(--a-secondary)]"
            >
              Reintentar
            </button>
          </div>
        </div>
      )}

      {activeTab === 'overview' && dashboard && (
        <AetherisOverview
          dashboard={dashboard}
          understand={understand}
          financialInbox={financialInbox}
          monthlyReview={monthlyReview}
          dataSource={dataSource}
          currency={currency}
          privacyMode={privacyMode}
        />
      )}
      {activeTab === 'overview' && !dashboard && (
        <section className="a-canvas">
          <div className="a-page-kicker">Overview</div>
          <h1 className="a-page-title">Cargando estado financiero</h1>
          <p className="a-page-subtitle">Se mantiene la interfaz disponible mientras el backend local responde.</p>
        </section>
      )}

      {activeTab === 'research' && <ResearchTab />}

      <section className="space-y-4">
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
              onRunCashProjection={runCashProjection}
              onRunSafeToSpend={runSafeToSpend}
              onRunRunway={runRunway}
              onEvaluateScenario={evaluateScenario}
            />
          )}

          {activeTab === 'invest' && (
            <div className={investTool ? 'grid gap-[var(--a-stack)] min-[1041px]:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]' : ''}>
              <WealthTab
                data={wealth}
                exposure={portfolioExposure}
                privacyMode={privacyMode}
                openTool={investTool}
                onOpenTool={setInvestTool}
                thesisLauncherRef={thesisLauncherRef}
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
                onRefreshFundCompositions={async (symbols) => { const result = await refreshFundCompositions(symbols); await refreshWealth(); return result; }}
                onSaveSymbolMapping={async (mapping) => { await saveSymbolMapping(mapping); await refreshWealth(); }}
                onSavePriceAuthority={async (authority) => { await savePriceAuthority(authority); await refreshWealth(); }}
                onSaveMarketDataConfig={async (config) => { await saveMarketDataConfig(config); await refreshWealth(); }}
                onSaveFxRate={async (rate) => { await saveFxRate(rate); await refreshWealth(); }}
              >
                <AssetListTab
                  assets={assets}
                  currency={currency}
                  exchangeRate={exchangeRate}
                  onSelectForSimulation={handleSelectAssetForSimulation}
                  privacyMode={privacyMode}
                />
              </WealthTab>
              <InvestmentThesisTab
                theses={theses}
                assets={assets}
                onSaveThesis={handleSaveThesis}
                onSimulatePurchase={handleSimulatePurchase}
                selectedTickerForSim={selectedTickerForSim}
                openTool={investTool}
                onOpenTool={setInvestTool}
                thesisLauncherRef={thesisLauncherRef}
              />
            </div>
          )}
        </div>
      </section>
    </AetherisShell>
  );
};
export default App;
