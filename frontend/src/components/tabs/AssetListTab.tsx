import React, { useState } from 'react';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { Field, SegmentedControl } from '../../aetheris/controls';
import { Asset } from '../../types';

interface AssetListTabProps {
  assets: Asset[];
  currency: 'USD' | 'COP';
  exchangeRate: number;
  onSelectForSimulation: (ticker: string) => void;
  privacyMode?: boolean;
}

export const AssetListTab: React.FC<AssetListTabProps> = ({
  assets,
  currency,
  exchangeRate,
  onSelectForSimulation,
  privacyMode = false
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('ALL');
  const [viewMode, setViewMode] = useState<'PORTFOLIO' | 'WATCHLIST'>('PORTFOLIO');

  const filteredAssets = assets.filter((a) => {
    const isWatchlist = Boolean(a.is_watchlist);
    if (viewMode === 'PORTFOLIO' && isWatchlist) return false;
    if (viewMode === 'WATCHLIST' && !isWatchlist) return false;

    if (filterType !== 'ALL' && a.asset_type !== filterType) return false;

    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      return a.ticker.toLowerCase().includes(q) || a.name.toLowerCase().includes(q) || a.sector.toLowerCase().includes(q);
    }
    return true;
  });

  const formatPrice = (priceUsd: number, assetCurrency: string = 'USD') => {
    if (privacyMode) return '••••';
    if (currency === 'USD') {
      return `$${priceUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
    } else {
      const copPrice = assetCurrency === 'COP' ? priceUsd : priceUsd * exchangeRate;
      return `$${copPrice.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} COP`;
    }
  };

  const totalValue = assets
    .filter((a) => !a.is_watchlist)
    .reduce((acc, a) => acc + (a.market_value_usd || 0), 0);

  const selectClass = 'min-h-10 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] focus:border-[var(--a-brand)] focus:outline-none';

  return (
    <section className="a-surface mt-5 p-5 space-y-4" aria-labelledby="invest-positions-title">
      <div className="min-w-0">
        <h2 id="invest-positions-title" className="text-lg font-bold text-[var(--a-text)]">Posiciones</h2>
        <p className="a-meta mt-1">Cartera activa y activos en observación sobre datos locales.</p>
      </div>

      {/* Toolbar: vista · búsqueda · tipo */}
      <div className="flex flex-col gap-3 border-b border-[var(--a-line)] pb-4 md:flex-row md:items-end md:justify-between">
        <SegmentedControl
          label="Vista"
          value={viewMode}
          options={[
            { value: 'PORTFOLIO', label: 'Portafolio Activo' },
            { value: 'WATCHLIST', label: 'Activos en Observación' },
          ]}
          onChange={setViewMode}
        />

        <div className="flex flex-wrap items-end gap-2.5">
          <div className="min-w-0 md:w-64">
            <Field
              id="invest-asset-search"
              label="Buscar"
              placeholder="Ticker, activo o sector"
              value={searchTerm}
              onChange={setSearchTerm}
            />
          </div>

          <div className="min-w-0">
            <label htmlFor="invest-type-filter" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Tipo</label>
            <select
              id="invest-type-filter"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className={selectClass}
            >
              <option value="ALL">Todos los Tipos</option>
              <option value="Renta Variable">Renta Variable</option>
              <option value="Efectivo">Efectivo</option>
              <option value="Alternativos">Alternativos</option>
            </select>
          </div>
        </div>
      </div>

      {/* Tabla de posiciones / watchlist */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-[var(--a-line)] text-[10px] uppercase tracking-wider font-semibold text-[var(--a-muted)]">
              <th className="py-2.5 px-3">Activo / Ticker</th>
              <th className="py-2.5 px-3">Categoría &bull; Sector</th>
              <th className="py-2.5 px-3 text-right">Precio Actual</th>
              <th className="py-2.5 px-3 text-right">Precio Promedio Compra</th>
              <th className="py-2.5 px-3 text-right">Ponderación %</th>
              <th className="py-2.5 px-3 text-right">Retorno Total (P&amp;L)</th>
              <th className="py-2.5 px-3 text-center">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--a-line)]">
            {filteredAssets.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-[var(--a-muted)] text-xs">
                  No se encontraron activos con los filtros seleccionados.
                </td>
              </tr>
            ) : (
              filteredAssets.map((asset) => {
                const pnlPct = asset.unrealized_pnl_pct || 0;
                const pnlUsd = asset.unrealized_pnl_usd || 0;
                const isPositive = pnlPct >= 0;
                const isWatchlist = Boolean(asset.is_watchlist);
                const allocationPct = totalValue > 0 && !isWatchlist
                  ? (((asset.market_value_usd || 0) / totalValue) * 100).toFixed(1)
                  : '0.0';

                return (
                  <tr key={asset.ticker} className="transition-colors hover:bg-[var(--a-hover)]">
                    {/* Ticker & Logo */}
                    <td className="py-2.5 px-3">
                      <div className="flex items-center space-x-2.5">
                        {asset.logo_url ? (
                          <img
                            src={asset.logo_url}
                            alt={asset.ticker}
                            className="w-7 h-7 rounded-lg border border-[var(--a-line)] bg-[var(--a-canvas)] object-contain p-0.5"
                            onError={(e) => {
                              // Fallback if logo fails
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                        ) : (
                          <div className="w-7 h-7 rounded-lg border border-[var(--a-line)] bg-[var(--a-canvas)] text-[var(--a-secondary)] flex items-center justify-center font-bold text-xs">
                            {asset.ticker.slice(0, 2)}
                          </div>
                        )}
                        <div>
                          <div className="font-bold text-[var(--a-text)] flex items-center gap-1.5">
                            {asset.ticker}
                            {isWatchlist && (
                              <span className="rounded-full border border-[var(--a-line-strong)] bg-[var(--a-canvas)] px-1.5 py-0.5 text-[9px] font-bold text-[var(--a-analytical)]">
                                Observación
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-[var(--a-secondary)] truncate max-w-[140px]">
                            {asset.name}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Category & Sector */}
                    <td className="py-2.5 px-3">
                      <div className="text-[var(--a-text)] font-medium text-xs">{asset.asset_type}</div>
                      <div className="text-[10px] text-[var(--a-secondary)]">{asset.sector} &bull; {asset.country}</div>
                    </td>

                    {/* Current Price */}
                    <td className="py-2.5 px-3 text-right font-bold text-[var(--a-text)] tabular-nums">
                      {formatPrice(asset.current_price, asset.currency)}
                    </td>

                    {/* Avg Buy Price */}
                    <td className="py-2.5 px-3 text-right text-[var(--a-secondary)] tabular-nums">
                      {asset.avg_price > 0 ? formatPrice(asset.avg_price, asset.currency) : '—'}
                    </td>

                    {/* Allocation */}
                    <td className="py-2.5 px-3 text-right">
                      <span className="font-bold text-[var(--a-text)] tabular-nums">{allocationPct}%</span>
                      {asset.target_allocation_pct && asset.target_allocation_pct > 0 && (
                        <div className="text-[10px] text-[var(--a-muted)] tabular-nums">Meta: {asset.target_allocation_pct}%</div>
                      )}
                    </td>

                    {/* Return Total P&L */}
                    <td className="py-2.5 px-3 text-right">
                      {isWatchlist || asset.quantity === 0 ? (
                        <span className="text-[var(--a-muted)] text-[11px]">—</span>
                      ) : (
                        <div>
                          <div className={`font-bold flex items-center justify-end gap-0.5 tabular-nums ${isPositive ? 'text-[var(--a-positive)]' : 'text-[var(--a-negative)]'}`}>
                            {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                            {isPositive ? '+' : ''}{pnlPct}%
                          </div>
                          <div className="text-[10px] text-[var(--a-secondary)] tabular-nums">
                            {privacyMode ? '••••' : `${isPositive ? '+' : ''}$${pnlUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`}
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Action: contextual thesis / simulation */}
                    <td className="py-2.5 px-3 text-center">
                      <button
                        type="button"
                        onClick={() => onSelectForSimulation(asset.ticker)}
                        className="min-h-10 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-surface)] px-2.5 py-1.5 text-[11px] font-bold text-[var(--a-secondary)] transition-colors hover:bg-[var(--a-elevated)] [@media(pointer:coarse)]:min-h-11"
                      >
                        Simular / Tesis
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};
