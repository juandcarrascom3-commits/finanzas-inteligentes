import React, { useState } from 'react';
import { AlertTriangle, BarChart3, GitCompare, PieChart, RefreshCw, Target, Upload } from 'lucide-react';
import { CsvImportResult, InvestmentOperation, MarketDataSyncResult, WealthData } from '../../types';

interface WealthTabProps {
  data: WealthData | null;
  privacyMode: boolean;
  onRefresh: (contributionUsd?: number, benchmarkKey?: string) => Promise<void>;
  onImportValuations: (content: string) => Promise<CsvImportResult>;
  onImportBenchmark: (content: string, benchmarkKey: string) => Promise<CsvImportResult>;
  onSaveInvestmentOperation: (operation: Partial<InvestmentOperation>) => Promise<void>;
  onDeleteInvestmentOperation: (id: string) => Promise<void>;
  onPreviewInvestmentCsv: (content: string) => Promise<CsvImportResult>;
  onImportInvestmentCsv: (content: string) => Promise<CsvImportResult>;
  onSaveOpeningPosition: (position: { ticker: string; opened_at: string; quantity: number; unit_cost?: number; total_cost?: number; currency: string; notes?: string }) => Promise<void>;
  onSetPositionAuthority: (ticker: string, state: string, notes?: string) => Promise<void>;
  onSyncMarketData: (benchmarkSymbol?: string) => Promise<MarketDataSyncResult>;
}

const panel = 'bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3';
const input = 'bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500';

