import React, { useState } from 'react';
import { FileText, Globe, AlertTriangle, CheckCircle2, TrendingUp, Compass, Target } from 'lucide-react';
import { GeopoliticalRisk } from '../../types';

interface ExecutiveReportTabProps {
  geopoliticalRisks: GeopoliticalRisk[];
  currency: 'USD' | 'COP';
  exchangeRate: number;
}

export const ExecutiveReportTab: React.FC<ExecutiveReportTabProps> = ({
  geopoliticalRisks,
  currency,
  exchangeRate
}) => {
  const [period, setPeriod] = useState<'diario' | 'semanal' | 'mensual'>('mensual');

  return (
    <div className="space-y-6">
      {/* Header with Periodicity Selector based on JERARQUIA sketch */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              Informe Estratégico & Diagnóstico Integral
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                A Solicitud &bull; Automático
              </span>
            </h3>
            <p className="text-xs text-gray-400">
              Cumplimiento de objetivos DCA, gestión de riesgo transversal y lectura de mercado
            </p>
          </div>
        </div>

        {/* Periodicity Selector */}
        <div className="flex bg-gray-900 p-1 rounded-lg border border-gray-800 text-xs">
          {(['diario', 'semanal', 'mensual'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-md font-semibold capitalize transition-all ${
                period === p ? 'bg-emerald-600 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Strategic Scorecards: DCA & Risk Alignment */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* DCA Objective Fulfillment */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-4.5 shadow-md space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-gray-400 flex items-center gap-1.5">
              <Target className="w-3.5 h-3.5 text-emerald-400" />
              Objetivo Sistemático (DCA)
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
              100% CUMPLIDO
            </span>
          </div>
          <div className="text-2xl font-extrabold text-white mono-number">
            $1,200.00 <span className="text-xs font-normal text-gray-400">USD aportados este mes</span>
          </div>
          <p className="text-[11px] text-gray-400">
            Próxima ejecución programada: 1 de Octubre, 2026 en SPY &amp; NVDA
          </p>
        </div>

        {/* Paradigm / Thesis Shift Monitor */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-4.5 shadow-md space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-gray-400 flex items-center gap-1.5">
              <Compass className="w-3.5 h-3.5 text-purple-400" />
              Cambio de Paradigma / Tesis
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-bold">
              ESTABLE
            </span>
          </div>
          <div className="text-sm font-bold text-gray-200">
            2 Tesis Certificadas &bull; 2 En Observación
          </div>
          <p className="text-[11px] text-gray-400">
            Filtro Humano operativo previniendo compras emocionales en AAPL y AMZN
          </p>
        </div>

        {/* Currency Impact ($ - COP) */}
        <div className="bg-[#111827] border border-gray-800 rounded-xl p-4.5 shadow-md space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-gray-400">
              Impacto Cambiario ($ - COP)
            </span>
            <span className="text-[10px] font-mono text-emerald-400 font-bold">
              +1.8% Cobertura
            </span>
          </div>
          <div className="text-2xl font-extrabold text-white mono-number">
            $4,050 <span className="text-xs font-normal text-gray-400">COP/USD</span>
          </div>
          <p className="text-[11px] text-gray-400">
            Exposición dolarizada del 86% protege contra devaluación regional
          </p>
        </div>
      </div>

      {/* Geopolitical Risk Radar Scorecard */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-md bg-blue-500/10 text-blue-400">
              <Globe className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white tracking-tight">
                Matriz de Riesgo Geopolítico &amp; Alertas Macro
              </h4>
              <p className="text-[11px] text-gray-400">
                Puntuación de riesgo activo (0 a 100) y detección de anomalías por zona económica
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {geopoliticalRisks.map((item) => {
            const hasAnomaly = Boolean(item.anomaly_alert);
            const score = item.active_risk_score;

            return (
              <div
                key={item.region}
                className={`p-4 rounded-xl border transition-all ${
                  hasAnomaly
                    ? 'bg-red-500/5 border-red-500/30'
                    : score > 45
                    ? 'bg-amber-500/5 border-amber-500/30'
                    : 'bg-gray-900/60 border-gray-800'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-white">{item.region}</span>
                  {hasAnomaly ? (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1 font-mono">
                      <AlertTriangle className="w-3 h-3" /> ANOMALÍA
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      Normal
                    </span>
                  )}
                </div>

                <div className="flex items-baseline justify-between mt-2">
                  <span className="text-xs text-gray-400 font-medium">Riesgo Activo:</span>
                  <span className={`text-lg font-extrabold mono-number ${
                    hasAnomaly ? 'text-red-400' : score > 45 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {score}/100
                  </span>
                </div>

                <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden mt-2">
                  <div
                    className={`h-1.5 rounded-full ${
                      hasAnomaly ? 'bg-red-500' : score > 45 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${score}%` }}
                  />
                </div>

                <p className="text-[11px] text-gray-300 mt-2.5 leading-snug">
                  {item.headline}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
