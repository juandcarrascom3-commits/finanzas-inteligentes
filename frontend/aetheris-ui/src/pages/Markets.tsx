import React, { useEffect, useState } from 'react';
import { fetchAssets } from '../services/api';
import type { Asset } from '../types';

interface IndexCardProps {
  label: string;
  value: string;
  change: string;
  positive: boolean;
}

const IndexCard: React.FC<IndexCardProps> = ({ label, value, change, positive }) => (
  <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4 flex items-center justify-between">
    <div>
      <p className="text-xs text-gray-400 font-medium">{label}</p>
      <h3 className="text-lg font-bold text-white">{value}</h3>
    </div>
    <span
      className={[
        'px-2.5 py-1 rounded-lg text-xs font-semibold',
        positive
          ? 'bg-teal-500/10 text-emerald-400 border border-teal-500/20'
          : 'bg-rose-400/10 text-rose-400 border border-rose-500/20',
      ].join(' ')}
    >
      {change}
    </span>
  </div>
);

interface AssetRowProps {
  ticker: string;
  name: string;
  price: number;
  changePct: number;
  marketValue: number;
  assetType: string;
  isWatchlist: boolean;
}

const AssetRow: React.FC<AssetRowProps> = ({ ticker, name, price, changePct, marketValue, assetType, isWatchlist }) => {
  const isPositive = changePct >= 0;
  
  // Sparklines dinámicos simulados según tendencia
  const positivePath = 'M 2,24 C 14,20 22,12 34,14 C 44,16 52,8 62,4';
  const negativePath = 'M 2,6 C 14,10 22,18 34,16 C 44,14 52,22 62,28';

  return (
    <div className="flex items-center justify-between py-3.5 px-3 border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] transition-all rounded-xl">
      {/* Ticker & Name */}
      <div className="flex items-center gap-3 min-w-[180px]">
        <div className="w-9 h-9 rounded-xl bg-white/[0.05] border border-white/10 flex items-center justify-center text-xs font-bold text-[#38e1e7] font-mono shadow-inner">
          {ticker.slice(0, 3)}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-white">{ticker}</p>
            <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono uppercase tracking-wider ${
              isWatchlist ? 'bg-purple-950/60 text-purple-300 border border-purple-500/30' : 'bg-cyan-950/60 text-[#38e1e7] border border-cyan-500/30'
            }`}>
              {isWatchlist ? 'Watchlist' : 'Holding'}
            </span>
          </div>
          <p className="text-xs text-gray-400 truncate max-w-[130px]">{name}</p>
        </div>
      </div>

      {/* Type / Category */}
      <div className="hidden md:block text-left min-w-[100px]">
        <p className="text-xs font-medium text-gray-300">{assetType}</p>
      </div>

      {/* Sparkline Graphic */}
      <div className="w-16 h-8 hidden sm:block">
        <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 64 32">
          <path
            d={isPositive ? positivePath : negativePath}
            stroke={isPositive ? '#38e1e7' : '#f43f5e'}
            strokeWidth="1.8"
            strokeLinecap="round"
            fill="none"
          />
        </svg>
      </div>

      {/* Market Value */}
      <div className="hidden lg:block text-right min-w-[110px]">
        <p className="text-xs text-gray-400">Market Value</p>
        <p className="text-sm font-mono text-white font-medium">${marketValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}</p>
      </div>

      {/* Price & Return */}
      <div className="text-right min-w-[100px]">
        <p className="text-sm font-mono font-semibold text-white">${price.toFixed(2)}</p>
        <p className={`text-xs font-mono font-medium ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
          {isPositive ? '+' : ''}{changePct.toFixed(2)}%
        </p>
      </div>
    </div>
  );
};