export const WealthTab: React.FC<WealthTabProps> = ({ data, privacyMode, onRefresh, onImportValuations, onImportBenchmark, onSaveInvestmentOperation, onDeleteInvestmentOperation, onPreviewInvestmentCsv, onImportInvestmentCsv, onSaveOpeningPosition, onSetPositionAuthority, onSyncMarketData }) => {
  const [contribution, setContribution] = useState(0);
  const [benchmarkKey, setBenchmarkKey] = useState('');
  const [valuationCsv, setValuationCsv] = useState('');
  const [benchmarkCsv, setBenchmarkCsv] = useState('');
  const [ledgerCsv, setLedgerCsv] = useState('');
  const [opForm, setOpForm] = useState<Partial<InvestmentOperation>>({
    occurred_at: new Date().toISOString().slice(0, 10),
    operation_type: 'BUY',
    currency: 'USD',
    quantity: 0,
    price: 0,
    amount: 0,
    fee: 0,
    source: 'MANUAL',
  });
  const [ledgerFilter, setLedgerFilter] = useState('');
  const [selectedRecon, setSelectedRecon] = useState<string | null>(null);
  const [feedback, setFeedback] = useState('');
  const [syncingMarket, setSyncingMarket] = useState(false);

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

  const syncMarket = async () => {
    setSyncingMarket(true);
    try {
      const res = await onSyncMarketData(benchmarkKey.trim().toUpperCase() || data?.market_data.benchmark_symbol);
      setFeedback(`Market Data: ${res.assets.filter((row) => row.status === 'UPDATED').length} activos, ${res.fx.filter((row) => row.status === 'UPDATED').length} FX, ${res.errors.length} fallos.`);
    } finally {
      setSyncingMarket(false);
    }
  };

  const saveOperation = async () => {
    await onSaveInvestmentOperation(opForm);
    setOpForm({ occurred_at: new Date().toISOString().slice(0, 10), operation_type: 'BUY', currency: 'USD', quantity: 0, price: 0, amount: 0, fee: 0, source: 'MANUAL' });
    setFeedback('Operación de inversión guardada.');
  };

  const previewLedger = async () => {
    const res = await onPreviewInvestmentCsv(ledgerCsv);
    setFeedback(`Preview ledger: ${res.accepted_count} aceptadas, ${res.rejected_count} rechazadas, ${res.duplicate_count ?? 0} duplicadas.`);
  };

  const importLedger = async () => {
    const res = await onImportInvestmentCsv(ledgerCsv);
    setFeedback(`Ledger importado: ${res.imported_count ?? 0}; duplicadas: ${res.duplicate_count ?? 0}; rechazadas: ${res.rejected_count}.`);
  };

  const registerOpeningFromRow = async (row: WealthData['ledger']['reconciliation']['rows'][number]) => {
    const date = window.prompt(`Fecha de posición inicial para ${row.ticker}`, new Date().toISOString().slice(0, 10));
    if (!date) return;
    await onSaveOpeningPosition({
      ticker: row.ticker,
      opened_at: date,
      quantity: row.registered_quantity,
      unit_cost: row.registered_avg_price,
      currency: 'USD',
      notes: 'Creada desde reconciliación.',
    });
    setFeedback(`Opening position registrada para ${row.ticker}.`);
  };

  const adoptLedger = async (ticker: string) => {
    if (!window.confirm(`Adoptar ledger como fuente autoritativa para ${ticker}?`)) return;
    await onSetPositionAuthority(ticker, 'LEDGER_AUTHORITATIVE', 'Adoptado desde reconciliación.');
    setFeedback(`${ticker} ahora usa Ledger como fuente.`);
  };

  const keepManual = async (ticker: string) => {
    if (!window.confirm(`Mantener ${ticker} en modo manual?`)) return;
    await onSetPositionAuthority(ticker, 'MANUAL', 'Mantener posición manual.');
    setFeedback(`${ticker} queda en modo manual.`);
  };

  const createAdjustment = async (row: WealthData['ledger']['reconciliation']['rows'][number]) => {
    if (!window.confirm(`Crear ADJUSTMENT explícito para ${row.ticker}?`)) return;
    await onSaveInvestmentOperation({
      occurred_at: new Date().toISOString().slice(0, 10),
      ticker: row.ticker,
      operation_type: 'ADJUSTMENT',
      quantity: Math.max(row.quantity_diff, 0),
      amount: Math.max(row.quantity_diff, 0) * row.registered_avg_price,
      currency: 'USD',
      notes: 'Ajuste explícito desde reconciliación.',
      source: 'MANUAL',
    });
    setFeedback(`Adjustment registrado para ${row.ticker}.`);
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
          <div className="text-xs text-gray-400">P&L realizado: {money(data.performance.realized_pnl.value_usd)}</div>
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
                <div className="text-xs text-gray-400">Ledger: {data.ledger.reconciliation.issues.length} acciones</div>
          <div className="text-xs text-gray-400">{data.history.policy}</div>
        </div>
      </section>

      <section className={panel}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-white">Market Data</div>
            <div className="text-xs text-gray-400">
              {data.market_data.provider} · {data.market_data.last_sync_at ? `actualizado ${new Date(data.market_data.last_sync_at).toLocaleString()}` : 'sin sync'} · Benchmark {data.market_data.benchmark_symbol || 'N/D'}
            </div>
            <div className="text-xs text-gray-500">
              {data.market_data.updated_assets} activos · {data.market_data.fx_pairs} FX · {data.market_data.stale_tickers.length} stale · {data.market_data.missing_tickers.length} missing
              {data.market_data.last_error ? ` · ${data.market_data.last_error}` : ''}
            </div>
          </div>
          <button onClick={syncMarket} disabled={syncingMarket} className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white text-xs font-bold flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${syncingMarket ? 'animate-spin' : ''}`} />Actualizar datos de mercado
          </button>
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

      <section className={panel}>
        <div className="flex flex-col lg:flex-row lg:items-start gap-4">
          <div className="lg:w-80 space-y-2">
            <div className="text-sm font-bold text-white">Investment Ledger</div>
            <div className="grid grid-cols-2 gap-2">
              <input className={input} type="date" value={opForm.occurred_at || ''} onChange={(e) => setOpForm({ ...opForm, occurred_at: e.target.value })} />
              <select className={input} value={opForm.operation_type || 'BUY'} onChange={(e) => setOpForm({ ...opForm, operation_type: e.target.value as InvestmentOperation['operation_type'] })}>
                {['CONTRIBUTION', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'INTEREST', 'FEE', 'TRANSFER_IN', 'TRANSFER_OUT'].map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
              <input className={input} placeholder="Ticker" value={opForm.ticker || ''} onChange={(e) => setOpForm({ ...opForm, ticker: e.target.value.toUpperCase() })} />
              <input className={input} placeholder="Moneda" value={opForm.currency || 'USD'} onChange={(e) => setOpForm({ ...opForm, currency: e.target.value.toUpperCase() })} />
              <input className={input} type="number" placeholder="Cantidad" value={opForm.quantity ?? 0} onChange={(e) => setOpForm({ ...opForm, quantity: Number(e.target.value) })} />
              <input className={input} type="number" placeholder="Precio" value={opForm.price ?? 0} onChange={(e) => setOpForm({ ...opForm, price: Number(e.target.value) })} />
              <input className={input} type="number" placeholder="Importe" value={opForm.amount ?? 0} onChange={(e) => setOpForm({ ...opForm, amount: Number(e.target.value) })} />
              <input className={input} type="number" placeholder="Fee" value={opForm.fee ?? 0} onChange={(e) => setOpForm({ ...opForm, fee: Number(e.target.value) })} />
            </div>
            <input className={`${input} w-full`} placeholder="Notas" value={opForm.notes || ''} onChange={(e) => setOpForm({ ...opForm, notes: e.target.value })} />
            <button onClick={saveOperation} className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Guardar operación</button>
          </div>

          <div className="flex-1 space-y-2">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
              <div>
                <div className="text-sm font-bold text-white">Actividad</div>
                <div className="text-xs text-gray-400">CONTRIBUTION/WITHDRAWAL son cashflows externos; BUY/SELL son operaciones internas.</div>
              </div>
              <input className={input} placeholder="Filtrar ticker/tipo" value={ledgerFilter} onChange={(e) => setLedgerFilter(e.target.value.toUpperCase())} />
            </div>
            <div className="overflow-x-auto max-h-64">
              <table className="w-full text-left text-xs">
                <thead className="text-gray-500 uppercase text-[10px]"><tr><th className="py-2">Fecha</th><th>Tipo</th><th>Ticker</th><th>Cantidad</th><th>Precio</th><th>Importe</th><th>Fuente</th><th></th></tr></thead>
                <tbody className="divide-y divide-gray-800">
                  {data.ledger.operations
                    .filter((op) => !ledgerFilter || `${op.ticker || ''} ${op.operation_type}`.includes(ledgerFilter))
                    .slice(-50)
                    .reverse()
                    .map((op) => (
                      <tr key={op.id}>
                        <td className="py-2">{op.occurred_at.slice(0, 10)}</td>
                        <td className="text-white">{op.operation_type}</td>
                        <td>{op.ticker || '-'}</td>
                        <td>{op.quantity}</td>
                        <td>{money(op.price)}</td>
                        <td>{money(op.amount)}</td>
                        <td>{op.source}</td>
                        <td><button onClick={() => window.confirm('Eliminar operación?') && onDeleteInvestmentOperation(op.id)} className="text-red-300">Eliminar</button></td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2">
          <div className="space-y-2">
            <div className="text-xs font-bold text-gray-300">Import CSV ledger</div>
            <textarea className={`${input} w-full min-h-20`} placeholder="date,ticker,type,quantity,price,amount,fee,currency,account_id,external_id&#10;2026-01-01,NVDA,BUY,10,100,1000,1,USD,,trade-1" value={ledgerCsv} onChange={(e) => setLedgerCsv(e.target.value)} />
            <div className="flex gap-2">
              <button onClick={previewLedger} className="px-3 py-2 rounded-lg bg-gray-800 text-gray-200 text-xs">Preview</button>
              <button onClick={importLedger} className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold">Importar</button>
            </div>
          </div>
          <div>
            <div className="text-xs font-bold text-gray-300 mb-2">Portfolio → Reconciliation</div>
            <div className="space-y-1 max-h-40 overflow-auto">
              {data.ledger.reconciliation.rows.map((row) => (
                <button key={row.ticker} onClick={() => setSelectedRecon(selectedRecon === row.ticker ? null : row.ticker)} className="w-full text-left text-xs bg-gray-900/60 rounded-lg p-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-white font-bold">{row.ticker}</span>
                    <span className={row.status === 'MATCH' ? 'text-emerald-300' : 'text-amber-300'}>{row.status}</span>
                    <span className="text-gray-400">hold {row.registered_quantity} / ledger {row.derived_quantity}</span>
                    <span className="text-gray-400">avg {row.registered_avg_price} / {row.derived_avg_price}</span>
                    <span className="text-gray-500">{row.coverage} · {row.source}</span>
                  </div>
                  {selectedRecon === row.ticker && (
                    <div className="mt-2 border-t border-gray-800 pt-2 space-y-2">
                      <div className="text-gray-400">
                        Fuente actual: {row.source}. Autoridad: {row.authority_state}. Diff qty: {row.quantity_diff}; diff avg: {row.avg_price_diff}.
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button onClick={(e) => { e.stopPropagation(); registerOpeningFromRow(row); }} className="px-2 py-1 rounded bg-gray-800 text-gray-200">Registrar posición inicial</button>
                        <button onClick={(e) => { e.stopPropagation(); createAdjustment(row); }} className="px-2 py-1 rounded bg-gray-800 text-gray-200">Adjustment explícito</button>
                        <button disabled={row.status !== 'MATCH'} onClick={(e) => { e.stopPropagation(); adoptLedger(row.ticker); }} className="px-2 py-1 rounded bg-emerald-600 disabled:opacity-50 text-white">Adoptar Ledger</button>
                        <button onClick={(e) => { e.stopPropagation(); keepManual(row.ticker); }} className="px-2 py-1 rounded bg-gray-800 text-gray-200">Mantener manual</button>
                      </div>
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
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
