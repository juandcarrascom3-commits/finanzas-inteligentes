import React from 'react';
import { DollarSign, Activity, RefreshCw, Layers } from 'lucide-react';
import { DailyQuota } from '../types';

interface HeaderProps {
  currency: 'USD' | 'COP';
  setCurrency: (c: 'USD' | 'COP') => void;
  exchangeRate: number;
  quota?: DailyQuota;
  onRefresh: () => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currency,
  setCurrency,
  exchangeRate,
  quota,
  onRefresh,
  isLoading
}) => {
  return (
    <header className="border-b border-gray-800 bg-[#0E1526]/80 backdrop-blur sticky top-0 z-40 px-4 lg:px-8 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand & Strategy Vision */}
        <div className="flex items-center space-x-3 w-full md:w-auto justify-between md:justify-start">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                Finanzas Inteligentes
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  3-Tier Layout
                </span>
              </h1>
              <p className="text-xs text-gray-400 hidden sm:block">
                Estrategia, Crecimiento, Gestión Inteligente y Control de Riesgo
              </p>
            </div>
          </div>

          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-emerald-400' : ''}`} />
            </button>
          </div>
        </div>

        {/* Action Controls: Currency Switcher, API Quota Indicator, Refresh */}
        <div className="flex flex-wrap items-center justify-end gap-2.5 w-full md:w-auto">
          {/* Parity Info */}
          <div className="hidden lg:flex items-center text-xs text-gray-400 bg-gray-900/60 px-2.5 py-1.5 rounded-md border border-gray-800 font-mono">
            <span className="text-gray-500 mr-1.5">Tasa:</span>
            <span>1 USD = {exchangeRate.toLocaleString()} COP</span>
          </div>

          {/* Daily API Quota Indicator */}
          {quota && (
            <div className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium ${
              quota.is_quota_exhausted
                ? 'bg-red-500/10 text-red-400 border-red-500/30'
                : quota.used_requests > 20
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                : 'bg-gray-800/80 text-gray-300 border-gray-700'
            }`}>
              <Activity className="w-3.5 h-3.5" />
              <span>API Ingestión:</span>
              <span className="font-mono font-bold text-white">
                {quota.used_requests}/{quota.max_quota}
              </span>
              <span className="text-[10px] text-gray-400">/día</span>
            </div>
          )}

          {/* Currency Toggle */}
          <div className="flex items-center bg-gray-900 p-0.5 rounded-lg border border-gray-800">
            <button
              onClick={() => setCurrency('USD')}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                currency === 'USD'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              USD ($)
            </button>
            <button
              onClick={() => setCurrency('COP')}
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                currency === 'COP'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              COP ($)
            </button>
          </div>

          {/* Refresh Action */}
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="hidden md:flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-medium transition-colors border border-gray-700"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-emerald-400' : ''}`} />
            <span>Actualizar</span>
          </button>
        </div>
      </div>
    </header>
  );
};
