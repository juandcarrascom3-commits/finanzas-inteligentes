import React, { useState, useRef } from 'react';
import { GitCompare, RefreshCw, Upload } from 'lucide-react';
import { Button, Field, MetricInput, MoneyField, SegmentedControl } from '../../aetheris/controls';
import { DataState, InlineMetric } from '../../aetheris/primitives';
import { ToolSurfaceDock } from '../../aetheris/ToolSurfaceDock';
import { CsvImportResult, FundCompositionRefreshResult, InvestmentOperation, MarketDataSyncResult, PortfolioExposureResult, WealthData } from '../../types';

interface WealthTabProps {
  data: WealthData | null;
  exposure: PortfolioExposureResult | null;
  privacyMode: boolean;
  /** Slot de composición: workspace operativo (Posiciones) entre X-Ray y Allocation. */
  children?: React.ReactNode;
  onRefresh: (contributionUsd?: number, benchmarkKey?: string) => Promise<void>;
  onImportValuations: (content: string) => Promise<CsvImportResult>;
  onImportBenchmark: (content: string, benchmarkKey: string) => Promise<CsvImportResult>;
  onSaveInvestmentOperation: (operation: Partial<InvestmentOperation>) => Promise<void>;
  onDeleteInvestmentOperation: (id: string) => Promise<void>;
  onPreviewInvestmentCsv: (content: string) => Promise<CsvImportResult>;
  onImportInvestmentCsv: (content: string) => Promise<CsvImportResult>;
  onSaveOpeningPosition: (position: { ticker: string; opened_at: string; quantity: number; unit_cost?: number; total_cost?: number; currency: string; notes?: string }) => Promise<void>;
  onSetPositionAuthority: (ticker: string, state: string, notes?: string) => Promise<void>;
  onSyncMarketData: (benchmarkSymbol?: string, mode?: 'QUICK' | 'FULL') => Promise<MarketDataSyncResult>;
  onRefreshFundCompositions: (symbols?: string[]) => Promise<FundCompositionRefreshResult>;
  onSaveSymbolMapping: (mapping: { internal_symbol: string; provider?: string; provider_symbol: string; instrument_type?: string; expected_currency?: string; status?: string }) => Promise<void>;
  onSavePriceAuthority: (authority: { ticker: string; authority_mode: 'AUTO' | 'MANUAL'; manual_price?: number; manual_currency?: string; notes?: string }) => Promise<void>;
  onSaveMarketDataConfig: (config: Record<string, unknown>) => Promise<void>;
  onSaveFxRate: (rate: { base_currency: string; quote_currency: string; rate: number; rate_date: string; provider?: string; source?: string }) => Promise<void>;
  /** Herramienta activa del contexto Invest (una a la vez). */
  openTool: InvestTool | null;
  onOpenTool: (tool: InvestTool | null) => void;
  /** Ref del lanzador de Tesis (el dock lo renderiza InvestmentThesisTab). */
  thesisLauncherRef: React.RefObject<HTMLButtonElement>;
}

export type InvestTool = 'thesis' | 'rebalance' | 'ledger' | 'market';

const rowClass = 'flex items-baseline justify-between gap-3 border-b border-[var(--a-line)] py-1.5 last:border-b-0';
const dividerClass = 'min-w-0 lg:border-l lg:border-[var(--a-line)] lg:pl-6';
const boxClass = 'rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3 text-xs';

const signDirection = (value: number | null | undefined) =>
  value === null || value === undefined ? 'neutral' : value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral';

