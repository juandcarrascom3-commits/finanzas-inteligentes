import React, { useEffect, useState } from 'react';

const DashboardRightPanel: React.FC = () => {
  const [metrics, setMetrics] = useState({
    inputLayer: 87.4,
    feedStability: 99.1,
    lossRate: 0.042,
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics((prev) => ({
        inputLayer: Math.min(100, Math.max(0, prev.inputLayer + (Math.random() * 2 - 1))),
        feedStability: Math.min(100, Math.max(90, prev.feedStability + (Math.random() * 0.5 - 0.25))),
        lossRate: Math.max(0, prev.lossRate + (Math.random() * 0.01 - 0.005)),
      }));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="glass-panel w-full lg:w-80 h-full flex flex-col gap-8 p-6 text-gray-200 font-mono text-sm relative overflow-hidden rounded-[32px] shadow-2xl transition-all duration-300 hover:border-white/20 hover:bg-white/[0.04]">
      {/* HUD Scanner overlay effect */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(56,225,231,0.03)_1px,transparent_1px)] bg-[size:100%_4px] pointer-events-none opacity-50 mix-blend-overlay"></div>

      {/* 1. Global Market Nodes */}
      <section className="relative z-10 flex flex-col gap-4">
        <div className="flex justify-between items-center border-b border-[#38e1e7]/30 pb-1">
          <h2 className="text-[#38e1e7] font-semibold tracking-[0.2em] text-[10px]">GLOBAL MARKET NODES</h2>
          <div className="h-1.5 w-1.5 bg-[#c850c0] rounded-full animate-pulse shadow-[0_0_5px_#c850c0]"></div>
        </div>
        
        <div className="relative w-full aspect-video bg-[#0a0a10]/50 border border-[#38e1e7]/20 rounded-xl overflow-hidden flex items-center justify-center p-2">
          {/* Minimalist World Map representation (Dots/Nodes) */}
          <svg viewBox="0 0 200 100" className="w-full h-full opacity-30">
            {/* North America */}
            <circle cx="40" cy="30" r="1.5" fill="#38e1e7" />
            <circle cx="30" cy="40" r="1" fill="#38e1e7" />
            <circle cx="50" cy="40" r="1" fill="#38e1e7" />
            {/* South America */}
            <circle cx="60" cy="70" r="1.5" fill="#38e1e7" />
            <circle cx="65" cy="80" r="1" fill="#38e1e7" />
            {/* Europe */}
            <circle cx="100" cy="25" r="1.5" fill="#38e1e7" />
            <circle cx="110" cy="30" r="1" fill="#38e1e7" />
            {/* Africa */}
            <circle cx="105" cy="55" r="1.5" fill="#38e1e7" />
            <circle cx="110" cy="65" r="1" fill="#38e1e7" />
            {/* Asia */}
            <circle cx="150" cy="35" r="1.5" fill="#38e1e7" />
            <circle cx="160" cy="45" r="1.5" fill="#38e1e7" />
            <circle cx="140" cy="25" r="1" fill="#38e1e7" />
            {/* Australia */}
            <circle cx="170" cy="80" r="1.5" fill="#38e1e7" />
            
            {/* Network lines */}
            <path d="M40,30 L100,25 L150,35 L170,80" stroke="#38e1e7" strokeWidth="0.2" fill="none" />
            <path d="M40,30 L60,70 L105,55 L160,45" stroke="#c850c0" strokeWidth="0.2" fill="none" />
          </svg>
          
          {/* Animated Active Nodes */}
          {/* NY */}
          <div className="absolute top-[30%] left-[20%] w-1.5 h-1.5 bg-[#38e1e7] rounded-full shadow-[0_0_8px_#38e1e7]">
            <div className="absolute inset-0 bg-[#38e1e7] rounded-full animate-ping opacity-75"></div>
          </div>
          {/* London */}
          <div className="absolute top-[25%] left-[50%] w-1.5 h-1.5 bg-[#c850c0] rounded-full shadow-[0_0_8px_#c850c0]">
            <div className="absolute inset-0 bg-[#c850c0] rounded-full animate-ping opacity-75" style={{ animationDelay: '0.5s' }}></div>
          </div>
          {/* Tokyo */}
          <div className="absolute top-[35%] left-[75%] w-1 h-1 bg-[#38e1e7] rounded-full shadow-[0_0_8px_#38e1e7]">
            <div className="absolute inset-0 bg-[#38e1e7] rounded-full animate-ping opacity-75" style={{ animationDelay: '1s' }}></div>
          </div>
          {/* Singapore */}
          <div className="absolute top-[55%] left-[80%] w-1.5 h-1.5 bg-[#c850c0] rounded-full shadow-[0_0_8px_#c850c0]">
            <div className="absolute inset-0 bg-[#c850c0] rounded-full animate-ping opacity-75" style={{ animationDelay: '0.2s' }}></div>
          </div>
        </div>
      </section>

      {/* 2. System Health */}
      <section className="relative z-10 flex flex-col gap-4">
        <div className="flex justify-between items-center border-b border-[#c850c0]/30 pb-1">
          <h2 className="text-[#c850c0] font-semibold tracking-[0.2em] text-[10px]">SYSTEM HEALTH</h2>
        </div>
        
        {/* Compact Vertical Bar Chart */}
        <div className="flex items-end justify-between h-12 w-full gap-[2px]">
          {[35, 60, 45, 80, 50, 75, 95, 65, 40, 85, 55, 70, 45, 90].map((val, idx) => (
            <div key={idx} className="w-full bg-[#111] rounded-t-sm relative group overflow-hidden">
              <div 
                className={`absolute bottom-0 w-full rounded-t-sm transition-all duration-500 ease-in-out ${idx % 4 === 0 ? 'bg-[#c850c0]' : 'bg-[#38e1e7]'}`}
                style={{ height: `${val}%` }}
              ></div>
            </div>
          ))}
        </div>

        {/* Horizontal Status Bars */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-[9px] tracking-wider">
              <span className="text-gray-400">LATENCY</span>
              <span className="text-[#38e1e7]">14 ms</span>
            </div>
            <div className="h-1 w-full bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-[#38e1e7] w-[18%] shadow-[0_0_8px_#38e1e7]"></div>
            </div>
          </div>
          
          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-[9px] tracking-wider">
              <span className="text-gray-400">THROUGHPUT</span>
              <span className="text-[#c850c0]">94.2 TB/s</span>
            </div>
            <div className="h-1 w-full bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-[#c850c0] w-[88%] shadow-[0_0_8px_#c850c0]"></div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Data Feeds */}
      <section className="relative z-10 flex flex-col gap-4">
        <div className="flex justify-between items-center border-b border-[#38e1e7]/30 pb-1">
          <h2 className="text-[#38e1e7] font-semibold tracking-[0.2em] text-[10px]">DATA FEEDS</h2>
          <span className="text-[9px] text-[#38e1e7]/60 border border-[#38e1e7]/30 px-1 rounded-sm animate-pulse">LIVE</span>
        </div>
        
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center bg-[#0a0a10]/80 p-2 border border-white/[0.04] rounded-xl">
            <span className="text-[10px] text-gray-500 tracking-wider">INPUT_LAYER_01</span>
            <span className="text-[#38e1e7] text-xs font-bold drop-shadow-[0_0_4px_#38e1e7]">
              {metrics.inputLayer.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between items-center bg-[#0a0a10]/80 p-2 border border-white/[0.04] rounded-xl">
            <span className="text-[10px] text-gray-500 tracking-wider">FEED_STABILITY</span>
            <span className="text-[#c850c0] text-xs font-bold drop-shadow-[0_0_4px_#c850c0]">
              {metrics.feedStability.toFixed(1)}%
            </span>
          </div>
          <div className="flex justify-between items-center bg-[#0a0a10]/80 p-2 border border-white/[0.04] rounded-xl">
            <span className="text-[10px] text-gray-500 tracking-wider">LOSS_RATE</span>
            <span className="text-[#38e1e7] text-xs font-bold drop-shadow-[0_0_4px_#38e1e7]">
              {metrics.lossRate.toFixed(4)}
            </span>
          </div>
          <div className="flex justify-between items-center bg-[#0a0a10]/80 p-2 border border-white/[0.04] rounded-xl">
            <span className="text-[10px] text-gray-500 tracking-wider">ROUTING_NODE</span>
            <span className="text-gray-300 text-xs font-bold">
              SECURE
            </span>
          </div>
        </div>
      </section>
    </aside>
  );
};

export default DashboardRightPanel;