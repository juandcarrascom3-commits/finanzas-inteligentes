import React, { useState } from 'react';
import { Calendar, AlertCircle, CheckCircle2, AlertTriangle, TrendingUp, ShieldCheck, Clock, DollarSign } from 'lucide-react';
import { PanoramaData } from '../../types';

interface PanoramaTabProps {
  data: PanoramaData;
  currency: 'USD' | 'COP';
  exchangeRate: number;
}

export const PanoramaTab: React.FC<PanoramaTabProps> = ({ data, currency, exchangeRate }) => {
  const [selectedHorizon, setSelectedHorizon] = useState<'3' | '6' | '12'>('6');

  const formatMoney = (usdVal: number) => {
    if (currency === 'USD') {
      return `$${usdVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;
    }
    return `$${(usdVal * exchangeRate).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })} COP`;
  };

  const getHorizonTotal = () => {
    switch (selectedHorizon) {
      case '3':
        return data.projections_summary['3_months_net'];
      case '6':
        return data.projections_summary['6_months_net'];
      case '12':
        return data.projections_summary['12_months_net'];
      default:
        return data.projections_summary['6_months_net'];
    }
  };

  return (
    <div className="space-y-6">
      {/* Overview Cards: Runway & Projected Superavit */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Runway Card */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-4.5 shadow-md flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold uppercase text-gray-400 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-blue-400" />
              Colchón de Seguridad (Runway)
            </span>
            <div className="text-2xl font-extrabold text-white mono-number mt-1">
              {data.runway_months} <span className="text-sm font-normal text-gray-400">meses</span>
            </div>
            <p className="text-[11px] text-gray-400 mt-0.5">
              Cobertura de gastos corrientes con reservas líquidas
            </p>
          </div>
          <div className="w-12 h-12 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
        </div>

        {/* Superavit Operativo */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-4.5 shadow-md flex items-center justify-between">
          <div>
            <span className="text-xs font-semibold uppercase text-gray-400 flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
              Superávit Operativo Mensual
            </span>
            <div className="text-2xl font-extrabold text-emerald-400 mono-number mt-1">
              +{formatMoney(data.monthly_net_savings)}
            </div>
            <p className="text-[11px] text-gray-400 mt-0.5">
              Capacidad neta recurrente para inyección DCA
            </p>
          </div>
          <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <DollarSign className="w-6 h-6" />
          </div>
        </div>

        {/* Cumulative Target by Horizon */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-4.5 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-gray-400">
              Acumulación a {selectedHorizon} Meses
            </span>
            <div className="flex bg-gray-900 p-0.5 rounded-lg border border-gray-800 text-[10px]">
              {(['3', '6', '12'] as const).map((h) => (
                <button
                  key={h}
                  onClick={() => setSelectedHorizon(h)}
                  className={`px-2 py-0.5 rounded font-mono font-medium transition-all ${
                    selectedHorizon === h ? 'bg-emerald-600 text-white' : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  {h}M
                </button>
              ))}
            </div>
          </div>
          <div className="text-2xl font-extrabold text-white mono-number mt-1">
            +{formatMoney(getHorizonTotal())}
          </div>
          <p className="text-[11px] text-gray-400 mt-0.5">
            Proyección acumulada bajo disciplina presupuestal
          </p>
        </div>
      </div>

      {/* Checklist Semafórico Interactivo */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-400">
              <AlertCircle className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-tight">
                Checklist Presupuestal Semafórico
              </h3>
              <p className="text-[11px] text-gray-400">
                Alertas visuales automatizadas basadas en contabilidad histórica y márgenes de seguridad
              </p>
            </div>
          </div>
          <span className="text-xs font-mono text-emerald-400 px-2.5 py-1 rounded bg-emerald-500/10 border border-emerald-500/20">
            🟢 3 Óptimos &bull; 🟠 1 Moderado
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {data.checklist.map((item) => {
            const isGreen = item.status === 'GREEN';
            const isOrange = item.status === 'ORANGE';

            return (
              <div
                key={item.id}
                className={`p-3.5 rounded-xl border transition-all ${
                  isGreen
                    ? 'bg-emerald-500/5 border-emerald-500/30'
                    : isOrange
                    ? 'bg-amber-500/5 border-amber-500/30'
                    : 'bg-red-500/5 border-red-500/30'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-2">
                    {isGreen ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    ) : isOrange ? (
                      <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                    )}
                    <span className="text-xs font-bold text-white">{item.title}</span>
                  </div>
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
                    isGreen
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                      : isOrange
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                      : 'bg-red-500/10 text-red-400 border-red-500/30'
                  }`}>
                    {item.value}
                  </span>
                </div>
                <p className="text-[11px] text-gray-300 mt-2 pl-6">
                  {item.message}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Monthly Projections Table */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
          <div className="flex items-center space-x-2">
            <Calendar className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-bold text-white">
              Cronograma de Flujos Futuros (12 Meses)
            </h3>
          </div>
          <span className="text-[11px] text-gray-400 font-mono">
            Modelo con deriva inflacionaria calculada
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 uppercase text-[10px] tracking-wider">
                <th className="py-2.5 px-3">Mes</th>
                <th className="py-2.5 px-3">Ingresos Estimados</th>
                <th className="py-2.5 px-3">Gastos Estimados</th>
                <th className="py-2.5 px-3">Superávit Neto</th>
                <th className="py-2.5 px-3">Ahorro Acumulado</th>
                <th className="py-2.5 px-3">Liquidez Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-mono">
              {data.monthly_timeline.slice(0, parseInt(selectedHorizon, 10)).map((row) => (
                <tr key={row.month} className="hover:bg-gray-800/40 transition-colors">
                  <td className="py-2.5 px-3 font-semibold text-white">Mes +{row.month}</td>
                  <td className="py-2.5 px-3 text-emerald-400">+{formatMoney(row.projected_income)}</td>
                  <td className="py-2.5 px-3 text-red-400">-{formatMoney(row.projected_expenses)}</td>
                  <td className="py-2.5 px-3 text-white font-bold">+{formatMoney(row.monthly_net)}</td>
                  <td className="py-2.5 px-3 text-blue-300">+{formatMoney(row.cumulative_savings)}</td>
                  <td className="py-2.5 px-3 text-emerald-300 font-bold">{formatMoney(row.total_liquidity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
