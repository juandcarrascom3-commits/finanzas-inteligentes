import React from 'react';

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
          ? 'bg-teal-500/10 text-emerald-400'
          : 'bg-rose-400/10 text-rose-400',
      ].join(' ')}
    >
      {change}
    </span>
  </div>
);

interface AssetRowProps {
  ticker: string;
  name: string;
  price: string;
  change: string;
  positive: boolean;
  sparkPath: string;
  sparkColor: string;
}

const AssetRow: React.FC<AssetRowProps> = ({ ticker, name, price, change, positive, sparkPath, sparkColor }) => (
  <div className="flex items-center justify-between py-3 border-b border-white/[0.04] last:border-b-0">
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-white/[0.05] border border-white/10 flex items-center justify-center text-xs font-bold text-gray-300">
        {ticker.slice(0, 2)}
      </div>
      <div>
        <p className="text-sm font-semibold text-white">{ticker}</p>
        <p className="text-xs text-gray-400">{name}</p>
      </div>
    </div>
    <div className="w-16 h-8 hidden sm:block">
      <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 64 32">
        <path d={sparkPath} stroke={sparkColor} strokeWidth="1.5" strokeLinecap="round" fill="none" />
      </svg>
    </div>
    <div className="text-right">
      <p className="text-sm font-semibold text-white">{price}</p>
      <p className={`text-xs font-medium ${positive ? 'text-emerald-400' : 'text-rose-400'}`}>{change}</p>
    </div>
  </div>
);

const Markets: React.FC = () => {
  const indices = [
    { label: 'S&P 500', value: '5,123.41', change: '+0.8%', positive: true },
    { label: 'NASDAQ', value: '16,231.10', change: '+1.2%', positive: true },
    { label: 'VIX (Volatility)', value: '14.20', change: '-2.5%', positive: false },
  ];

  const trendingAssets: AssetRowProps[] = [
    {
      ticker: 'AAPL',
      name: 'Apple Inc.',
      price: '$189.30',
      change: '+2.14%',
      positive: true,
      sparkPath: 'M 2,24 C 10,20 16,14 24,12 C 32,10 40,16 48,10 C 54,6 58,8 62,6',
      sparkColor: '#38e1e7',
    },
    {
      ticker: 'MSFT',
      name: 'Microsoft Corp.',
      price: '$415.60',
      change: '+1.82%',
      positive: true,
      sparkPath: 'M 2,20 C 8,18 16,22 24,16 C 32,10 40,14 48,8 C 54,4 58,6 62,4',
      sparkColor: '#38e1e7',
    },
    {
      ticker: 'NVDA',
      name: 'NVIDIA Corp.',
      price: '$875.40',
      change: '+4.30%',
      positive: true,
      sparkPath: 'M 2,28 C 8,22 14,18 22,12 C 30,6 40,10 48,6 C 54,4 58,5 62,2',
      sparkColor: '#38e1e7',
    },
    {
      ticker: 'TSLA',
      name: 'Tesla Inc.',
      price: '$248.10',
      change: '-1.45%',
      positive: false,
      sparkPath: 'M 2,8 C 8,10 16,12 24,18 C 32,22 40,20 48,24 C 54,26 58,25 62,28',
      sparkColor: '#f43f5e',
    },
    {
      ticker: 'BTC',
      name: 'Bitcoin',
      price: '$67,420',
      change: '+3.21%',
      positive: true,
      sparkPath: 'M 2,22 C 6,18 12,20 20,14 C 28,8 36,12 44,6 C 52,2 58,4 62,2',
      sparkColor: '#38e1e7',
    },
  ];

  return (
    <div className="h-full overflow-y-auto p-6 md:p-8 space-y-6 custom-scrollbar">
      <div className="glass-panel relative z-10 w-full max-w-6xl mx-auto rounded-[32px] p-8 md:p-10 flex flex-col gap-6 overflow-hidden shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium tracking-tight text-white">Market Overview</h1>
            <p className="text-xs md:text-sm text-gray-400 mt-1">Live global indices and trending assets</p>
          </div>
          <span className="flex items-center gap-2 text-xs text-emerald-400 font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse inline-block"></span>
            Live
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
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                    tf === '1D'
                      ? 'bg-[#1d1f27] text-white'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4">
            <div className="w-full h-40">
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
                {/* Area fill */}
                <path
                  d="M 0,120 C 80,100 140,110 200,90 C 260,70 320,80 380,60 C 440,40 500,70 560,50 C 620,30 680,55 740,40 L 800,35 L 800,160 L 0,160 Z"
                  fill="url(#mkFill)"
                />
                {/* Line */}
                <path
                  className="glow-cyan-path"
                  d="M 0,120 C 80,100 140,110 200,90 C 260,70 320,80 380,60 C 440,40 500,70 560,50 C 620,30 680,55 740,40 L 800,35"
                  stroke="url(#mkCyanGrad)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                {/* Current price dot */}
                <circle cx="800" cy="35" r="4" fill="#38e1e7" />
                <circle cx="800" cy="35" r="8" fill="#38e1e7" fillOpacity="0.25" />
              </svg>
            </div>
          </div>
        </div>

        {/* Trending Assets */}
        <div>
          <p className="text-sm font-medium text-white mb-2">Trending Assets</p>
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl px-4">
            {trendingAssets.map((asset) => (
              <AssetRow key={asset.ticker} {...asset} />
            ))}
          </div>
        </div>

      </div>
    </div>
  );
};

export default Markets;

