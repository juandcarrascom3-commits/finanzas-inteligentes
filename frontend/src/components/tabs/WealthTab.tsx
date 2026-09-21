import React, { useState } from 'react';
import { AlertTriangle, BarChart3, GitCompare, PieChart, RefreshCw, Target, Upload } from 'lucide-react';
import { CsvImportResult, WealthData } from '../../types';

interface WealthTabProps {
  data: WealthData | null;
  privacyMode: boolean;
  onRefresh: (contributionUsd?: number, benchmarkKey?: string) => Promise<void>;
  onImportValuations: (content: string) => Promise<CsvImportResult>;
  onImportBenchmark: (content: string, benchmarkKey: string) => Promise<CsvImportResult>;
}

const panel = 'bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3';
const input = 'bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500';

export const WealthTab: React.FC<WealthTabProps> = ({ data, privacyMode, onRefresh, onImportValuations, onImportBenchmark }) => {
  const [contribution, setContribution] = useState(0);
  const [benchmarkKey, setBenchmarkKey] = useState('');
  const [valuationCsv, setValuationCsv] = useState('');
  const [benchmarkCsv, setBenchmarkCsv] = useState('');
  const [feedback, setFeedback] = useState('');

  const money = (value?: number | null) => {
    if (value === null || value === undefined) return 'N/D';
    if (privacyMode) return '••••';
    return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };
  const pct = (value?: number | null) => value === null || value === undefined ? 'N/D' : `${value >= 0 ? '+' : ''}${value}%`;
  const metric = (item: { status: string; value_pct?: number | null; value?: number | null; reason?: string | null }, kind: 'pct' | 'num' = 'pct') => (
    item.status === 'AVAILABLE' ? (kind === 'pct' ? pct(item.value_pct) : item.value ?? 'N/D') : `N/D · ${item.reason || 'datos insuficientes'}`
  );

  const importValuations = async () => {
    const res = await onImportValuations(valuationCsv);
    setFeedback(`Valoraciones importadas: ${res.imported_count ?? 0}; rechazadas: ${res.rejected_count}`);
    await onRefresh(contribution, benchmarkKey || undefined);
  };

  const importBenchmark = async () => {
    const key = benchmarkKey.trim().toUpperCase();
    if (!key) {
      setFeedback('Defina un benchmark key antes de importar.');
      return;
    }
    const res = await onImportBenchmark(benchmarkCsv, key);
    setFeedback(`Benchmark importado: ${res.imported_count ?? 0}; rechazadas: ${res.rejected_count}`);
    await onRefresh(contribution, key);
  };

  if (!data) {
    return (
      <section className={panel}>
        <div className="text-sm text-gray-300">Cargando Wealth...</div>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      {feedback && <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 rounded-xl p-3 text-xs">{feedback}</div>}

      <section className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className={panel}>
          <div className="flex items-center gap-2 text-gray-400 text-xs"><PieChart className="w-4 h-4 text-emerald-400" />Portfolio</div>
          <div className="text-2xl font-bold text-white">{money(data.summary.total_value_usd)}</div>
          <div className="text-xs text-gray-400">P&L no realizado: <span className="text-emerald-300">{money(data.summary.unrealized_pnl_usd)}</span></div>
        </div>
        <div className={panel}>
          <div className="flex items-center gap-2 text-gray-400 text-xs"><BarChart3 className="w-4 h-4 text-purple-400" />Performance</div>
          <div className="text-sm text-white">TWR: {metric(data.performance.twr)}</div>
          <div className="text-sm text-white">MWR: {metric(data.performance.mwr)}</div>
          <div className="text-xs text-gray-400">Retorno acumulado: {metric(data.performance.cumulative_return)}</div>
        </div>
        <div className={panel}>
          <div className="flex items-center gap-2 text-gray-400 text-xs"><AlertTriangle className="w-4 h-4 text-amber-400" />Exposure & Risk</div>
          <div className="text-sm text-white">Top activo: {data.concentration.top_asset?.ticker || 'N/D'} {data.concentration.top_asset ? `${data.concentration.top_asset.allocation_pct}%` : ''}</div>
          <div className="text-xs text-gray-400">Volatilidad: {metric(data.performance.risk.volatility)}</div>
          <div className="text-xs text-gray-400">Max DD: {metric(data.performance.risk.max_drawdown)}</div>
        </div>
        <div className={panel}>
          <div className="flex items-center gap-2 text-gray-400 text-xs"><Target className="w-4 h-4 text-blue-400" />Calidad</div>
          <div className="text-sm text-white">{data.data_quality.history_coverage_pct}% con historial</div>
          <div className="text-xs text-gray-400">{data.data_quality.issues.length} datos por completar</div>
          <div className="text-xs text-gray-400">{data.history.policy}</div>
        </div>
      </section>

      <section className={panel}>
        <div className="flex flex-col lg:flex-row lg:items-end gap-3">
          <div className="flex-1">
            <div className="text-sm font-bold text-white mb-1">Histórico manual / CSV</div>
            <textarea className={`${input} w-full min-h-20`} placeholder="ticker,date,price,currency&#10;NVDA,2026-09-01,120,USD" value={valuationCsv} onChange={(e) => setValuationCsv(e.target.value)} />
          </div>
          <button onClick={importValuations} className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-2"><Upload className="w-4 h-4" />Importar valoraciones</button>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className={panel}>
          <div className="text-sm font-bold text-white">Allocation</div>
          {['asset_type', 'sector', 'country', 'currency'].map((dimension) => (
            <div key={dimension}>
              <div className="text-[10px] uppercase text-gray-500 mb-1">{dimension}</div>
              {(data.allocation.dimensions[dimension] || []).slice(0, 4).map((row) => (
                <div key={`${dimension}-${row.name}`} className="flex items-center justify-between text-xs py-1 border-b border-gray-800/60">
                  <span className="text-gray-300">{row.name || 'Unknown'}</span>
                  <span className="text-white">{row.allocation_pct}% · {money(row.value_usd)}</span>
                </div>
              ))}
            </div>
          ))}
        </div>

        <div className={panel}>
          <div className="text-sm font-bold text-white">Action Center</div>
          {data.action_items.length === 0 && <div className="text-xs text-gray-400">Sin acciones pendientes de Wealth.</div>}
          {data.action_items.slice(0, 8).map((item, idx) => (
            <div key={`${item.type}-${idx}`} className="text-xs bg-gray-900/60 border border-gray-800 rounded-lg p-2">
              <div className="text-white font-semibold">{item.title}</div>
              <div className="text-gray-400">{item.why}</div>
              <div className="text-emerald-300">{item.action}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className={panel}>
          <div className="text-sm font-bold text-white">Attribution v1</div>
          {data.attribution.status !== 'AVAILABLE' && <div className="text-xs text-gray-400">{data.attribution.reason}</div>}
          {data.attribution.status === 'AVAILABLE' && (
            <>
              <div className="text-xs text-gray-400">Cambio: <span className="text-white">{money(data.attribution.change_usd)}</span></div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-[10px] uppercase text-gray-500">Ganadores</div>
                  {data.attribution.top_winners?.map((row) => <div key={row.ticker} className="text-xs text-emerald-300">{row.ticker}: {money(row.contribution_usd)}</div>)}
                </div>
                <div>
                  <div className="text-[10px] uppercase text-gray-500">Detractores</div>
                  {data.attribution.top_detractors?.map((row) => <div key={row.ticker} className="text-xs text-red-300">{row.ticker}: {money(row.contribution_usd)}</div>)}
                </div>
              </div>
            </>
          )}
        </div>

        <div className={panel}>
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-bold text-white">Benchmark manual</div>
            <button onClick={() => onRefresh(contribution, benchmarkKey || undefined)} className="p-2 rounded-lg bg-gray-800 text-gray-300"><RefreshCw className="w-4 h-4" /></button>
          </div>
          <input className={input} placeholder="Benchmark key, ej: SPY_MANUAL" value={benchmarkKey} onChange={(e) => setBenchmarkKey(e.target.value.toUpperCase())} />
          <textarea className={`${input} w-full min-h-16`} placeholder="date,price,currency&#10;2026-09-01,100,USD" value={benchmarkCsv} onChange={(e) => setBenchmarkCsv(e.target.value)} />
          <button onClick={importBenchmark} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs flex items-center gap-2"><GitCompare className="w-4 h-4" />Importar benchmark</button>
          <div className="text-xs text-gray-400">Estado: {data.benchmark.status} {data.benchmark.excess_return_pct !== undefined ? `· Excess return ${pct(data.benchmark.excess_return_pct)}` : data.benchmark.reason}</div>
        </div>
      </section>

      <section className={panel}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>
            <div className="text-sm font-bold text-white">Rebalance Planner</div>
            <div className="text-xs text-gray-400">Tradicional y con nuevos aportes; no ejecuta operaciones.</div>
          </div>
          <div className="flex gap-2">
            <input className={input} type="number" value={contribution} onChange={(e) => setContribution(Number(e.target.value) || 0)} />
            <button onClick={() => onRefresh(contribution, benchmarkKey || undefined)} className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold">Calcular</button>
          </div>
        </div>
        {data.rebalancing.status !== 'AVAILABLE' && <div className="text-xs text-gray-400">{data.rebalancing.reason}</div>}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-gray-500 uppercase text-[10px]"><tr><th className="py-2">Activo</th><th>Actual</th><th>Meta</th><th>Desvío</th><th>Compra/Venta</th><th>Aporte</th></tr></thead>
            <tbody className="divide-y divide-gray-800">
              {data.rebalancing.traditional.map((row) => {
                const aport = data.rebalancing.new_contribution.find((item) => item.ticker === row.ticker);
                return <tr key={row.ticker}><td className="py-2 text-white">{row.ticker}</td><td>{row.current_pct}%</td><td>{row.target_pct}%</td><td>{row.drift_pct} pp</td><td>{money(row.trade_usd)}</td><td>{money(aport?.contribution_usd || 0)}</td></tr>;
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