const Markets: React.FC = () => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('ALL');
  const [timeframe, setTimeframe] = useState<string>('1D');

  useEffect(() => {
    fetchAssets().then((data) => {
      setAssets(data || []);
      setLoading(false);
    });
  }, []);

  const indices = [
    { label: 'S&P 500', value: '5,123.41', change: '+0.8%', positive: true },
    { label: 'NASDAQ', value: '16,231.10', change: '+1.2%', positive: true },
    { label: 'VIX (Volatility)', value: '14.20', change: '-2.5%', positive: false },
  ];

  const filteredAssets = assets.filter((asset) => {
    const matchesSearch = asset.ticker.toLowerCase().includes(search.toLowerCase()) ||
                          asset.name.toLowerCase().includes(search.toLowerCase());
    const matchesType = selectedType === 'ALL' || asset.asset_type === selectedType;
    return matchesSearch && matchesType;
  });

  return (
    <div className="h-full overflow-y-auto p-4 md:p-8 space-y-6 custom-scrollbar">
      <div className="glass-panel relative z-10 w-full max-w-6xl mx-auto rounded-[32px] p-6 md:p-10 flex flex-col gap-6 overflow-hidden shadow-2xl">

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-medium tracking-tight text-white">Market & Asset Screener</h1>
            <p className="text-xs md:text-sm text-gray-400 mt-1">Monitoreo cuantitativo de posiciones y activos en seguimiento</p>
          </div>
          <span className="self-start md:self-auto flex items-center gap-2 text-xs text-emerald-400 font-medium px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse inline-block"></span>
            FastAPI Live Sync
          </span>
        </div>

        {/* Global Indices Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full">
          {indices.map((idx) => (
            <IndexCard key={idx.label} {...idx} />
          ))}
        </div>

        {/* Live Asset Tracker SVG Chart */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-white">Live Asset Tracker</p>
            <div className="flex gap-2">
              {['1H', '4H', '1D', '1W'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                    tf === timeframe
                      ? 'bg-[#38e1e7]/20 text-[#38e1e7] border border-[#38e1e7]/30'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4">
            <div className="w-full h-36">
              <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 800 160" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="mkCyanGrad" x1="0%" x2="100%" y1="0%" y2="0%">
                    <stop offset="0%" stopColor="#38e1e7" stopOpacity="0.3" />
                    <stop offset="50%" stopColor="#38e1e7" stopOpacity="1" />
                    <stop offset="100%" stopColor="#38e1e7" stopOpacity="0.7" />
                  </linearGradient>
                  <linearGradient id="mkFill" x1="0%" x2="0%" y1="0%" y2="100%">
                    <stop offset="0%" stopColor="#38e1e7" stopOpacity="0.15" />
                    <stop offset="100%" stopColor="#38e1e7" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path
                  d="M 0,120 C 80,100 140,110 200,90 C 260,70 320,80 380,60 C 440,40 500,70 560,50 C 620,30 680,55 740,40 L 800,35 L 800,160 L 0,160 Z"
                  fill="url(#mkFill)"
                />
                <path
                  className="glow-cyan-path"
                  d="M 0,120 C 80,100 140,110 200,90 C 260,70 320,80 380,60 C 440,40 500,70 560,50 C 620,30 680,55 740,40 L 800,35"
                  stroke="url(#mkCyanGrad)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                <circle cx="800" cy="35" r="4" fill="#38e1e7" />
                <circle cx="800" cy="35" r="8" fill="#38e1e7" fillOpacity="0.25" />
              </svg>
            </div>
          </div>
        </div>

        {/* Screener Controls & Filtering */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
          <p className="text-sm font-medium text-white self-start sm:self-auto">Screener Assets ({filteredAssets.length})</p>
          
          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
            <input
              type="text"
              placeholder="Filtrar por ticker o nombre..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-black/40 border border-white/10 rounded-xl px-4 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#38e1e7] transition-all w-full sm:w-60"
            />
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="bg-black/40 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-[#38e1e7] transition-all"
            >
              <option value="ALL">Todos los Tipos</option>
              <option value="ETF">ETFs</option>
              <option value="EQUITY">Acciones (Equity)</option>
              <option value="CASH">Liquidez (Cash)</option>
            </select>
          </div>
        </div>

        {/* Assets List */}
        <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-2 md:p-4">
          {loading ? (
            <div className="py-12 text-center text-xs text-gray-400 font-mono">
              Obteniendo activos desde la base de datos...
            </div>
          ) : filteredAssets.length === 0 ? (
            <div className="py-12 text-center text-xs text-gray-500">
              No se encontraron activos que coincidan con la búsqueda.
            </div>
          ) : (
            filteredAssets.map((asset) => (
              <AssetRow
                key={asset.ticker}
                ticker={asset.ticker}
                name={asset.name}
                price={asset.current_price}
                changePct={asset.unrealized_pnl_pct}
                marketValue={asset.market_value_usd}
                assetType={asset.asset_type}
                isWatchlist={asset.is_watchlist}
              />
            ))
          )}
        </div>

      </div>
    </div>
  );
};

export default Markets;