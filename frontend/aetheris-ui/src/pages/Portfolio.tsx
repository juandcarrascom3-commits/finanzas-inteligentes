import React from 'react';

interface HoldingRow {
  ticker: string;
  name: string;
  allocation: number;
  value: string;
  pnl: string;
  positive: boolean;
}

const HOLDINGS: HoldingRow[] = [
  { ticker: 'AAPL', name: 'Apple Inc.', allocation: 28, value: '$348,684', pnl: '+12.4%', positive: true },
  { ticker: 'MSFT', name: 'Microsoft Corp.', allocation: 22, value: '$273,966', pnl: '+8.7%', positive: true },
  { ticker: 'NVDA', name: 'NVIDIA Corp.', allocation: 18, value: '$224,154', pnl: '+31.2%', positive: true },
  { ticker: 'BTC', name: 'Bitcoin', allocation: 15, value: '$186,795', pnl: '+19.5%', positive: true },
  { ticker: 'TSLA', name: 'Tesla Inc.', allocation: 10, value: '$124,530', pnl: '-4.1%', positive: false },
  { ticker: 'CASH', name: 'Cash & Equivalents', allocation: 7, value: '$87,171', pnl: '+0.0%', positive: true },
];

const Portfolio: React.FC = () => {
  return (
    <div className="h-full overflow-y-auto p-6 md:p-8 space-y-6 custom-scrollbar">
      <div className="glass-panel relative z-10 w-full max-w-6xl mx-auto rounded-[32px] p-8 md:p-10 flex flex-col gap-8 overflow-hidden shadow-2xl">

        {/* Header row */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-medium tracking-tight text-white">Portfolio</h1>
            <p className="text-xs md:text-sm text-gray-400 mt-1">Current holdings and allocation breakdown</p>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-3xl font-light text-white tracking-tight">$1,245,300</span>
            <span className="text-sm font-medium text-[#38e1e7] mt-0.5">+$14,943 today (+1.2%)</span>
          </div>
        </div>

        {/* Allocation bar */}
        <div>
          <p className="text-xs text-gray-400 font-medium mb-2 uppercase tracking-wider">Allocation</p>
          <div className="flex h-3 rounded-full overflow-hidden gap-px">
            {HOLDINGS.map((h) => (
              <div
                key={h.ticker}
                style={{ width: `${h.allocation}%` }}
                className={`h-full ${
                  h.ticker === 'CASH' ? 'bg-gray-600' :
                  h.positive ? 'bg-[#38e1e7]' : 'bg-rose-500'
                }`}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
            {HOLDINGS.map((h) => (
              <span key={h.ticker} className="flex items-center gap-1.5 text-xs text-gray-400">
                <span className={`w-2 h-2 rounded-sm inline-block ${
                  h.ticker === 'CASH' ? 'bg-gray-600' :
                  h.positive ? 'bg-[#38e1e7]' : 'bg-rose-500'
                }`} />
                {h.ticker} {h.allocation}%
              </span>
            ))}
          </div>
        </div>

        {/* Holdings table */}
        <div>
          <p className="text-xs text-gray-400 font-medium mb-3 uppercase tracking-wider">Holdings</p>
          <div className="bg-white/[0.03] border border-white/5 rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Asset</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider hidden sm:table-cell">Allocation</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Value</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {HOLDINGS.map((h, idx) => (
                  <tr
                    key={h.ticker}
                    className={`${idx < HOLDINGS.length - 1 ? 'border-b border-white/[0.04]' : ''} hover:bg-white/[0.02] transition`}
                  >
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-[#171920] border border-white/10 flex items-center justify-center text-xs font-bold text-gray-300">
                          {h.ticker.slice(0, 2)}
                        </div>
                        <div>
                          <p className="font-semibold text-white">{h.ticker}</p>
                          <p className="text-xs text-gray-400">{h.name}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-right text-gray-300 hidden sm:table-cell">{h.allocation}%</td>
                    <td className="px-4 py-3.5 text-right font-medium text-white">{h.value}</td>
                    <td className={`px-4 py-3.5 text-right font-semibold ${h.positive ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {h.pnl}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Portfolio;

