import React, { useState } from 'react';
import { PieChart, TrendingUp, Layers, Globe, Shield, Sparkles, Filter } from 'lucide-react';
import { TreemapCategory, EvolutionPoint } from '../types';

interface CentralVisualSectionProps {
  treemapData: TreemapCategory[];
  evolutionData: EvolutionPoint[];
  currency: 'USD' | 'COP';
  exchangeRate: number;
}

export const CentralVisualSection: React.FC<CentralVisualSectionProps> = ({
  treemapData,
  evolutionData,
  currency,
  exchangeRate
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'treemap' | 'sectors'>('treemap');
  const [hoveredMonth, setHoveredMonth] = useState<EvolutionPoint | null>(null);

  const totalPortfolioValue = treemapData.reduce((acc, cat) => acc + cat.value, 0);

  const getCategoryColor = (name: string) => {
    switch (name) {
      case 'Renta Variable':
        return { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', badge: 'bg-emerald-500' };
      case 'Efectivo':
        return { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', badge: 'bg-blue-500' };
      case 'Alternativos':
        return { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', badge: 'bg-purple-500' };
      default:
        return { bg: 'bg-gray-800', border: 'border-gray-700', text: 'text-gray-300', badge: 'bg-gray-500' };
    }
  };

  const formatMoney = (usdVal: number) => {
    if (currency === 'USD') {
      return `$${usdVal.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} USD`;
    }
    return `$${(usdVal * exchangeRate).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} COP`;
  };

  // Evolution chart scaling
  const minVal = 95;
  const maxVal = 132;
  const getY = (val: number, height: number = 220) => {
    return height - ((val - minVal) / (maxVal - minVal)) * height;
  };

  const activePoint = hoveredMonth || (evolutionData.length > 0 ? evolutionData[evolutionData.length - 1] : null);

  return (
    <section className="grid grid-cols-1 lg:grid-cols-12 gap-5">
      {/* 1. ASSET ALLOCATION (Interactive Sunburst / Treemap Distribution) */}
      <div className="lg:col-span-6 bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
            <div className="flex items-center space-x-2.5">
              <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-400">
                <PieChart className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                  Distribución de Activos (Asset Allocation)
                </h2>
                <p className="text-[11px] text-gray-400">
                  Jerarquía por Tipo de Activo &bull; Sector &bull; Geografía
                </p>
              </div>
            </div>

            {/* View Mode Toggle */}
            <div className="flex bg-gray-900 p-0.5 rounded-lg border border-gray-800 text-[11px]">
              <button
                onClick={() => setActiveTab('treemap')}
                className={`px-2.5 py-1 rounded font-medium transition-all ${
                  activeTab === 'treemap' ? 'bg-gray-800 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Treemap
              </button>
              <button
                onClick={() => setActiveTab('sectors')}
                className={`px-2.5 py-1 rounded font-medium transition-all ${
                  activeTab === 'sectors' ? 'bg-gray-800 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Por Sectores
              </button>
            </div>
          </div>

          {/* Allocation Visual Blocks (Proportional Treemap Engine) */}
          <div className="space-y-3">
            {treemapData.map((cat) => {
              const style = getCategoryColor(cat.name);
              const isSelected = selectedCategory === cat.name;

              return (
                <div
                  key={cat.name}
                  onClick={() => setSelectedCategory(isSelected ? null : cat.name)}
                  className={`rounded-xl border p-3.5 transition-all cursor-pointer ${
                    isSelected ? 'ring-2 ring-emerald-400 border-transparent bg-gray-800/90' : `${style.bg} ${style.border} hover:bg-gray-800/50`
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className={`w-2.5 h-2.5 rounded-full ${style.badge}`} />
                      <span className="text-xs font-bold text-white">{cat.name}</span>
                      <span className="text-[10px] text-gray-400 font-mono">({cat.percentage}%)</span>
                    </div>
                    <div className="text-xs font-bold mono-number text-gray-200">
                      {formatMoney(cat.value)}
                    </div>
                  </div>

                  {/* Level 2: Children Sectors Progress Bar & Tickers */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 mt-2.5 pt-2 border-t border-gray-800/60">
                    {cat.children.map((sector) => (
                      <div key={sector.name} className="bg-gray-900/70 p-2 rounded-lg border border-gray-800/80">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-gray-300 font-medium truncate">{sector.name}</span>
                          <span className="text-gray-400 font-mono text-[10px]">{formatMoney(sector.value)}</span>
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {sector.items.map((item) => (
                            <span
                              key={item.ticker}
                              className="text-[9px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700 font-mono"
                              title={`${item.name} (${item.country}): ${item.allocation_pct}%`}
                            >
                              {item.ticker} ({item.allocation_pct}%)
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Legend / Status Footer */}
        <div className="mt-4 pt-3 border-t border-gray-800/80 flex flex-wrap items-center justify-between text-[11px] text-gray-400">
          <span className="flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5 text-blue-400" />
            Exposición: 78% EE.UU., 14% Colombia, 8% Global
          </span>
          <span className="text-emerald-400 font-mono font-semibold">
            Total Asignado: {formatMoney(totalPortfolioValue)}
          </span>
        </div>
      </div>

      {/* 2. TEMPORAL EVOLUTION (Net Worth Curve vs S&P 500 Benchmark) */}
      <div className="lg:col-span-6 bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
            <div className="flex items-center space-x-2.5">
              <div className="p-1.5 rounded-md bg-purple-500/10 text-purple-400">
                <TrendingUp className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                  Evolución Temporal vs. Benchmark
                </h2>
                <p className="text-[11px] text-gray-400">
                  Crecimiento del Portafolio vs. S&P 500 (Base 100) &bull; Últimos 12 Meses
                </p>
              </div>
            </div>

            {/* Active Alpha Badge */}
            {activePoint && (
              <div className="flex items-center space-x-1 px-2.5 py-1 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold">
                <Sparkles className="w-3 h-3" />
                <span>Alfa: +{activePoint.alpha_spread}%</span>
              </div>
            )}
          </div>

          {/* SVG Area Chart Container */}
          <div className="relative w-full h-56 bg-gray-950/60 rounded-xl border border-gray-800/80 p-3 flex flex-col justify-between">
            {/* Chart SVG */}
            <svg className="w-full h-40 overflow-visible" viewBox="0 0 500 160" preserveAspectRatio="none">
              <defs>
                <linearGradient id="portfolioGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10B981" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#10B981" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="benchmarkGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366F1" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="#6366F1" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Grid lines */}
              <line x1="0" y1="40" x2="500" y2="40" stroke="#1F2937" strokeDasharray="3 3" />
              <line x1="0" y1="80" x2="500" y2="80" stroke="#1F2937" strokeDasharray="3 3" />
              <line x1="0" y1="120" x2="500" y2="120" stroke="#1F2937" strokeDasharray="3 3" />

              {/* Benchmark Line (S&P 500) */}
              {evolutionData.length > 1 && (
                <>
                  <path
                    d={`M 0,${getY(evolutionData[0].benchmark_growth, 140)} ` +
                      evolutionData.map((pt, idx) => `L ${(idx / (evolutionData.length - 1)) * 500},${getY(pt.benchmark_growth, 140)}`).join(' ')}
                    fill="none"
                    stroke="#6366F1"
                    strokeWidth="2"
                    strokeDasharray="4 4"
                  />
                  {/* Portfolio Curve (Green Area) */}
                  <path
                    d={`M 0,${getY(evolutionData[0].portfolio_growth, 140)} ` +
                      evolutionData.map((pt, idx) => `L ${(idx / (evolutionData.length - 1)) * 500},${getY(pt.portfolio_growth, 140)}`).join(' ') +
                      ` L 500,160 L 0,160 Z`}
                    fill="url(#portfolioGrad)"
                  />
                  <path
                    d={`M 0,${getY(evolutionData[0].portfolio_growth, 140)} ` +
                      evolutionData.map((pt, idx) => `L ${(idx / (evolutionData.length - 1)) * 500},${getY(pt.portfolio_growth, 140)}`).join(' ')}
                    fill="none"
                    stroke="#10B981"
                    strokeWidth="3"
                  />
                </>
              )}

              {/* Interactive Points */}
              {evolutionData.map((pt, idx) => {
                const cx = (idx / (evolutionData.length - 1)) * 500;
                const cy = getY(pt.portfolio_growth, 140);
                const isHovered = hoveredMonth?.date === pt.date;

                return (
                  <circle
                    key={pt.date}
                    cx={cx}
                    cy={cy}
                    r={isHovered ? "6" : "3.5"}
                    className="cursor-pointer transition-all fill-emerald-400 stroke-gray-900 stroke-2 hover:fill-white"
                    onMouseEnter={() => setHoveredMonth(pt)}
                  />
                );
              })}
            </svg>

            {/* X-Axis Timeline Labels */}
            <div className="flex justify-between text-[10px] text-gray-500 font-mono mt-1 border-t border-gray-800/80 pt-1">
              {evolutionData.filter((_, idx) => idx % 2 === 0 || idx === evolutionData.length - 1).map((pt) => (
                <span key={pt.date}>{pt.date}</span>
              ))}
            </div>
          </div>

          {/* Interactive Inspection Card */}
          {activePoint && (
            <div className="mt-3.5 bg-gray-900/80 p-3 rounded-lg border border-gray-800 flex items-center justify-between text-xs">
              <div>
                <span className="text-gray-400 text-[10px] font-mono uppercase block">Mes: {activePoint.date}</span>
                <span className="font-bold text-white mono-number">
                  Valuación: {formatMoney(activePoint.portfolio_usd)}
                </span>
              </div>
              <div className="flex items-center space-x-4">
                <div className="text-right">
                  <span className="text-emerald-400 font-bold mono-number block">
                    Portafolio: +{(activePoint.portfolio_growth - 100).toFixed(1)}%
                  </span>
                  <span className="text-indigo-400 font-medium mono-number block text-[11px]">
                    S&P 500: +{(activePoint.benchmark_growth - 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Legend / Methodology */}
        <div className="mt-3 pt-2.5 border-t border-gray-800/80 flex items-center justify-between text-[11px] text-gray-400">
          <div className="flex items-center space-x-3">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-0.5 bg-emerald-500 rounded-full" /> Portafolio Inteligente
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-0.5 bg-indigo-500 border-dashed rounded-full" /> S&P 500 (SPY)
            </span>
          </div>
          <span className="text-gray-500 font-mono text-[10px]">Cálculo TWR normalizado</span>
        </div>
      </div>
    </section>
  );
};
