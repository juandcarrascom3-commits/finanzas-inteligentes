import React, { useState } from 'react';
import { Search, Filter, ArrowUpRight, ArrowDownRight, Eye, Shield, DollarSign } from 'lucide-react';
import { Asset } from '../../types';

interface AssetListTabProps {
  assets: Asset[];
  currency: 'USD' | 'COP';
  exchangeRate: number;
  onSelectForSimulation: (ticker: string) => void;
}

export const AssetListTab: React.FC<AssetListTabProps> = ({
  assets,
  currency,
  exchangeRate,
  onSelectForSimulation
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

  return (
    <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg space-y-4">
      {/* Header Controls: Search, Type filter, Portfolio vs Watchlist toggle */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 pb-3 border-b border-gray-800">
        <div className="flex items-center space-x-2">
          {/* Portfolio vs Watchlist tabs */}
          <div className="flex bg-gray-900 p-0.5 rounded-lg border border-gray-800 text-xs">
            <button
              onClick={() => setViewMode('PORTFOLIO')}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                viewMode === 'PORTFOLIO' ? 'bg-emerald-600 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Portafolio Activo
            </button>
            <button
              onClick={() => setViewMode('WATCHLIST')}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all flex items-center gap-1.5 ${
                viewMode === 'WATCHLIST' ? 'bg-purple-600 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              Activos en Observación
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Search Input */}
          <div className="relative flex-1 md:w-56">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-500" />
            <input
              type="text"
              placeholder="Buscar ticker, activo..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-gray-900 border border-gray-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* Type Filter */}
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-gray-900 border border-gray-800 rounded-lg px-2.5 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-emerald-500"
          >
            <option value="ALL">Todos los Tipos</option>
            <option value="Renta Variable">Renta Variable</option>
            <option value="Efectivo">Efectivo</option>
            <option value="Alternativos">Alternativos</option>
          </select>
        </div>
      </div>

      {/* Asset Grid Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-gray-800 text-gray-400 uppercase text-[10px] tracking-wider font-semibold">
              <th className="py-3 px-3">Activo / Ticker</th>
              <th className="py-3 px-3">Categoría &bull; Sector</th>
              <th className="py-3 px-3 text-right">Precio Actual</th>
              <th className="py-3 px-3 text-right">Precio Promedio Compra</th>
              <th className="py-3 px-3 text-right">Ponderación %</th>
              <th className="py-3 px-3 text-right">Retorno Total (P&amp;L)</th>
              <th className="py-3 px-3 text-center">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60 font-mono">
            {filteredAssets.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-8 text-center text-gray-500 text-xs font-sans">
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
                  <tr key={asset.ticker} className="hover:bg-gray-800/40 transition-colors">
                    {/* Ticker & Logo */}
                    <td className="py-3 px-3 font-sans">
                      <div className="flex items-center space-x-2.5">
                        {asset.logo_url ? (
                          <img
                            src={asset.logo_url}
                            alt={asset.ticker}
                            className="w-7 h-7 rounded-lg bg-gray-800 object-contain p-0.5 border border-gray-700"
                            onError={(e) => {
                              // Fallback if logo fails
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                        ) : (
                          <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs">
                            {asset.ticker.slice(0, 2)}
                          </div>
                        )}
                        <div>
                          <div className="font-bold text-white flex items-center gap-1.5">
                            {asset.ticker}
                            {isWatchlist && (
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                Observación
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-gray-400 truncate max-w-[140px]">
                            {asset.name}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Category & Sector */}
                    <td className="py-3 px-3 font-sans">
                      <div className="text-gray-200 font-medium text-xs">{asset.asset_type}</div>
                      <div className="text-[10px] text-gray-400">{asset.sector} &bull; {asset.country}</div>
                    </td>

                    {/* Current Price */}
                    <td className="py-3 px-3 text-right font-bold text-white">
                      {formatPrice(asset.current_price, asset.currency)}
                    </td>

                    {/* Avg Buy Price */}
                    <td className="py-3 px-3 text-right text-gray-300">
                      {asset.avg_price > 0 ? formatPrice(asset.avg_price, asset.currency) : '—'}
                    </td>

                    {/* Allocation */}
                    <td className="py-3 px-3 text-right font-sans">
                      <span className="font-mono font-bold text-emerald-400">{allocationPct}%</span>
                      {asset.target_allocation_pct && asset.target_allocation_pct > 0 && (
                        <div className="text-[10px] text-gray-500 font-mono">Meta: {asset.target_allocation_pct}%</div>
                      )}
                    </td>

                    {/* Return Total P&L */}
                    <td className="py-3 px-3 text-right">
                      {isWatchlist || asset.quantity === 0 ? (
                        <span className="text-gray-500 text-[11px]">—</span>
                      ) : (
                        <div>
                          <div className={`font-bold flex items-center justify-end gap-0.5 ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                            {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                            {isPositive ? '+' : ''}{pnlPct}%
                          </div>
                          <div className="text-[10px] text-gray-400">
                            {isPositive ? '+' : ''}${pnlUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Action Button: Simulate Purchase / Guardrail */}
                    <td className="py-3 px-3 text-center font-sans">
                      <button
                        onClick={() => onSelectForSimulation(asset.ticker)}
                        className="px-2.5 py-1 rounded bg-gray-800 hover:bg-emerald-600/20 hover:text-emerald-400 text-gray-300 border border-gray-700 hover:border-emerald-500/40 text-[11px] font-semibold transition-all"
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
    </div>
  );
};
