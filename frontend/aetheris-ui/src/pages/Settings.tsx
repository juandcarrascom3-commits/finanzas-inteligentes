import React from 'react';

const Settings: React.FC = () => {
  return (
    <div className="h-full overflow-y-auto p-6 md:p-8 space-y-6 custom-scrollbar">
      <div className="glass-panel relative z-10 w-full max-w-6xl mx-auto rounded-[32px] p-8 md:p-10 flex flex-col overflow-hidden shadow-2xl">
        <div className="flex flex-col md:flex-row gap-8 lg:gap-10 w-full">

          {/* Left Column: API Integrations */}
          <div className="w-full md:w-[60%] flex flex-col justify-between space-y-6">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-medium tracking-tight text-white">API Integrations</h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-teal-950/40 text-[#38e1e7] border border-teal-500/30">
                  Production
                </span>
              </div>
              <p className="text-xs md:text-sm font-normal text-gray-400 mt-1">
                Active market data sources and broker connections
              </p>
            </div>

            <div className="space-y-3.5">
              {/* Alpaca API */}
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-[#171920] border border-white/10 flex items-center justify-center text-[#38e1e7] font-bold">
                    &#9889;
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white">Alpaca API</h4>
                    <p className="text-xs text-gray-400 mt-0.5">Trading &amp; Real-time Market Feeds</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs font-medium text-emerald-400">&#11044; Connected</span>
                  <button className="px-3 py-1.5 rounded-lg border border-white/10 text-xs font-medium text-gray-300 hover:text-white hover:bg-white/5 transition">
                    Sync Now
                  </button>
                </div>
              </div>

              {/* FMP API */}
              <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-[#171920] border border-white/10 flex items-center justify-center text-gray-300 font-bold">
                    &#128202;
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-white">Financial Modeling Prep</h4>
                    <p className="text-xs text-gray-400 mt-0.5">Fundamental &amp; Financial Statements API</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs font-medium text-emerald-400">&#11044; Connected</span>
                  <button className="px-3 py-1.5 rounded-lg border border-white/10 text-xs font-medium text-gray-300 hover:text-white hover:bg-white/5 transition">
                    Sync Now
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Risk Guardrails */}
          <div className="w-full md:w-[40%] flex flex-col justify-between border-t md:border-t-0 md:border-l border-white/10 pt-6 md:pt-0 md:pl-8 lg:pl-10 space-y-6">
            <div>
              <h2 className="text-2xl font-medium tracking-tight text-white">Risk Guardrails</h2>
              <p className="text-xs md:text-sm font-normal text-gray-400 mt-1">
                Automated protection rules and limits
              </p>

              <div className="space-y-4 mt-6">
                {/* Anomalous transactions toggle */}
                <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-white">Block anomalous transactions</p>
                    <p className="text-xs text-gray-400 mt-0.5">Automatically halt orders with deviation &gt; 3&#963;</p>
                  </div>
                  {/* Toggle: ON state */}
                  <div className="w-11 h-6 bg-[#38e1e7] rounded-full relative flex items-center justify-end px-0.5 cursor-pointer flex-shrink-0">
                    <div className="w-5 h-5 bg-[#0c0d12] rounded-full"></div>
                  </div>
                </div>

                {/* Max daily loss limit */}
                <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-4">
                  <label className="block text-sm font-medium text-white mb-2">
                    Max daily loss limit (%)
                  </label>
                  <input
                    className="w-full bg-[#171920] border border-white/10 text-white text-sm rounded-xl px-4 py-2.5 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30 transition"
                    type="text"
                    defaultValue="5.0"
                  />
                </div>
              </div>
            </div>

            <button className="w-full bg-teal-500/20 text-[#38e1e7] border border-teal-500/50 hover:bg-teal-500/30 rounded-xl px-5 py-3 font-medium transition">
              Save Preferences
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};

export default Settings;

