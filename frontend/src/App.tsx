import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { TopKpiRow } from './components/TopKpiRow';
import { CentralVisualSection } from './components/CentralVisualSection';
import { PanoramaTab } from './components/tabs/PanoramaTab';
import { AssetListTab } from './components/tabs/AssetListTab';
import { InvestmentThesisTab } from './components/tabs/InvestmentThesisTab';
import { IngestionTab } from './components/tabs/IngestionTab';
import { ExecutiveReportTab } from './components/tabs/ExecutiveReportTab';
import {
  fetchDashboard,
  fetchPanorama,
  fetchAssets,
  fetchTheses,
  saveThesis,
  simulatePurchase,
  fetchBudgetBakersMappings,
  updateBudgetBakersMapping,
  triggerBudgetBakersSync
} from './services/api';
import { DashboardSummary, PanoramaData, Asset, InvestmentThesis, BudgetBakersMapping } from './types';
import { Compass, ListFilter, ShieldCheck, Database, FileText, AlertTriangle } from 'lucide-react';

export const App: React.FC = () => {
  const [currency, setCurrency] = useState<'USD' | 'COP'>('USD');
  const [activeTab, setActiveTab] = useState<'panorama' | 'activos' | 'tesis' | 'ingestion' | 'informe'>('panorama');
  const [selectedTickerForSim, setSelectedTickerForSim] = useState<string | undefined>(undefined);

  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [panorama, setPanorama] = useState<PanoramaData | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [theses, setTheses] = useState<InvestmentThesis[]>([]);
  const [mappings, setMappings] = useState<BudgetBakersMapping[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const exchangeRate = dashboard?.kpis?.net_worth?.exchange_rate || 4050;

  const loadAllData = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [dashData, panoData, assetsData, thesesData, mapData] = await Promise.all([
        fetchDashboard(exchangeRate),
        fetchPanorama(),
        fetchAssets(),
        fetchTheses(),
        fetchBudgetBakersMappings()
      ]);
      setDashboard(dashData);
      setPanorama(panoData);
      setAssets(assetsData);
      setTheses(thesesData);
      setMappings(mapData);
    } catch (err: any) {
      console.error('Error loading data:', err);
      setErrorMsg('No se pudo conectar al servidor local. Verifique que el backend de FastAPI esté en ejecución.');
    } finally {
      setIsLoading(false);
    }
  }, [exchangeRate]);

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  const handleSelectAssetForSimulation = (ticker: string) => {
    setSelectedTickerForSim(ticker);
    setActiveTab('tesis');
  };

  const handleSaveThesis = async (thesisData: Partial<InvestmentThesis>) => {
    await saveThesis(thesisData);
    const updatedTheses = await fetchTheses();
    setTheses(updatedTheses);
  };

  const handleSimulatePurchase = async (ticker: string, amountUsd: number) => {
    return await simulatePurchase(ticker, amountUsd);
  };

  const handleUpdateMapping = async (mappingId: string, localCategory: string, isActive: boolean) => {
    await updateBudgetBakersMapping(mappingId, localCategory, isActive);
    const updated = await fetchBudgetBakersMappings();
    setMappings(updated);
  };

  const handleTriggerSync = async (forceRefresh: boolean) => {
    const res = await triggerBudgetBakersSync(forceRefresh);
    await loadAllData();
    return res;
  };

  return (
    <div className="min-h-screen bg-[#080C15] text-gray-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* HEADER SECTION */}
      <Header
        currency={currency}
        setCurrency={setCurrency}
        exchangeRate={exchangeRate}
        quota={dashboard?.daily_api_quota}
        onRefresh={loadAllData}
        isLoading={isLoading}
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

      {/* MAIN THREE-TIER CONTAINER */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-6 space-y-7">
        {dashboard && (
          <>
            {/* TIER 1: TOP KPI ROW (High-Level Summary) */}
            <TopKpiRow
              netWorth={dashboard.kpis.net_worth}
              savingsRate={dashboard.kpis.savings_rate}
              twrPct={dashboard.kpis.twr_pct}
              mwrPct={dashboard.kpis.mwr_pct}
              riskMetrics={dashboard.kpis.risk_metrics}
              currency={currency}
            />

            {/* TIER 2: CENTRAL VISUAL SECTION (Asset Allocation & Temporal Evolution) */}
            <CentralVisualSection
              treemapData={dashboard.allocation_treemap}
              evolutionData={dashboard.temporal_evolution}
              currency={currency}
              exchangeRate={exchangeRate}
            />
          </>
        )}

        {/* TIER 3: BOTTOM TAB SECTION & GRANULAR CONTROLS */}
        <section className="space-y-4">
          {/* Tabs Navigation Bar */}
          <div className="flex items-center space-x-2 border-b border-gray-800 pb-2 overflow-x-auto">
            <button
              onClick={() => setActiveTab('panorama')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'panorama'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <Compass className="w-4 h-4" />
              <span>Panorama (Pronósticos &amp; Checklist)</span>
            </button>

            <button
              onClick={() => setActiveTab('activos')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'activos'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <ListFilter className="w-4 h-4" />
              <span>Lista de Activos ({assets.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('tesis')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'tesis'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Tesis de Inversión (Filtro Humano)</span>
            </button>

            <button
              onClick={() => setActiveTab('ingestion')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'ingestion'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <Database className="w-4 h-4" />
              <span>REST API Ingestión (Wallet)</span>
            </button>

            <button
              onClick={() => setActiveTab('informe')}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'informe'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Informe Estratégico</span>
            </button>
          </div>

          {/* Active Tab Content Container */}
          <div className="pt-2">
            {activeTab === 'panorama' && panorama && (
              <PanoramaTab
                data={panorama}
                currency={currency}
                exchangeRate={exchangeRate}
              />
            )}

            {activeTab === 'activos' && (
              <AssetListTab
                assets={assets}
                currency={currency}
                exchangeRate={exchangeRate}
                onSelectForSimulation={handleSelectAssetForSimulation}
              />
            )}

            {activeTab === 'tesis' && (
              <InvestmentThesisTab
                theses={theses}
                assets={assets}
                onSaveThesis={handleSaveThesis}
                onSimulatePurchase={handleSimulatePurchase}
                selectedTickerForSim={selectedTickerForSim}
              />
            )}

            {activeTab === 'ingestion' && (
              <IngestionTab
                quota={dashboard?.daily_api_quota}
                mappings={mappings}
                onTriggerSync={handleTriggerSync}
                onUpdateMapping={handleUpdateMapping}
              />
            )}

            {activeTab === 'informe' && dashboard && (
              <ExecutiveReportTab
                geopoliticalRisks={dashboard.geopolitical_risk}
                currency={currency}
                exchangeRate={exchangeRate}
              />
            )}
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer className="border-t border-gray-800/80 bg-[#0B0F19] py-4 px-4 text-center text-xs text-gray-500 font-mono">
        Finanzas Inteligentes &bull; Arquitectura de 3 Niveles &bull; Supabase PostgreSQL / SQLite Parity &bull; Cuota Máx: 25 req/día
      </footer>
    </div>
  );
};
export default App;
