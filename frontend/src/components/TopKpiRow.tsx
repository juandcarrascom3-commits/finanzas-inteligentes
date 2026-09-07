import React from 'react';
import { DollarSign, PiggyBank, TrendingUp, ShieldAlert, ArrowUpRight, ArrowDownRight, Info } from 'lucide-react';
import { NetWorthData, SavingsRateData, RiskMetrics } from '../types';

interface TopKpiRowProps {
  netWorth: NetWorthData;
  savingsRate: SavingsRateData;
  twrPct: number;
  mwrPct: number;
  riskMetrics: RiskMetrics;
  currency: 'USD' | 'COP';
}

export const TopKpiRow: React.FC<TopKpiRowProps> = ({
  netWorth,
  savingsRate,
  twrPct,
  mwrPct,
  riskMetrics,
  currency
}) => {
  const formatMoney = (usdVal: number, copVal: number) => {
    if (currency === 'USD') {
      return `$${usdVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
    } else {
      return `$${copVal.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} COP`;
    }
  };

  const formatUsdOnly = (usdVal: number) => {
    return `$${usdVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Patrimonio Neto Total */}
      <div className="bg-[#111827] border border-gray-800 hover:border-emerald-500/40 rounded-xl p-4.5 shadow-lg relative overflow-hidden group transition-all">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            Patrimonio Neto Total
          </span>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 flex items-center gap-0.5 border border-emerald-500/20">
            <ArrowUpRight className="w-3 h-3" /> +14.2% YTD
          </span>
        </div>
        <div className="text-2xl font-extrabold text-white tracking-tight mono-number mt-1">
          {formatMoney(netWorth.net_worth_usd, netWorth.net_worth_cop)}
        </div>
        <div className="mt-2 text-xs text-gray-400 flex items-center justify-between border-t border-gray-800/80 pt-2 font-mono">
          <span>{currency === 'USD' ? `Equivalente: $${netWorth.net_worth_cop.toLocaleString()} COP` : `Equivalente: $${netWorth.net_worth_usd.toLocaleString()} USD`}</span>
          <span className="text-emerald-400 font-medium">Líquido: ~14.3%</span>
        </div>
      </div>

      {/* 2. Tasa de Ahorro Mensual */}
      <div className="bg-[#111827] border border-gray-800 hover:border-blue-500/40 rounded-xl p-4.5 shadow-lg relative overflow-hidden group transition-all">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
            <PiggyBank className="w-3.5 h-3.5 text-blue-400" />
            Tasa de Ahorro Mensual
          </span>
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${
            savingsRate.status === 'OPTIMAL'
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : savingsRate.status === 'MODERATE'
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
              : 'bg-red-500/10 text-red-400 border-red-500/20'
          }`}>
            {savingsRate.status === 'OPTIMAL' ? '🟢 Óptima' : savingsRate.status === 'MODERATE' ? '🟠 Moderada' : '🔴 Déficit'}
          </span>
        </div>
        <div className="flex items-baseline space-x-2 mt-1">
          <span className="text-2xl font-extrabold text-white mono-number">
            {savingsRate.savings_rate_pct}%
          </span>
          <span className="text-xs text-gray-400">
            (Meta: 30%)
          </span>
        </div>
        {/* Progress bar */}
        <div className="mt-3">
          <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-1.5 rounded-full transition-all duration-500 ${
                savingsRate.savings_rate_pct >= 30 ? 'bg-emerald-500' : savingsRate.savings_rate_pct >= 15 ? 'bg-amber-500' : 'bg-red-500'
              }`}
              style={{ width: `${Math.min(100, Math.max(5, savingsRate.savings_rate_pct))}%` }}
            />
          </div>
          <div className="flex justify-between text-[11px] text-gray-400 font-mono mt-1.5">
            <span>Ahorro neto: +${savingsRate.net_savings.toLocaleString()} USD/mes</span>
          </div>
        </div>
      </div>

      {/* 3. Retorno Ponderado (TWR & MWR) */}
      <div className="bg-[#111827] border border-gray-800 hover:border-purple-500/40 rounded-xl p-4.5 shadow-lg relative overflow-hidden group transition-all">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
            Rendimiento (TWR / MWR)
          </span>
          <span className="text-[10px] text-purple-300 font-medium px-1.5 py-0.5 rounded bg-purple-500/10 border border-purple-500/20">
            Anualizado
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 mt-1">
          <div className="bg-gray-900/60 p-2 rounded-lg border border-gray-800/60">
            <div className="text-[10px] uppercase font-semibold text-gray-400">TWR (Tiempo)</div>
            <div className="text-lg font-bold text-emerald-400 mono-number mt-0.5">
              +{twrPct}%
            </div>
            <div className="text-[10px] text-gray-500">Sin sesgo de flujos</div>
          </div>
          <div className="bg-gray-900/60 p-2 rounded-lg border border-gray-800/60">
            <div className="text-[10px] uppercase font-semibold text-gray-400">MWR / TIR (Dinero)</div>
            <div className="text-lg font-bold text-purple-400 mono-number mt-0.5">
              +{mwrPct}%
            </div>
            <div className="text-[10px] text-gray-500">Pondera aportes DCA</div>
          </div>
        </div>
      </div>

      {/* 4. Métricas de Riesgo de Portafolio */}
      <div className="bg-[#111827] border border-gray-800 hover:border-amber-500/40 rounded-xl p-4.5 shadow-lg relative overflow-hidden group transition-all">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            Métricas de Riesgo
          </span>
          <span className="text-[11px] text-gray-400 font-mono">Vs. S&P 500</span>
        </div>
        <div className="grid grid-cols-3 gap-2 mt-1.5 text-center">
          <div className="bg-gray-900/60 p-2 rounded-lg border border-gray-800/60">
            <div className="text-[10px] uppercase font-semibold text-gray-400">Beta (&beta;)</div>
            <div className="text-base font-bold text-white mono-number mt-0.5">
              {riskMetrics.beta}
            </div>
            <div className="text-[9px] text-emerald-400 font-medium">Bajo Riesgo</div>
          </div>
          <div className="bg-gray-900/60 p-2 rounded-lg border border-gray-800/60">
            <div className="text-[10px] uppercase font-semibold text-gray-400">Sharpe</div>
            <div className="text-base font-bold text-white mono-number mt-0.5">
              {riskMetrics.sharpe_ratio}
            </div>
            <div className="text-[9px] text-purple-400 font-medium">Óptimo &gt;1.5</div>
          </div>
          <div className="bg-gray-900/60 p-2 rounded-lg border border-gray-800/60">
            <div className="text-[10px] uppercase font-semibold text-gray-400">Max DD</div>
            <div className="text-base font-bold text-red-400 mono-number mt-0.5">
              {riskMetrics.max_drawdown_pct}%
            </div>
            <div className="text-[9px] text-gray-400 font-mono">Caída máx.</div>
          </div>
        </div>
      </div>
    </section>
  );
};
