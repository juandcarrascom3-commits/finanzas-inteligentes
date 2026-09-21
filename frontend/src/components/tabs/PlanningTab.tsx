import React, { useState } from 'react';
import { Budget, Category, MonthlyReview, RecurringRule } from '../../types';

interface PlanningTabProps {
  budgets: Budget[];
  categories: Category[];
  recurring: RecurringRule[];
  review: MonthlyReview | null;
  privacyMode: boolean;
  onSaveBudget: (budget: Partial<Budget>) => Promise<void>;
  onDeleteBudget: (id: string) => Promise<void>;
  onUpdateRecurring: (id: string, status: RecurringRule['status']) => Promise<void>;
  onSaveSnapshot: () => Promise<void>;
}

const inputClass = "bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500";

export const PlanningTab: React.FC<PlanningTabProps> = ({
  budgets,
  categories,
  recurring,
  review,
  privacyMode,
  onSaveBudget,
  onDeleteBudget,
  onUpdateRecurring,
  onSaveSnapshot
}) => {
  const [budgetForm, setBudgetForm] = useState<Partial<Budget>>({ category: 'General', monthly_limit: 0, currency: 'USD', period: 'MONTHLY', is_active: true, source: 'MANUAL' });
  const money = (value: number) => privacyMode ? '••••' : value.toLocaleString(undefined, { maximumFractionDigits: 0 });

  const submitBudget = async () => {
    await onSaveBudget(budgetForm);
    setBudgetForm({ category: 'General', monthly_limit: 0, currency: 'USD', period: 'MONTHLY', is_active: true, source: 'MANUAL' });
  };

  return (
    <div className="space-y-4">
      <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-white">Monthly Review</h2>
            <p className="text-xs text-gray-400">Resumen → desviaciones → recurrentes → próximo mes → acciones</p>
          </div>
          <button onClick={onSaveSnapshot} className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Guardar cierre mensual</button>
        </div>
        {review && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Ingresos</div><div className="text-emerald-300 font-bold">{money(review.facts.income)}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Gastos</div><div className="text-red-300 font-bold">{money(review.facts.expenses)}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Cashflow</div><div className="text-white font-bold">{money(review.facts.cashflow)}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Ahorro</div><div className="text-white font-bold">{review.facts.savings_rate_pct}%</div></div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div>
                <div className="text-xs font-bold text-gray-300 mb-2">Desviaciones</div>
                {review.budget_variances.slice(0, 6).map((item) => (
                  <div key={item.category} className="flex justify-between text-xs border-b border-gray-800 py-1">
                    <span>{item.category}</span><span className={item.variance > 0 ? 'text-red-300' : 'text-emerald-300'}>{money(item.variance)}</span>
                  </div>
                ))}
              </div>
              <div>
                <div className="text-xs font-bold text-gray-300 mb-2">Próximos pagos</div>
                {review.upcoming_obligations.slice(0, 6).map((item) => (
                  <div key={`${item.merchant}-${item.date}`} className="flex justify-between text-xs border-b border-gray-800 py-1">
                    <span className="truncate">{item.merchant}</span><span>{item.date} · {money(item.amount)}</span>
                  </div>
                ))}
                {review.upcoming_obligations.length === 0 && <div className="text-xs text-gray-500">Sin obligaciones confirmadas próximas.</div>}
              </div>
              <div>
                <div className="text-xs font-bold text-gray-300 mb-2">Acciones</div>
                {review.action_items.slice(0, 6).map((item, index) => (
                  <div key={`${item.type}-${index}`} className="text-xs border-b border-gray-800 py-1">
                    <div className="text-white">{item.reason}</div>
                    <div className="text-emerald-300">{item.action}</div>
                  </div>
                ))}
                {review.action_items.length === 0 && <div className="text-xs text-gray-500">Sin acciones críticas.</div>}
              </div>
            </div>
          </>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-bold text-white">Presupuestos</h3>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} list="budget-categories" placeholder="Categoría" value={budgetForm.category || ''} onChange={(e) => setBudgetForm({ ...budgetForm, category: e.target.value })} />
            <input className={inputClass} type="number" placeholder="Importe" value={budgetForm.monthly_limit ?? 0} onChange={(e) => setBudgetForm({ ...budgetForm, monthly_limit: Number(e.target.value) })} />
            <input className={inputClass} placeholder="Moneda" value={budgetForm.currency || 'USD'} onChange={(e) => setBudgetForm({ ...budgetForm, currency: e.target.value.toUpperCase() })} />
            <select className={inputClass} value={budgetForm.period || 'MONTHLY'} onChange={(e) => setBudgetForm({ ...budgetForm, period: e.target.value })}>
              <option value="MONTHLY">Mensual</option>
              <option value="WEEKLY">Semanal</option>
              <option value="YEARLY">Anual</option>
            </select>
          </div>
          <datalist id="budget-categories">{categories.map((c) => <option key={c.id} value={c.name} />)}</datalist>
          <label className="flex items-center gap-2 text-xs text-gray-300"><input type="checkbox" checked={Boolean(budgetForm.is_active)} onChange={(e) => setBudgetForm({ ...budgetForm, is_active: e.target.checked })} /> Activo</label>
          <button onClick={submitBudget} className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Guardar presupuesto</button>
          <div className="space-y-2 max-h-72 overflow-auto">
            {budgets.map((budget) => (
              <div key={budget.id} className="flex items-center justify-between bg-gray-900/60 rounded-lg p-2 text-xs">
                <button className="text-left" onClick={() => setBudgetForm(budget)}>{budget.category}<span className="text-gray-500"> · {money(budget.monthly_limit)} {budget.currency} · {budget.source}</span></button>
                <button onClick={() => onDeleteBudget(budget.id)} className="text-red-300">Eliminar</button>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-bold text-white">Recurrentes</h3>
          <div className="space-y-2 max-h-96 overflow-auto">
            {recurring.map((item) => (
              <div key={item.id} className="bg-gray-900/60 rounded-lg p-3 text-xs space-y-2">
                <div className="flex justify-between gap-2">
                  <div><div className="text-white font-bold">{item.merchant}</div><div className="text-gray-500">{item.frequency} · {item.category} · {money(item.typical_amount)}</div></div>
                  <span className="text-gray-400">{item.status}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => onUpdateRecurring(item.id, 'confirmed')} className="px-2 py-1 rounded bg-emerald-600 text-white">Confirmar</button>
                  <button onClick={() => onUpdateRecurring(item.id, 'rejected')} className="px-2 py-1 rounded bg-red-500/20 text-red-300">Rechazar</button>
                  <button onClick={() => onUpdateRecurring(item.id, 'ignored')} className="px-2 py-1 rounded bg-gray-800 text-gray-300">Ignorar</button>
                </div>
              </div>
            ))}
            {recurring.length === 0 && <div className="text-xs text-gray-400">Aún no hay candidatos recurrentes.</div>}
          </div>
        </section>
      </div>
    </div>
  );
};
