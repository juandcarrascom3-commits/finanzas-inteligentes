import React from 'react';

interface StatCardProps {
  label: string;
  value: string;
  sub: string;
  positive: boolean;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sub, positive }) => (
  <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5 flex flex-col gap-2">
    <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</p>
    <p className="text-2xl font-light text-white tracking-tight">{value}</p>
    <p className={`text-xs font-semibold ${positive ? 'text-emerald-400' : 'text-rose-400'}`}>{sub}</p>
  </div>
);

const Analytics: React.FC = () => {
  const stats: StatCardProps[] = [
    { label: 'Sharpe Ratio', value: '2.14', sub: '↑ vs 1.87 last month', positive: true },
    { label: 'Max Drawdown', value: '-8.3%', sub: '↓ improved from -11.2%', positive: true },
    { label: 'Win Rate', value: '68.4%', sub: '↑ 342 / 500 trades', positive: true },
    { label: 'Avg. Return/Trade', value: '+0.87%', sub: '↓ slight decrease vs +0.91%', positive: false },
    { label: 'Portfolio Beta', value: '0.92', sub: 'Low market correlation', positive: true },
    { label: 'Alpha (annualized)', value: '+6.2%', sub: '↑ vs benchmark S&P 500', positive: true },
  ];

  return (
    <div className="h-full overflow-y-auto p-6 md:p-8 space-y-6 custom-scrollbar">
      <div className="glass-panel relative z-10 w-full max-w-6xl mx-auto rounded-[32px] p-8 md:p-10 flex flex-col gap-8 overflow-hidden shadow-2xl">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-white">Analytics</h1>
          <p className="text-xs md:text-sm text-gray-400 mt-1">Performance metrics and risk analytics</p>
        </div>

        {/* KPI Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {stats.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </div>

        {/* Equity Curve */}
        <div>
          <p className="text-sm font-medium text-white mb-3">Equity Curve — YTD</p>
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4">
            <div className="w-full h-48">
              <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 800 192" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="eqFill" x1="0%" x2="0%" y1="0%" y2="100%">
                    <stop offset="0%" stopColor="#38e1e7" stopOpacity="0.18" />
                    <stop offset="100%" stopColor="#38e1e7" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="eqLine" x1="0%" x2="100%" y1="0%" y2="0%">
                    <stop offset="0%" stopColor="#38e1e7" stopOpacity="0.4" />
                    <stop offset="60%" stopColor="#38e1e7" stopOpacity="1" />
                    <stop offset="100%" stopColor="#c850c0" stopOpacity="0.9" />
                  </linearGradient>
                </defs>
                {/* Y-axis guide lines */}
                {[0.25, 0.5, 0.75].map((y) => (
                  <line
                    key={y}
                    x1="0" y1={192 * y}
                    x2="800" y2={192 * y}
                    stroke="rgba(255,255,255,0.04)"
                    strokeWidth="1"
                  />
                ))}
                {/* Area */}
                <path
                  d="M 0,160 C 60,145 120,150 180,130 C 240,110 280,120 340,95 C 400,70 460,85 520,60 C 580,35 640,55 700,30 L 800,20 L 800,192 L 0,192 Z"
                  fill="url(#eqFill)"
                />
                {/* Line */}
                <path
                  className="glow-cyan-path"
                  d="M 0,160 C 60,145 120,150 180,130 C 240,110 280,120 340,95 C 400,70 460,85 520,60 C 580,35 640,55 700,30 L 800,20"
                  stroke="url(#eqLine)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                {/* End dot */}
                <circle cx="800" cy="20" r="4" fill="#c850c0" />
                <circle cx="800" cy="20" r="8" fill="#c850c0" fillOpacity="0.25" />
              </svg>
            </div>
            <div className="flex justify-between mt-2 px-1">
              {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'].map((m) => (
                <span key={m} className="text-xs text-gray-500">{m}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Monthly returns heatmap-style row */}
        <div>
          <p className="text-sm font-medium text-white mb-3">Monthly Returns</p>
          <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-9 gap-2">
            {[
              { m: 'Jan', r: '+3.2%', pos: true }, { m: 'Feb', r: '+1.8%', pos: true },
              { m: 'Mar', r: '-0.9%', pos: false }, { m: 'Apr', r: '+4.1%', pos: true },
              { m: 'May', r: '+2.7%', pos: true }, { m: 'Jun', r: '-1.2%', pos: false },
              { m: 'Jul', r: '+5.3%', pos: true }, { m: 'Aug', r: '+0.6%', pos: true },
              { m: 'Sep', r: '+1.2%', pos: true },
            ].map(({ m, r, pos }) => (
              <div
                key={m}
                className={`rounded-xl p-2.5 text-center border ${
                  pos
                    ? 'bg-teal-500/10 border-teal-500/20 text-emerald-400'
                    : 'bg-rose-400/10 border-rose-400/20 text-rose-400'
                }`}
              >
                <p className="text-xs text-gray-400">{m}</p>
                <p className="text-xs font-semibold mt-0.5">{r}</p>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
};

export default Analytics;

