import React from 'react';
import { UnderstandSummary } from '../../types';

interface UnderstandTabProps {
  data: UnderstandSummary | null;
  period: string;
  setPeriod: (period: string) => void;
  privacyMode: boolean;
}

const money = (value: number, privacyMode: boolean) => privacyMode ? '••••' : value.toLocaleString(undefined, { maximumFractionDigits: 0 });

export const UnderstandTab: React.FC<UnderstandTabProps> = ({ data, period, setPeriod, privacyMode }) => {
  if (!data) {
    return <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 text-sm text-gray-400">Sin datos suficientes para analizar todavía.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-white">Understand</h2>
          <p className="text-xs text-gray-400">Hechos calculados desde datos persistidos. Sin IA.</p>
        </div>
        <select value={period} onChange={(e) => setPeriod(e.target.value)} className="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white">
          <option value="current_month">Mes actual</option>
          <option value="previous_month">Mes anterior</option>
          <option value="last_30_days">Últimos 30 días</option>
        </select>
      </div>

      <section className="bg-[#111827] border border-gray-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-white mb-3">Qué requiere atención</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {data.action_items.length === 0 && <div className="text-xs text-gray-400">No hay acciones pendientes claras.</div>}
          {data.action_items.map((item, index) => (
            <div key={`${item.type}-${index}`} className="bg-gray-900/60 rounded-lg p-3 text-xs">
              <div className="text-white font-bold">{item.title}</div>
              <div className="text-gray-400">{item.why}</div>
              <div className="text-emerald-300 mt-1">{item.action}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-bold text-white">Qué cambió</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Ingresos</div><div className="text-emerald-300 font-bold">{money(data.what_changed.facts.income, privacyMode)}</div></div>
          <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Gastos</div><div className="text-red-300 font-bold">{money(data.what_changed.facts.expenses, privacyMode)}</div></div>
          <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Cashflow</div><div className="text-white font-bold">{money(data.what_changed.facts.cashflow, privacyMode)}</div></div>
          <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Ahorro</div><div className="text-white font-bold">{data.what_changed.facts.savings_rate_pct}%</div></div>
        </div>
        <div className="text-xs text-gray-400">Interpretación: {data.what_changed.interpretation.join(' ')}</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <div className="text-xs font-bold text-gray-300 mb-2">Categorías que más cambiaron</div>
            {data.what_changed.category_changes.map((item) => (
              <div key={item.category} className="flex justify-between text-xs border-b border-gray-800 py-1">
                <span>{item.category}</span><span className={item.delta > 0 ? 'text-red-300' : 'text-emerald-300'}>{money(item.delta, privacyMode)}</span>
              </div>
            ))}
          </div>
          <div>
            <div className="text-xs font-bold text-gray-300 mb-2">Movimientos de mayor impacto</div>
            {data.what_changed.largest_transactions.slice(0, 6).map((tx) => (
              <div key={tx.id} className="flex justify-between text-xs border-b border-gray-800 py-1">
                <span className="truncate">{tx.description || tx.category}</span><span>{money(tx.amount, privacyMode)}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-bold text-white mb-3">Qué viene después</h3>
          <div className="text-xs text-gray-400 mb-2">Saldo proyectado 30 días: <span className="text-white font-bold">{money(data.cashflow_forecast.projected_balance, privacyMode)}</span></div>
          <div className="text-xs text-gray-500">Incertidumbre: {data.cashflow_forecast.uncertainty}</div>
        </section>
        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-bold text-white mb-3">Recurrentes</h3>
          {data.recurring.slice(0, 5).map((item) => (
            <div key={`${item.merchant}-${item.typical_amount}`} className="text-xs border-b border-gray-800 py-1">
              <div className="text-white">{item.merchant}</div>
              <div className="text-gray-500">{item.confidence} · {item.frequency} · {money(item.typical_amount, privacyMode)}</div>
            </div>
          ))}
          {data.recurring.length === 0 && <div className="text-xs text-gray-400">Aún no hay historial suficiente.</div>}
        </section>
        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-bold text-white mb-3">Presupuestos</h3>
          {data.budget_burn.map((item) => (
            <div key={item.category} className="text-xs border-b border-gray-800 py-1">
              <div className="flex justify-between"><span>{item.category}</span><span>{item.spent_pct}%</span></div>
              <div className={item.status === 'on_track' ? 'text-emerald-300' : 'text-amber-300'}>{item.status}</div>
            </div>
          ))}
          {data.budget_burn.length === 0 && <div className="text-xs text-gray-400">No hay presupuestos configurados.</div>}
        </section>
      </div>
    </div>
  );
};