export const WealthTab: React.FC<WealthTabProps> = ({ data, exposure, privacyMode, children, openTool, onOpenTool, thesisLauncherRef, onRefresh, onImportValuations, onImportBenchmark, onSaveInvestmentOperation, onDeleteInvestmentOperation, onPreviewInvestmentCsv, onImportInvestmentCsv, onSaveOpeningPosition, onSetPositionAuthority, onSyncMarketData, onRefreshFundCompositions, onSaveSymbolMapping, onSavePriceAuthority, onSaveMarketDataConfig, onSaveFxRate }) => {
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
  const [refreshingFunds, setRefreshingFunds] = useState(false);
  const [xrayLens, setXrayLens] = useState<'asset_class' | 'sector' | 'underlying_security'>('underlying_security');
  const [symbolDrafts, setSymbolDrafts] = useState<Record<string, string>>({});
  const [manualPriceDrafts, setManualPriceDrafts] = useState<Record<string, string>>({});
  const [fxForm, setFxForm] = useState({ base_currency: 'COP', quote_currency: 'USD', rate: 0, rate_date: new Date().toISOString().slice(0, 10) });
  const rebalanceLauncherRef = useRef<HTMLButtonElement>(null);
  const ledgerLauncherRef = useRef<HTMLButtonElement>(null);
  const marketLauncherRef = useRef<HTMLButtonElement>(null);

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

  const syncMarket = async (mode: 'QUICK' | 'FULL') => {
    setSyncingMarket(true);
    try {
      const res = await onSyncMarketData(benchmarkKey.trim().toUpperCase() || data?.market_data.benchmark_symbol, mode);
      setFeedback(`Market Data ${mode}: ${res.assets.filter((row) => row.status === 'UPDATED').length} activos, ${res.fx.filter((row) => row.status === 'UPDATED').length} FX, ${res.errors.length} fallos.`);
    } finally {
      setSyncingMarket(false);
    }
  };

  const refreshFunds = async () => {
    setRefreshingFunds(true);
    try {
      const res = await onRefreshFundCompositions();
      setFeedback(`Fund compositions: ${res.symbols.length} símbolos, ${res.errors.length} fallos.`);
    } finally {
      setRefreshingFunds(false);
    }
  };

  const saveBenchmarkConfig = async () => {
    const symbol = benchmarkKey.trim().toUpperCase();
    if (!symbol) {
      setFeedback('Defina benchmark antes de guardar.');
      return;
    }
    await onSaveMarketDataConfig({ ...data?.market_data.config, benchmark_symbol: symbol, benchmark_label: symbol, benchmark_provider: data?.market_data.provider || 'YFINANCE' });
    setFeedback(`Benchmark configurado: ${symbol}.`);
  };

  const saveCoverageSymbol = async (ticker: string) => {
    const providerSymbol = (symbolDrafts[ticker] || '').trim().toUpperCase();
    if (!providerSymbol) {
      setFeedback(`Defina provider symbol para ${ticker}.`);
      return;
    }
    await onSaveSymbolMapping({ internal_symbol: ticker, provider: data?.market_data.provider || 'YFINANCE', provider_symbol: providerSymbol, instrument_type: 'EQUITY', status: 'ACTIVE' });
    setFeedback(`${ticker} usará ${providerSymbol} en ${data?.market_data.provider || 'provider'}.`);
  };

  const saveAuthority = async (ticker: string, mode: 'AUTO' | 'MANUAL', currency: string) => {
    const raw = manualPriceDrafts[ticker];
    await onSavePriceAuthority({
      ticker,
      authority_mode: mode,
      manual_price: mode === 'MANUAL' ? Number(raw || 0) : undefined,
      manual_currency: mode === 'MANUAL' ? currency : undefined,
    });
    setFeedback(`${ticker}: autoridad ${mode}.`);
  };

  const saveFx = async () => {
    await onSaveFxRate({ ...fxForm, provider: 'MANUAL', source: 'MANUAL' });
    setFeedback(`FX manual ${fxForm.base_currency}/${fxForm.quote_currency} guardado.`);
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
      <section className="a-canvas a-enter">
        <div className="a-page-kicker">Invest</div>
        <p className="a-page-subtitle mt-3">Cargando estado de inversión…</p>
        {children}
      </section>
    );
  }

  return (
    <>
    <section className="a-canvas a-enter">
      {/* =============================================================== */}
      {/* HEADER                                                          */}
      {/* =============================================================== */}
      <header>
        <div className="a-page-kicker">Invest</div>
        <p className="a-page-subtitle mt-3">
          Estado de la cartera, rendimiento y exposición; posiciones operativas y herramientas de mantenimiento sobre datos locales.
        </p>
      </header>

      {feedback && (
        <div role="status" className="a-surface mt-5 p-3 text-xs text-[var(--a-secondary)]">{feedback}</div>
      )}

      {/* =============================================================== */}
      {/* 1 · ESTADO EJECUTIVO: Portfolio dominante → Performance fuerte   */}
      {/*     → Riesgo secundario → Calidad de datos                     */}
      {/* =============================================================== */}
      <section className="a-elevated mt-7 p-5 md:p-6" aria-labelledby="invest-status-title">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h2 id="invest-status-title" className="text-lg font-bold text-[var(--a-text)]">Estado de la cartera</h2>
            <p className="a-meta mt-1">Valor consolidado, rendimiento, riesgo y confianza de los datos.</p>
          </div>
        </div>

        {/* Portfolio dominante | Performance fuerte */}
        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="min-w-0">
            <div className="a-page-kicker">Portfolio</div>
            <div className="mt-3 text-[clamp(34px,4.6vw,54px)] font-[760] leading-none tabular-nums text-[var(--a-text)]">
              {money(data.summary.total_value_usd)}
            </div>
            <div className="mt-4">
              <InlineMetric
                label="P&L no realizado"
                value={money(data.summary.unrealized_pnl_usd)}
                direction={privacyMode ? 'neutral' : signDirection(data.summary.unrealized_pnl_usd)}
              />
            </div>
            <p className="a-meta mt-2">Estado {data.summary.unrealized_pnl_status || 'N/D'} · política {data.history.policy}</p>
          </div>

          <div className={dividerClass}>
            <div className="a-page-kicker">Performance</div>
            <div className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2">
              <InlineMetric label="TWR" value={String(metric(data.performance.twr))} />
              <InlineMetric label="MWR" value={String(metric(data.performance.mwr))} />
              <InlineMetric label="Retorno acumulado" value={String(metric(data.performance.cumulative_return))} />
              <InlineMetric label="P&L realizado" value={money(data.performance.realized_pnl.value_usd)} />
            </div>

            {/* Benchmark (estado real de comparación de desempeño) */}
            <div className="mt-4 border-t border-[var(--a-line)] pt-3">
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Benchmark</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">
                  {data.market_data.benchmark_symbol || 'N/D'} · {data.benchmark.status}
                  {data.benchmark.excess_return_pct !== undefined ? ` · Excess return ${pct(data.benchmark.excess_return_pct)}` : ''}
                </span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Cobertura benchmark</span>
                <span className="text-xs tabular-nums text-[var(--a-text)]">
                  Alineadas {data.benchmark.coverage?.aligned_observations ?? 0} · Portfolio {data.benchmark.coverage?.portfolio_observations ?? 0} · Benchmark {data.benchmark.coverage?.benchmark_observations ?? 0}
                </span>
              </div>
              {data.benchmark.excess_return_pct === undefined && data.benchmark.reason && (
                <p className="a-meta mt-1">{data.benchmark.reason}</p>
              )}
            </div>
          </div>
        </div>

        <div className="my-6 h-px bg-[var(--a-line)]" />

        {/* Riesgo secundario | Calidad de datos */}
        <div className="grid gap-6 md:grid-cols-2">
          <div className="min-w-0">
            <div className="a-page-kicker">Exposición y riesgo</div>
            <div className="mt-3">
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Top activo</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">
                  {data.concentration.top_asset ? `${data.concentration.top_asset.ticker} ${data.concentration.top_asset.allocation_pct}%` : 'N/D'}
                </span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Volatilidad</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">{metric(data.performance.risk.volatility)}</span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Max DD</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">{metric(data.performance.risk.max_drawdown)}</span>
              </div>
            </div>
          </div>

          <div className={dividerClass}>
            <div className="a-page-kicker">Calidad de datos</div>
            <div className="mt-3">
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Historial</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">{data.data_quality.history_coverage_pct}% con historial</span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Datos por completar</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">{data.data_quality.issues.length}</span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Ledger</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">{data.ledger.reconciliation.issues.length} acciones</span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Mercado</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">
                  {data.market_data.provider} · {data.market_data.last_sync_at ? `actualizado ${new Date(data.market_data.last_sync_at).toLocaleString()}` : 'sin sync'}
                </span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Precios</span>
                <span className="text-xs tabular-nums text-[var(--a-text)]">
                  {data.market_data.updated_assets} activos · {data.market_data.fx_pairs} FX · {data.market_data.stale_tickers.length} stale · {data.market_data.missing_tickers.length} missing
                </span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Cobertura</span>
                <span className="text-xs tabular-nums text-[var(--a-text)]">
                  {data.market_data.coverage.summary.holdings_ok}/{data.market_data.coverage.summary.holdings_total} OK · {data.market_data.coverage.summary.fresh_value_pct}% valor fresco · Provider {data.market_data.provider_health}
                </span>
              </div>
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Benchmark coverage</span>
                <span className="text-xs tabular-nums text-[var(--a-text)]">
                  {data.market_data.coverage.summary.benchmark_status} · {data.market_data.coverage.summary.benchmark_observations} obs.
                </span>
              </div>
            </div>
            {data.market_data.last_error && (
              <p className="a-meta mt-2 text-[var(--a-negative)]">Error de mercado: {data.market_data.last_error}</p>
            )}
            <p className="a-meta mt-2">{data.history.policy}</p>
          </div>
        </div>
      </section>

      {/* =============================================================== */}
      {/* 2 · PORTFOLIO X-RAY                                             */}
      {/* =============================================================== */}
      <section className="a-surface mt-5 p-5" aria-labelledby="invest-xray-title">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <h2 id="invest-xray-title" className="text-lg font-bold text-[var(--a-text)]">Portfolio X-Ray</h2>
            <p className="a-meta mt-1">
              {exposure ? `${exposure.status} · Look-through ${exposure.lenses?.underlying_security?.coverage_pct ?? 0}% · ${money(exposure.portfolio_value)}` : 'Sin exposición calculada'}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <SegmentedControl
              label="Lente"
              value={xrayLens}
              options={[
                { value: 'asset_class', label: 'Asset Class' },
                { value: 'sector', label: 'Sector' },
                { value: 'underlying_security', label: 'Underlying' },
              ]}
              onChange={setXrayLens}
            />
            <Button variant="quiet" onClick={refreshFunds} disabled={refreshingFunds}>
              {refreshingFunds ? 'Actualizando...' : 'Refresh funds'}
            </Button>
          </div>
        </div>

        {exposure?.lenses?.[xrayLens] ? (
          <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
            <div className="min-w-0 space-y-2">
              <div className="h-2 overflow-hidden rounded-full bg-[var(--a-canvas)]">
                <div className="h-full bg-[var(--a-brand)]" style={{ width: `${Math.min(100, Math.max(0, exposure.lenses[xrayLens].coverage_pct || 0))}%` }} />
              </div>
              <div className="a-meta">
                Cobertura {exposure.lenses[xrayLens].coverage_pct}% · residual {(exposure.lenses[xrayLens].residual_weight * 100).toFixed(2)}% · opaque {(exposure.lenses[xrayLens].opaque_weight * 100).toFixed(2)}% · unclassified {(exposure.lenses[xrayLens].unclassified_weight * 100).toFixed(2)}%
              </div>
              {exposure.lenses[xrayLens].items.slice(0, 10).map((row) => (
                <details key={row.id} className={boxClass}>
                  <summary className="cursor-pointer">
                    <span className="font-bold text-[var(--a-text)]">{row.label}</span>
                    <span className="float-right text-[var(--a-secondary)]">{row.allocation_pct}% · {money(row.value_usd)}</span>
                  </summary>
                  <div className="mt-2 space-y-1">
                    {row.contributors.map((contributor) => (
                      <div key={`${row.id}-${contributor.source_symbol}-${contributor.effective_weight}`} className="flex justify-between border-t border-[var(--a-line)] pt-1 text-[var(--a-muted)]">
                        <span>{contributor.source_symbol}<span className="text-[var(--a-muted)]"> · source {(contributor.source_weight * 100).toFixed(2)}%</span></span>
                        <span>{(contributor.effective_weight * 100).toFixed(2)}%</span>
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>

            <div className="space-y-2 text-xs">
              <div className={boxClass}>
                <div className="text-[var(--a-muted)]">Opaque</div>
                {(exposure.opaque_positions || []).slice(0, 5).map((row) => (
                  <div key={row.ticker} className="flex justify-between"><span className="text-[var(--a-secondary)]">{row.ticker}</span><span className="tabular-nums text-[var(--a-text)]">{(row.portfolio_weight * 100).toFixed(2)}%</span></div>
                ))}
                {(exposure.opaque_positions || []).length === 0 && <div className="text-[var(--a-muted)]">Sin posiciones opacas.</div>}
              </div>
              <div className={boxClass}>
                <div className="text-[var(--a-muted)]">Intersections</div>
                {(exposure.intersections || []).slice(0, 5).map((row) => (
                  <div key={row.id} className="flex justify-between"><span className="text-[var(--a-secondary)]">{row.label}</span><span className="tabular-nums text-[var(--a-text)]">{row.allocation_pct}%</span></div>
                ))}
                {(exposure.intersections || []).length === 0 && <div className="text-[var(--a-muted)]">Sin exposición compartida.</div>}
              </div>
              <div className={`${boxClass} text-[var(--a-muted)]`}>
                Concentración: {exposure.concentration?.status || 'DEFERRED'}
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-5">
            <DataState
              state="UNEVALUABLE"
              title="X-Ray no evaluable todavía"
              detail="Aún no hay exposición calculada con las lentes disponibles."
            />
          </div>
        )}
      </section>

      {/* =============================================================== */}
      {/* 3 · POSICIONES / WATCHLIST (workspace operativo, slot)          */}
      {/* =============================================================== */}
      {children}

      {/* =============================================================== */}
      {/* 4 · ALLOCATION (cómo está distribuido) | ATRIBUTIÓN (qué        */}
      {/*     explicó el cambio)                                          */}
      {/* =============================================================== */}
      <section className="a-surface mt-5 grid gap-6 p-5 lg:grid-cols-2" aria-label="Distribución y explicación del cambio">
        <div className="min-w-0">
          <h2 className="text-lg font-bold text-[var(--a-text)]">Allocation</h2>
          <p className="a-meta mt-1">Cómo está distribuido el patrimonio por dimensión.</p>
          <div className="mt-4">
            {['asset_type', 'sector', 'country', 'currency'].map((dimension) => (
              <div key={dimension} className="mb-4 last:mb-0">
                <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">{dimension}</div>
                <div className="mt-1">
                  {(data.allocation.dimensions[dimension] || []).slice(0, 4).map((row) => (
                    <div key={`${dimension}-${row.name}`} className={rowClass}>
                      <span className="min-w-0 truncate text-xs text-[var(--a-secondary)]">{row.name || 'Unknown'}</span>
                      <span className="shrink-0 text-xs font-bold tabular-nums text-[var(--a-text)]">{row.allocation_pct}% · {money(row.value_usd)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className={dividerClass}>
          <h2 className="text-lg font-bold text-[var(--a-text)]">Attribution</h2>
          <p className="a-meta mt-1">Qué explicó el cambio del periodo.</p>
          {data.attribution.status !== 'AVAILABLE' && <p className="a-meta mt-3">{data.attribution.reason}</p>}
          {data.attribution.status === 'AVAILABLE' && (
            <div className="mt-4">
              <div className={rowClass}>
                <span className="text-xs text-[var(--a-secondary)]">Cambio</span>
                <span className="text-xs font-bold tabular-nums text-[var(--a-text)]">{money(data.attribution.change_usd)}</span>
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Ganadores</div>
                  <div className="mt-1 space-y-1">
                    {data.attribution.top_winners?.map((row) => (
                      <div key={row.ticker} className="text-xs font-semibold tabular-nums text-[var(--a-positive)]">{row.ticker}: {money(row.contribution_usd)}</div>
                    ))}
                  </div>
                </div>
                <div className="min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Detractores</div>
                  <div className="mt-1 space-y-1">
                    {data.attribution.top_detractors?.map((row) => (
                      <div key={row.ticker} className="text-xs font-semibold tabular-nums text-[var(--a-negative)]">{row.ticker}: {money(row.contribution_usd)}</div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* =============================================================== */}
      {/* 5 · ATENCIÓN / ACTION CENTER                                    */}
      {/* =============================================================== */}
      <section className="a-surface mt-5 p-5" aria-labelledby="invest-attention-title">
        <h2 id="invest-attention-title" className="a-page-kicker">Atención</h2>
        <p className="a-meta mt-1">Señales de Wealth: qué requiere revisión y por qué.</p>
        <div className="mt-4">
          {data.action_items.length === 0 && (
            <DataState state="EMPTY" title="Sin acciones pendientes de Wealth." detail="No hay señales abiertas en esta fuente." />
          )}
          {data.action_items.slice(0, 8).map((item, idx) => (
            <div key={`${item.type}-${idx}`} className="border-b border-[var(--a-line)] py-2.5 last:border-b-0">
              <div className="text-xs font-semibold text-[var(--a-text)]">{item.title}</div>
              <div className="a-meta mt-0.5">{item.why}</div>
              <div className="mt-1 text-xs font-semibold text-[var(--a-brand)]">{item.action}</div>
            </div>
          ))}
        </div>
      </section>

      {/* =============================================================== */}
      {/* TOOLS · lanzadores (una familia activa por contexto)            */}
      {/* =============================================================== */}
      <section className="a-surface mt-5 p-5" aria-labelledby="invest-tools-title">
        <h2 id="invest-tools-title" className="a-page-kicker">Herramientas</h2>
        <p className="a-meta mt-1">Abre un instrumento sin perder el contexto de cartera, rendimiento y posiciones.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Button
            ref={thesisLauncherRef}
            variant={openTool === 'thesis' ? 'operational' : 'quiet'}
            aria-pressed={openTool === 'thesis'}
            aria-controls="invest-thesis-dock"
            onClick={() => onOpenTool(openTool === 'thesis' ? null : 'thesis')}
          >
            Tesis de inversión
          </Button>
          <Button
            ref={rebalanceLauncherRef}
            variant={openTool === 'rebalance' ? 'operational' : 'quiet'}
            aria-pressed={openTool === 'rebalance'}
            aria-controls="invest-rebalance-dock"
            onClick={() => onOpenTool(openTool === 'rebalance' ? null : 'rebalance')}
          >
            Rebalance Planner
          </Button>
          <Button
            ref={ledgerLauncherRef}
            variant={openTool === 'ledger' ? 'operational' : 'quiet'}
            aria-pressed={openTool === 'ledger'}
            aria-controls="invest-ledger-dock"
            onClick={() => onOpenTool(openTool === 'ledger' ? null : 'ledger')}
          >
            Investment Ledger
          </Button>
          <Button
            ref={marketLauncherRef}
            variant={openTool === 'market' ? 'operational' : 'quiet'}
            aria-pressed={openTool === 'market'}
            aria-controls="invest-market-dock"
            onClick={() => onOpenTool(openTool === 'market' ? null : 'market')}
          >
            Market Data
          </Button>
        </div>
      </section>
      </section>

      {/* =============================================================== */}
      {/* DOCK · Rebalance Planner                                         */}
      {/* =============================================================== */}
      {openTool === 'rebalance' && (
        <ToolSurfaceDock
          id="invest-rebalance-dock"
          title="Rebalance Planner"
          description="Tradicional y con nuevos aportes; no ejecuta operaciones."
          triggerRef={rebalanceLauncherRef}
          onClose={() => onOpenTool(null)}
        >
          <div className="space-y-4">
            <div className="flex items-end gap-2">
              <div className="min-w-0 flex-1">
                <MoneyField
                  id="invest-rebalance-contribution"
                  label="Aporte nuevo"
                  value={contribution}
                  onChange={setContribution}
                  currency="USD"
                  allowNegative
                />
              </div>
              <Button variant="operational" onClick={() => onRefresh(contribution, benchmarkKey || undefined)}>
                Calcular
              </Button>
            </div>

            {data.rebalancing.status !== 'AVAILABLE' && <p className="a-meta">{data.rebalancing.reason}</p>}

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[var(--a-line)] text-[10px] uppercase tracking-wider text-[var(--a-muted)]">
                  <tr>
                    <th className="py-2 pr-2">Activo</th>
                    <th className="py-2 pr-2">Actual</th>
                    <th className="py-2 pr-2">Meta</th>
                    <th className="py-2 pr-2">Desvío</th>
                    <th className="py-2 pr-2">Compra/Venta</th>
                    <th className="py-2">Aporte</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--a-line)]">
                  {data.rebalancing.traditional.map((row) => {
                    const aport = data.rebalancing.new_contribution.find((item) => item.ticker === row.ticker);
                    return (
                      <tr key={row.ticker}>
                        <td className="py-2 pr-2 font-bold text-[var(--a-text)]">{row.ticker}</td>
                        <td className="py-2 pr-2 tabular-nums text-[var(--a-secondary)]">{row.current_pct}%</td>
                        <td className="py-2 pr-2 tabular-nums text-[var(--a-secondary)]">{row.target_pct}%</td>
                        <td className="py-2 pr-2 tabular-nums text-[var(--a-secondary)]">{row.drift_pct} pp</td>
                        <td className="py-2 pr-2 tabular-nums text-[var(--a-text)]">{money(row.trade_usd)}</td>
                        <td className="py-2 tabular-nums text-[var(--a-text)]">{money(aport?.contribution_usd || 0)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </ToolSurfaceDock>
      )}

      {/* =============================================================== */}
      {/* DOCK · Investment Ledger / Reconciliation                        */}
      {/* =============================================================== */}
      {openTool === 'ledger' && (
        <ToolSurfaceDock
          id="invest-ledger-dock"
          title="Investment Ledger"
          description="Operaciones, importación CSV y reconciliación de posiciones."
          triggerRef={ledgerLauncherRef}
          onClose={() => onOpenTool(null)}
        >
          <div className="space-y-5">
            {/* Registrar operación */}
            <div className="space-y-3">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Registrar operación</div>
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label htmlFor="invest-op-date" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Fecha</label>
                  <input
                    id="invest-op-date"
                    type="date"
                    value={opForm.occurred_at || ''}
                    onChange={(e) => setOpForm({ ...opForm, occurred_at: e.target.value })}
                    className="min-h-10 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] focus:border-[var(--a-brand)] focus:outline-none"
                  />
                </div>
                <div>
                  <label htmlFor="invest-op-type" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Tipo</label>
                  <select
                    id="invest-op-type"
                    value={opForm.operation_type || 'BUY'}
                    onChange={(e) => setOpForm({ ...opForm, operation_type: e.target.value as InvestmentOperation['operation_type'] })}
                    className="min-h-10 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] focus:border-[var(--a-brand)] focus:outline-none"
                  >
                    {['CONTRIBUTION', 'WITHDRAWAL', 'BUY', 'SELL', 'DIVIDEND', 'INTEREST', 'FEE', 'TRANSFER_IN', 'TRANSFER_OUT'].map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </div>
                <Field
                  id="invest-op-ticker"
                  label="Ticker"
                  value={opForm.ticker || ''}
                  onChange={(value) => setOpForm({ ...opForm, ticker: value.toUpperCase() })}
                />
                <Field
                  id="invest-op-currency"
                  label="Moneda"
                  value={opForm.currency || 'USD'}
                  onChange={(value) => setOpForm({ ...opForm, currency: value.toUpperCase() })}
                />
                <MetricInput
                  id="invest-op-quantity"
                  label="Cantidad"
                  unit="uds"
                  value={Number(opForm.quantity ?? 0)}
                  onChange={(value) => setOpForm({ ...opForm, quantity: value === '' ? 0 : value })}
                  allowNegative
                />
                <MetricInput
                  id="invest-op-price"
                  label="Precio"
                  unit={opForm.currency || 'USD'}
                  value={Number(opForm.price ?? 0)}
                  onChange={(value) => setOpForm({ ...opForm, price: value === '' ? 0 : value })}
                  allowNegative
                />
                <MoneyField
                  id="invest-op-amount"
                  label="Importe"
                  value={Number(opForm.amount ?? 0)}
                  onChange={(value) => setOpForm({ ...opForm, amount: value })}
                  currency={opForm.currency || 'USD'}
                  allowNegative
                />
                <MoneyField
                  id="invest-op-fee"
                  label="Fee"
                  value={Number(opForm.fee ?? 0)}
                  onChange={(value) => setOpForm({ ...opForm, fee: value })}
                  currency={opForm.currency || 'USD'}
                  allowNegative
                />
              </div>
              <Field
                id="invest-op-notes"
                label="Notas"
                value={opForm.notes || ''}
                onChange={(value) => setOpForm({ ...opForm, notes: value })}
              />
              <Button variant="primary" className="w-full" onClick={saveOperation}>
                Guardar operación
              </Button>
            </div>

            {/* Actividad */}
            <div className="border-t border-[var(--a-line)] pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Actividad</div>
              <p className="a-meta mt-1">CONTRIBUTION/WITHDRAWAL son cashflows externos; BUY/SELL son operaciones internas.</p>
              <div className="mt-3">
                <Field
                  id="invest-ledger-filter"
                  label="Filtrar ticker/tipo"
                  value={ledgerFilter}
                  onChange={(value) => setLedgerFilter(value.toUpperCase())}
                />
              </div>
              <div className="mt-2 overflow-x-auto max-h-64">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-[var(--a-line)] text-[10px] uppercase tracking-wider text-[var(--a-muted)]">
                    <tr>
                      <th className="py-2 pr-2">Fecha</th>
                      <th className="py-2 pr-2">Tipo</th>
                      <th className="py-2 pr-2">Ticker</th>
                      <th className="py-2 pr-2">Cantidad</th>
                      <th className="py-2 pr-2">Precio</th>
                      <th className="py-2 pr-2">Importe</th>
                      <th className="py-2 pr-2">Fuente</th>
                      <th className="py-2"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--a-line)]">
                    {data.ledger.operations
                      .filter((op) => !ledgerFilter || `${op.ticker || ''} ${op.operation_type}`.includes(ledgerFilter))
                      .slice(-50)
                      .reverse()
                      .map((op) => (
                        <tr key={op.id}>
                          <td className="py-2 pr-2 tabular-nums text-[var(--a-secondary)]">{op.occurred_at.slice(0, 10)}</td>
                          <td className="py-2 pr-2 font-bold text-[var(--a-text)]">{op.operation_type}</td>
                          <td className="py-2 pr-2 text-[var(--a-text)]">{op.ticker || '-'}</td>
                          <td className="py-2 pr-2 tabular-nums text-[var(--a-secondary)]">{op.quantity}</td>
                          <td className="py-2 pr-2 tabular-nums text-[var(--a-secondary)]">{money(op.price)}</td>
                          <td className="py-2 pr-2 tabular-nums text-[var(--a-text)]">{money(op.amount)}</td>
                          <td className="py-2 pr-2 text-[var(--a-muted)]">{op.source}</td>
                          <td className="py-2">
                            <Button
                              variant="negative"
                              className="px-2.5 py-1.5"
                              onClick={() => window.confirm('Eliminar operación?') && onDeleteInvestmentOperation(op.id)}
                            >
                              Eliminar
                            </Button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Import CSV */}
            <div className="border-t border-[var(--a-line)] pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Import CSV ledger</div>
              <div className="mt-3 space-y-2.5">
                <label htmlFor="invest-ledger-csv" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">CSV de operaciones</label>
                <textarea
                  id="invest-ledger-csv"
                  rows={3}
                  placeholder="date,ticker,type,quantity,price,amount,fee,currency,account_id,external_id&#10;2026-01-01,NVDA,BUY,10,100,1000,1,USD,,trade-1"
                  value={ledgerCsv}
                  onChange={(e) => setLedgerCsv(e.target.value)}
                  className="min-h-20 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3 text-xs leading-relaxed text-[var(--a-text)] placeholder:text-[var(--a-muted)] focus:border-[var(--a-brand)] focus:outline-none"
                />
                <div className="flex gap-2">
                  <Button variant="quiet" className="flex-1" onClick={previewLedger}>Preview</Button>
                  <Button variant="primary" className="flex-1" onClick={importLedger}>Importar</Button>
                </div>
              </div>
            </div>

            {/* Reconciliation */}
            <div className="border-t border-[var(--a-line)] pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Portfolio → Reconciliation</div>
              <div className="mt-3 space-y-1 max-h-40 overflow-auto">
                {data.ledger.reconciliation.rows.map((row) => (
                  <button
                    key={row.ticker}
                    onClick={() => setSelectedRecon(selectedRecon === row.ticker ? null : row.ticker)}
                    className="w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2 text-left text-xs transition-colors hover:bg-[var(--a-hover)]"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-bold text-[var(--a-text)]">{row.ticker}</span>
                      <span className={row.status === 'MATCH' ? 'font-bold text-[var(--a-positive)]' : 'font-bold text-[var(--a-warning)]'}>{row.status}</span>
                      <span className="tabular-nums text-[var(--a-secondary)]">hold {row.registered_quantity} / ledger {row.derived_quantity}</span>
                      <span className="tabular-nums text-[var(--a-secondary)]">avg {row.registered_avg_price} / {row.derived_avg_price}</span>
                      <span className="text-[var(--a-muted)]">{row.coverage} · {row.source}</span>
                    </div>
                    {selectedRecon === row.ticker && (
                      <div className="mt-2 space-y-2 border-t border-[var(--a-line)] pt-2">
                        <div className="text-[var(--a-secondary)]">
                          Fuente actual: {row.source}. Autoridad: {row.authority_state}. Diff qty: {row.quantity_diff}; diff avg: {row.avg_price_diff}.
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button variant="quiet" className="px-2.5 py-1.5" onClick={(e) => { e.stopPropagation(); registerOpeningFromRow(row); }}>Registrar posición inicial</Button>
                          <Button variant="quiet" className="px-2.5 py-1.5" onClick={(e) => { e.stopPropagation(); createAdjustment(row); }}>Adjustment explícito</Button>
                          <Button variant="positive" className="px-2.5 py-1.5" disabled={row.status !== 'MATCH'} onClick={(e) => { e.stopPropagation(); adoptLedger(row.ticker); }}>Adoptar Ledger</Button>
                          <Button variant="quiet" className="px-2.5 py-1.5" onClick={(e) => { e.stopPropagation(); keepManual(row.ticker); }}>Mantener manual</Button>
                        </div>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </ToolSurfaceDock>
      )}

      {/* =============================================================== */}
      {/* DOCK · Market Data                                              */}
      {/* =============================================================== */}
      {openTool === 'market' && (
        <ToolSurfaceDock
          id="invest-market-dock"
          title="Market Data"
          description="Sincronización, cobertura de precios, valoraciones manuales, benchmark y FX."
          triggerRef={marketLauncherRef}
          onClose={() => onOpenTool(null)}
        >
          <div className="space-y-5">
            {/* Sincronización */}
            <div className="space-y-3">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Sincronización</div>
              <div className="flex flex-wrap gap-2">
                <Button variant="operational" disabled={syncingMarket} onClick={() => syncMarket('QUICK')}>
                  <span className="inline-flex items-center gap-2">
                    <RefreshCw className={`h-4 w-4 ${syncingMarket ? 'animate-spin' : ''}`} aria-hidden="true" />
                    Quick refresh
                  </span>
                </Button>
                <Button variant="quiet" disabled={syncingMarket} onClick={() => syncMarket('FULL')}>
                  Full history
                </Button>
              </div>
            </div>

            {/* Cobertura por activo */}
            <div className="border-t border-[var(--a-line)] pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Cobertura por activo</div>
              <div className="mt-3 space-y-3">
                {data.market_data.coverage.rows.map((row) => (
                  <div key={row.ticker} className="rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-[var(--a-text)]">{row.ticker}</span>
                      <span className={row.status === 'OK' ? 'text-xs font-bold text-[var(--a-positive)]' : 'text-xs font-bold text-[var(--a-warning)]'}>{row.status}</span>
                    </div>
                    <div className="a-meta">Precio: {money(row.current_price)} · {row.freshness} · {row.price_source}</div>
                    <div className="a-meta">Provider symbol: {row.provider_symbol || 'Sin resolver'} · Historial {row.history_count} · FX {row.fx_status}</div>
                    <div className="grid grid-cols-[1fr_auto] gap-2">
                      <input
                        aria-label={`Provider symbol para ${row.ticker}`}
                        placeholder={row.provider_symbol || row.ticker}
                        value={symbolDrafts[row.ticker] ?? ''}
                        onChange={(e) => setSymbolDrafts({ ...symbolDrafts, [row.ticker]: e.target.value.toUpperCase() })}
                        className="min-h-10 min-w-0 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-surface)] px-3 py-2 text-sm text-[var(--a-text)] placeholder:text-[var(--a-muted)] focus:border-[var(--a-brand)] focus:outline-none"
                      />
                      <Button variant="quiet" onClick={() => saveCoverageSymbol(row.ticker)}>Símbolo</Button>
                    </div>
                    <MetricInput
                      id={`invest-manual-price-${row.ticker}`}
                      label="Precio manual"
                      unit={row.currency || 'USD'}
                      value={Number(manualPriceDrafts[row.ticker] || 0)}
                      onChange={(value) => setManualPriceDrafts({ ...manualPriceDrafts, [row.ticker]: value === '' ? '' : String(value) })}
                    />
                    <div className="flex gap-2">
                      <Button variant="quiet" className="flex-1" onClick={() => saveAuthority(row.ticker, 'MANUAL', row.currency || 'USD')}>MANUAL</Button>
                      <Button variant="operational" className="flex-1" onClick={() => saveAuthority(row.ticker, 'AUTO', row.currency || 'USD')}>AUTO</Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Histórico manual / CSV */}
            <div className="border-t border-[var(--a-line)] pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Histórico manual / CSV</div>
              <div className="mt-3 space-y-2.5">
                <label htmlFor="invest-valuation-csv" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Valoraciones CSV</label>
                <textarea
                  id="invest-valuation-csv"
                  rows={3}
                  placeholder="ticker,date,price,currency&#10;NVDA,2026-09-01,120,USD"
                  value={valuationCsv}
                  onChange={(e) => setValuationCsv(e.target.value)}
                  className="min-h-20 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3 text-xs leading-relaxed text-[var(--a-text)] placeholder:text-[var(--a-muted)] focus:border-[var(--a-brand)] focus:outline-none"
                />
                <Button variant="primary" className="w-full" onClick={importValuations}>
                  <span className="inline-flex items-center gap-2">
                    <Upload className="h-4 w-4" aria-hidden="true" />
                    Importar valoraciones
                  </span>
                </Button>
              </div>
            </div>

            {/* Benchmark */}
            <div className="border-t border-[var(--a-line)] pt-4">
              <div className="flex items-center justify-between gap-2">
                <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">Benchmark</div>
                <Button
                  variant="quiet"
                  className="px-2.5"
                  aria-label="Recalcular wealth con el benchmark actual"
                  onClick={() => onRefresh(contribution, benchmarkKey || undefined)}
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
              <div className="mt-3 space-y-2.5">
                <Field
                  id="invest-benchmark-key"
                  label="Benchmark key"
                  placeholder={`Actual: ${data.market_data.benchmark_symbol || 'sin benchmark'}`}
                  value={benchmarkKey}
                  onChange={(value) => setBenchmarkKey(value.toUpperCase())}
                />
                <Button variant="quiet" className="w-full" onClick={saveBenchmarkConfig}>Guardar benchmark</Button>
                <label htmlFor="invest-benchmark-csv" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Benchmark CSV</label>
                <textarea
                  id="invest-benchmark-csv"
                  rows={2}
                  placeholder="date,price,currency&#10;2026-09-01,100,USD"
                  value={benchmarkCsv}
                  onChange={(e) => setBenchmarkCsv(e.target.value)}
                  className="min-h-16 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3 text-xs leading-relaxed text-[var(--a-text)] placeholder:text-[var(--a-muted)] focus:border-[var(--a-brand)] focus:outline-none"
                />
                <Button variant="quiet" className="w-full" onClick={importBenchmark}>
                  <span className="inline-flex items-center gap-2">
                    <GitCompare className="h-4 w-4" aria-hidden="true" />
                    Importar benchmark
                  </span>
                </Button>
              </div>
            </div>

            {/* FX manual */}
            <div className="border-t border-[var(--a-line)] pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">FX manual</div>
              <div className="mt-3 space-y-2.5">
                <div className="grid grid-cols-2 gap-2.5">
                  <Field
                    id="invest-fx-base"
                    label="Base"
                    value={fxForm.base_currency}
                    onChange={(value) => setFxForm({ ...fxForm, base_currency: value.toUpperCase() })}
                  />
                  <Field
                    id="invest-fx-quote"
                    label="Quote"
                    value={fxForm.quote_currency}
                    onChange={(value) => setFxForm({ ...fxForm, quote_currency: value.toUpperCase() })}
                  />
                </div>
                <div>
                  <label htmlFor="invest-fx-date" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Fecha</label>
                  <input
                    id="invest-fx-date"
                    type="date"
                    value={fxForm.rate_date}
                    onChange={(e) => setFxForm({ ...fxForm, rate_date: e.target.value })}
                    className="min-h-10 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] focus:border-[var(--a-brand)] focus:outline-none"
                  />
                </div>
                <MetricInput
                  id="invest-fx-rate"
                  label="Rate"
                  unit={`${fxForm.base_currency || 'BASE'}/${fxForm.quote_currency || 'QUOTE'}`}
                  value={Number(fxForm.rate || 0)}
                  onChange={(value) => setFxForm({ ...fxForm, rate: value === '' ? 0 : value })}
                />
                <Button variant="quiet" className="w-full" onClick={saveFx}>Guardar FX</Button>
                <p className="a-meta">Pares faltantes: {data.market_data.coverage.summary.missing_fx.join(', ') || 'Ninguno'}</p>
              </div>
            </div>
          </div>
        </ToolSurfaceDock>
      )}
    </>
  );
};
