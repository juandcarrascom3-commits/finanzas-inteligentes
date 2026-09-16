import DashboardRightPanel from '../components/DashboardRightPanel';
import React, { useEffect, useRef } from 'react';

const Dashboard: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width: number;
    let height: number;
    let animationFrame: number;

    function resize(): void {
      if (!canvas) return;
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    }

    window.addEventListener('resize', resize);
    resize();

    // Dot matrix parameters
    const cols = 75;
    const rows = 35;
    let phase = 0;

    function draw(): void {
      if (!ctx) return;
      ctx.clearRect(0, 0, width, height);

      const startX = width * 0.05;
      const endX = width * 0.98;
      const startY = height * 0.25;
      const gridWidth = endX - startX;
      const gridHeight = height * 0.55;

      for (let r = 0; r < rows; r++) {
        const rowNorm = r / rows;

        for (let c = 0; c < cols; c++) {
          const colNorm = c / cols;

          // Generate undulating multi-frequency sine wave landscape
          const wave1 = Math.sin(colNorm * 7 + phase + rowNorm * 3);
          const wave2 = Math.cos(colNorm * 4 - phase * 0.7 + rowNorm * 2);
          const elevation = wave1 * 38 + wave2 * 28 + rowNorm * 70;

          const x = startX + colNorm * gridWidth;
          const y = startY + rowNorm * gridHeight + elevation;

          const isMagenta = colNorm > 0.52;
          const centerFactor = Math.sin(colNorm * Math.PI);

          ctx.beginPath();
          const radius = 1.0 + centerFactor * 1.1 + rowNorm * 0.6;
          ctx.arc(x, y, radius, 0, Math.PI * 2);

          if (isMagenta) {
            const alpha = 0.2 + colNorm * 0.45 * centerFactor;
            ctx.fillStyle = `rgba(200, 80, 192, ${Math.min(alpha, 0.75)})`;
          } else {
            const alpha = 0.25 + (1 - colNorm) * 0.45 * centerFactor;
            ctx.fillStyle = `rgba(56, 225, 231, ${Math.min(alpha, 0.85)})`;
          }
          ctx.fill();
        }
      }

      phase += 0.008;
      animationFrame = requestAnimationFrame(draw);
    }

    draw();

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', resize);
    };
  }, []);

  const metricClass = "transition-all duration-300 hover:border-white/20 hover:bg-white/[0.04] border border-transparent rounded-2xl p-3 -m-3";

return (
    <div className="relative overflow-y-auto flex flex-col justify-start h-full p-4 md:p-8" data-purpose="dashboard-content">
      {/* Fondo de Canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none z-0 opacity-85" />

      {/* Contenedor principal de 2 columnas */}
      <div className="relative z-10 w-full max-w-[1600px] mx-auto flex flex-col xl:flex-row gap-6 items-start">
        
        {/* COLUMNA IZQUIERDA: Tu panel actual del Dashboard intacto */}
        <div className="flex-1 w-full min-w-0 glass-panel rounded-[32px] p-8 md:p-10 flex flex-col justify-between shadow-2xl transition-all duration-300 hover:border-white/20 hover:bg-white/[0.04]">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 items-start">
            <div className={metricClass}>
              <p className="text-xs md:text-sm font-normal text-gray-400 mb-1">Total Asset Value</p>
              <h2 className="text-3xl lg:text-4xl font-light tracking-tight text-white">$1,245,300</h2>
            </div>
            <div className={metricClass}>
              <p className="text-xs md:text-sm font-normal text-gray-400 mb-1">Daily Change</p>
              <span className="text-2xl lg:text-3xl font-medium tracking-tight text-[#38e1e7]">+1.2%</span>
            </div>
            <div className={metricClass}>
              <p className="text-xs md:text-sm font-normal text-gray-400 mb-2">Spliner Chart</p>
              <div className="w-24 h-9">
                <svg className="w-full h-full overflow-visible" fill="none" viewBox="0 0 96 36">
                  <path className="glow-cyan-path" d="M 2,12 C 14,2 24,28 40,24 C 52,20 62,32 76,28 C 84,24 88,14 94,10" stroke="#38e1e7" strokeLinecap="round" strokeWidth="2.5" />
                </svg>
              </div>
            </div>
            <div className={metricClass}>
              <p className="text-xs md:text-sm font-normal text-gray-400 mb-2">Market Sentiment</p>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-teal-950/40 border border-teal-500/30 text-[#38e1e7] shadow-inner">
                <svg className="w-4 h-4 text-[#38e1e7]" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <path d="m4.5 19.5 15-15m0 0H8.25m11.25 0v11.25" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span className="text-xs font-semibold uppercase tracking-wider">Bullish</span>
                <span className="text-xs opacity-70 ml-0.5">&#128070;</span>
              </div>
            </div>
          </div>

          <div className="relative w-full h-64 md:h-80 my-4 flex items-center justify-center">
            <svg className="w-full h-full overflow-visible" fill="none" preserveAspectRatio="none" viewBox="0 0 1000 320">
              <defs>
                <linearGradient id="cyanGradient" x1="0%" x2="100%" y1="0%" y2="0%">
                  <stop offset="0%" stopColor="#38e1e7" stopOpacity="0.3" />
                  <stop offset="30%" stopColor="#38e1e7" stopOpacity="0.9" />
                  <stop offset="70%" stopColor="#38e1e7" stopOpacity="1" />
                  <stop offset="100%" stopColor="#38e1e7" stopOpacity="0.8" />
                </linearGradient>
                <linearGradient id="magentaGradient" x1="0%" x2="100%" y1="0%" y2="0%">
                  <stop offset="0%" stopColor="#c850c0" stopOpacity="0.2" />
                  <stop offset="40%" stopColor="#c850c0" stopOpacity="0.85" />
                  <stop offset="80%" stopColor="#db2777" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.75" />
                </linearGradient>
              </defs>
              <path className="glow-magenta-path opacity-90" d="M 0,260 C 140,220 180,210 240,210 C 300,210 320,185 360,195 C 420,210 480,225 540,165 C 600,110 660,190 740,180 C 800,170 850,140 920,150 L 1000,120" fill="none" stroke="url(#magentaGradient)" strokeLinecap="round" strokeWidth="2.5" />
              <path className="glow-cyan-path" d="M 0,250 C 120,170 200,220 280,220 C 350,220 400,160 480,180 C 550,200 620,130 680,135 C 760,140 820,190 890,170 L 1000,110" fill="none" stroke="url(#cyanGradient)" strokeLinecap="round" strokeWidth="3" />
            </svg>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4 border-t border-white/[0.04]">
            <div className={metricClass}>
              <p className="text-xs md:text-sm font-normal text-gray-400 mb-1">Total Asset Value:</p>
              <p className="text-2xl md:text-4xl font-light text-white tracking-tight">$1,245,300</p>
            </div>
            <div className={metricClass}>
              <p className="text-xs md:text-sm font-normal text-gray-400 mb-1">Daily Change:</p>
              <p className="text-2xl md:text-4xl font-light text-[#38e1e7] tracking-tight">+1.2%</p>
            </div>
            <div className={metricClass}>
              <p className="text-xs md:text-sm font-normal text-gray-400 mb-1">Market Sentiment:</p>
              <p className="text-2xl md:text-4xl font-normal text-white tracking-tight">Bullish</p>
            </div>
          </div>
        </div>

        {/* COLUMNA DERECHA: El panel lateral HUD con el mapa y métricas */}
        <div className="w-full xl:w-80 shrink-0">
          <DashboardRightPanel />
        </div>

      </div>
    </div>
  );
};

export default Dashboard;