import React, { useState } from 'react';
import { Budget, CalculatorKind, CalculatorResult, CashProjectionResult, Category, FinancialEvent, MonthlyReview, RecurringRule, SafeToSpendResult, ScenarioEvaluationResult, ScenarioType } from '../../types';

interface PlanningTabProps {
  budgets: Budget[];
  categories: Category[];
  recurring: RecurringRule[];
  financialEvents: FinancialEvent[];
  review: MonthlyReview | null;
  privacyMode: boolean;
  onSaveBudget: (budget: Partial<Budget>) => Promise<void>;
  onDeleteBudget: (id: string) => Promise<void>;
  onUpdateRecurring: (id: string, status: RecurringRule['status']) => Promise<void>;
  onSaveSnapshot: () => Promise<void>;
  onRunCalculator: (kind: string, payload: Record<string, unknown>) => Promise<CalculatorResult>;
  onRunCashProjection: (payload: Record<string, unknown>) => Promise<CashProjectionResult>;
  onRunSafeToSpend: (payload: Record<string, unknown>) => Promise<SafeToSpendResult>;
  onRunRunway: (payload: Record<string, unknown>) => Promise<CalculatorResult>;
  onEvaluateScenario: (payload: Record<string, unknown>) => Promise<ScenarioEvaluationResult>;
}

const inputClass = "bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500";
const planLabel: Record<string, string> = {
  UNDER_PLAN: 'Por debajo del presupuesto',
  ON_PLAN: 'En el límite previsto',
  OVER_PLAN: 'Por encima del presupuesto',
};
const paceLabel: Record<string, string> = {
  UNDER_PACE: 'Ritmo por debajo del esperado',
  ON_PACE: 'Ritmo alineado con el mes',
  OVER_PACE: 'Ritmo por encima del esperado',
  UNEVALUABLE: 'Ritmo no evaluable',
};

export const PlanningTab: React.FC<PlanningTabProps> = ({
  budgets,
  categories,
  recurring,
  financialEvents,
  review,
  privacyMode,
  onSaveBudget,
  onDeleteBudget,
  onUpdateRecurring,
  onSaveSnapshot,
  onRunCalculator,
  onRunCashProjection,
  onRunSafeToSpend,
  onRunRunway,
  onEvaluateScenario
}) => {
  const [budgetForm, setBudgetForm] = useState<Partial<Budget>>({ category: 'General', monthly_limit: 0, currency: 'USD', period: 'MONTHLY', is_active: true, source: 'MANUAL' });
  const [calculatorKind, setCalculatorKind] = useState<CalculatorKind>('savings-goal');
  const [calcForm, setCalcForm] = useState<Record<string, number | string>>({
    currency: 'COP',
    target: 12000000,
    current_amount: 3000000,
    annual_effective_rate_pct: 0,
    periods: 9,
    periodic_contribution: 100000,
    principal: 1000000,
    liquid_resources: 12000000,
    essential_monthly_expenses: 3000000,
    balance: 12000000,
    monthly_payment: 1000000,
    extra_payment: 0,
    amount: 1000000,
    contribution_timing: 'END'
  });
  const [calcResult, setCalcResult] = useState<CalculatorResult | null>(null);
  const [calcError, setCalcError] = useState<string | null>(null);
  const [cashForm, setCashForm] = useState<Record<string, number | string>>({ currency: 'COP', starting_balance: 5000000, reserve_floor: 2000000, essential_monthly_expenses: 3000000, horizon_days: 30 });
  const [cashProjection, setCashProjection] = useState<CashProjectionResult | null>(null);
  const [safeResult, setSafeResult] = useState<SafeToSpendResult | null>(null);
  const [runwayResult, setRunwayResult] = useState<CalculatorResult | null>(null);
  const [cashError, setCashError] = useState<string | null>(null);
  const [scenarioType, setScenarioType] = useState<ScenarioType>('CASH');
  const [scenarioForm, setScenarioForm] = useState<Record<string, number | string>>({
    currency: 'COP',
    starting_balance: 5000000,
    reserve_floor: 2000000,
    horizon_days: 30,
    weekly_variable_spend_delta: -100000,
    balance: 12000000,
    monthly_payment: 1000000,
    extra_payment: 300000,
    annual_effective_rate_pct: 0,
    current_amount: 3000000,
    target_amount: 12000000,
    periods: 12,
    monthly_contribution: 500000,
    monthly_contribution_override: 800000,
    contribution_timing: 'END'
  });
  const [scenarioResult, setScenarioResult] = useState<ScenarioEvaluationResult | null>(null);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const money = (value: number) => privacyMode ? '••••' : value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  const todayIso = new Date().toISOString().slice(0, 10);
  const sevenDaysOut = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

  const submitBudget = async () => {
    await onSaveBudget(budgetForm);
    setBudgetForm({ category: 'General', monthly_limit: 0, currency: 'USD', period: 'MONTHLY', is_active: true, source: 'MANUAL' });
  };

  const setCalcValue = (key: string, value: number | string) => setCalcForm((current) => ({ ...current, [key]: value }));

  const calculatorPayload = (): Record<string, unknown> => {
    const base = { annual_effective_rate_pct: Number(calcForm.annual_effective_rate_pct || 0), currency: String(calcForm.currency || 'COP') };
    if (calculatorKind === 'compound') return { ...base, principal: Number(calcForm.principal || 0), periodic_contribution: Number(calcForm.periodic_contribution || 0), periods: Number(calcForm.periods || 0), contribution_timing: calcForm.contribution_timing || 'END' };
    if (calculatorKind === 'emergency-fund') return { currency: base.currency, liquid_resources: Number(calcForm.liquid_resources || 0), essential_monthly_expenses: Number(calcForm.essential_monthly_expenses || 0) };
    if (calculatorKind === 'debt-payoff') return { ...base, balance: Number(calcForm.balance || 0), monthly_payment: Number(calcForm.monthly_payment || 0), extra_payment: Number(calcForm.extra_payment || 0) };
    if (calculatorKind === 'opportunity-cost') return { ...base, amount: Number(calcForm.amount || 0), periods: Number(calcForm.periods || 0) };
    return { ...base, target: Number(calcForm.target || 0), current_amount: Number(calcForm.current_amount || 0), periods: Number(calcForm.periods || 0), contribution_timing: calcForm.contribution_timing || 'END' };
  };

  const runSelectedCalculator = async () => {
    setCalcError(null);
    try {
      setCalcResult(await onRunCalculator(calculatorKind, calculatorPayload()));
    } catch (err: any) {
      setCalcError(err.message || 'No se pudo calcular.');
    }
  };

  const renderCalculatorResult = () => {
    if (!calcResult) return <div className="text-xs text-gray-500">Sin resultado todavía.</div>;
    if (calculatorKind === 'savings-goal') return <div className="text-xs text-gray-300">Aporte requerido: <span className="text-white font-bold">{calcResult.required_contribution == null ? 'No evaluable' : `${money(calcResult.required_contribution)} ${calcResult.currency}`}</span><div className="text-gray-500">Estado: {calcResult.status || calcResult.reason}</div></div>;
    if (calculatorKind === 'compound') return <div className="text-xs text-gray-300">Valor futuro: <span className="text-white font-bold">{money(calcResult.future_value || 0)} {calcResult.currency}</span><div className="text-gray-500">Crecimiento: {money(calcResult.growth || 0)}</div></div>;
    if (calculatorKind === 'emergency-fund') return <div className="text-xs text-gray-300">Cobertura: <span className="text-white font-bold">{calcResult.coverage_months == null ? 'No evaluable' : `${calcResult.coverage_months.toFixed(2)} meses`}</span><div className="text-gray-500">{calcResult.reason || calcResult.evaluability}</div></div>;
    if (calculatorKind === 'debt-payoff') return <div className="text-xs text-gray-300">Estado: <span className="text-white font-bold">{calcResult.payoff_status}</span><div className="text-gray-500">Periodos: {calcResult.periods ?? 'N/A'} · Interés: {calcResult.total_interest == null ? 'N/A' : money(calcResult.total_interest)}</div></div>;
    return <div className="text-xs text-gray-300">Costo de oportunidad: <span className="text-white font-bold">{money(calcResult.opportunity_cost || 0)} {calcResult.currency}</span><div className="text-gray-500">Valor supuesto: {money(calcResult.assumed_future_value || 0)}</div></div>;
  };
  const setCashValue = (key: string, value: number | string) => setCashForm((current) => ({ ...current, [key]: value }));
  const setScenarioValue = (key: string, value: number | string) => setScenarioForm((current) => ({ ...current, [key]: value }));
  const scenarioPayload = () => {
    const currency = String(scenarioForm.currency || 'COP').toUpperCase();
    if (scenarioType === 'DEBT') {
      return {
        scenario_type: 'DEBT',
        context: { currency, balance: Number(scenarioForm.balance || 0), annual_effective_rate_pct: Number(scenarioForm.annual_effective_rate_pct || 0), monthly_payment: Number(scenarioForm.monthly_payment || 0) },
        overrides: { extra_payment: Number(scenarioForm.extra_payment || 0) }
      };
    }
    if (scenarioType === 'GOAL') {
      return {
        scenario_type: 'GOAL',
        context: { currency, current_amount: Number(scenarioForm.current_amount || 0), target_amount: Number(scenarioForm.target_amount || 0), annual_effective_rate_pct: Number(scenarioForm.annual_effective_rate_pct || 0), periods: Number(scenarioForm.periods || 0), monthly_contribution: Number(scenarioForm.monthly_contribution || 0), contribution_timing: scenarioForm.contribution_timing || 'END' },
        overrides: { monthly_contribution_override: Number(scenarioForm.monthly_contribution_override || 0) }
      };
    }
    return {
      scenario_type: 'CASH',
      context: { currency, horizon_days: Number(scenarioForm.horizon_days || 30), starting_balance: Number(scenarioForm.starting_balance || 0), reserve_floor: Number(scenarioForm.reserve_floor || 0) },
      overrides: { weekly_variable_spend_delta: Number(scenarioForm.weekly_variable_spend_delta || 0) }
    };
  };
  const runScenario = async () => {
    setScenarioError(null);
    try {
      setScenarioResult(await onEvaluateScenario(scenarioPayload()));
    } catch (err: any) {
      setScenarioError(err.message || 'No se pudo evaluar el escenario.');
    }
  };
  const scenarioMainMetric = () => {
    if (!scenarioResult) return null;
    if (scenarioResult.scenario_type === 'CASH') {
      return {
        label: 'Safe-to-Spend',
        baseline: scenarioResult.baseline?.safe_to_spend?.safe_to_spend,
        scenario: scenarioResult.scenario?.safe_to_spend?.safe_to_spend,
        delta: scenarioResult.deltas?.safe_to_spend,
        currency: scenarioResult.baseline?.safe_to_spend?.currency
      };
    }
    if (scenarioResult.scenario_type === 'DEBT') {
      return { label: 'Periodos', baseline: scenarioResult.baseline?.periods, scenario: scenarioResult.scenario?.periods, delta: scenarioResult.deltas?.periods, currency: '' };
    }
    return {
      label: 'ETA meta',
      baseline: scenarioResult.baseline?.goal_eta?.periods_required,
      scenario: scenarioResult.scenario?.goal_eta?.periods_required,
      delta: scenarioResult.deltas?.goal_eta_periods,
      currency: ''
    };
  };
  const runCashIntelligence = async () => {
    setCashError(null);
    const payload = { currency: cashForm.currency, horizon_days: Number(cashForm.horizon_days || 30), starting_balance: Number(cashForm.starting_balance || 0), reserve_floor: Number(cashForm.reserve_floor || 0) };
    try {
      const [projection, safe, runway] = await Promise.all([
        onRunCashProjection(payload),
        onRunSafeToSpend(payload),
        onRunRunway({ currency: cashForm.currency, liquid_resources: Number(cashForm.starting_balance || 0), essential_monthly_expenses: Number(cashForm.essential_monthly_expenses || 0) })
      ]);
      setCashProjection(projection);
      setSafeResult(safe);
      setRunwayResult(runway);
    } catch (err: any) {
      setCashError(err.message || 'No se pudo calcular caja.');
    }
  };
  const eventGroups = {
    TODAY: financialEvents.filter((event) => event.date === todayIso),
    NEXT_7_DAYS: financialEvents.filter((event) => event.date > todayIso && event.date <= sevenDaysOut),
    LATER: financialEvents.filter((event) => event.date > sevenDaysOut),
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
                <div className="text-xs font-bold text-gray-300 mb-2">Plan vs actual</div>
                {(review.plan_vs_actual || []).slice(0, 6).map((item) => (
                  <div key={item.category} className="flex justify-between text-xs border-b border-gray-800 py-1">
                    <span>{item.category}<span className="text-gray-500"> · {planLabel[item.status] || item.status}</span></span>
                    <span className={item.status === 'OVER_PLAN' ? 'text-red-300' : item.status === 'ON_PLAN' ? 'text-amber-300' : 'text-emerald-300'}>{money(item.variance)} {item.currency}</span>
                  </div>
                ))}
                {(review.plan_vs_actual || []).length === 0 && <div className="text-xs text-gray-500">Sin presupuestos comparables.</div>}
                <div className="text-xs font-bold text-gray-300 mt-3 mb-2">Ritmo de presupuesto</div>
                {(review.budget_burn || []).slice(0, 4).map((item) => (
                  <div key={`${item.category}-${item.currency}`} className="flex justify-between text-xs border-b border-gray-800 py-1">
                    <span>{item.category}<span className="text-gray-500"> · {paceLabel[item.pace_status || ''] || item.pace_status}</span></span>
                    <span>{money(item.pace_projection || item.projected_close)} {item.currency}</span>
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
          <h3 className="text-sm font-bold text-white">Caja corto plazo</h3>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} placeholder="Moneda" value={cashForm.currency} onChange={(e) => setCashValue('currency', e.target.value.toUpperCase())} />
            <input className={inputClass} type="number" placeholder="Horizonte días" value={cashForm.horizon_days} onChange={(e) => setCashValue('horizon_days', Number(e.target.value))} />
            <input className={inputClass} type="number" placeholder="Balance inicial" value={cashForm.starting_balance} onChange={(e) => setCashValue('starting_balance', Number(e.target.value))} />
            <input className={inputClass} type="number" placeholder="Reserva mínima" value={cashForm.reserve_floor} onChange={(e) => setCashValue('reserve_floor', Number(e.target.value))} />
            <input className={inputClass} type="number" placeholder="Gasto esencial mensual" value={cashForm.essential_monthly_expenses} onChange={(e) => setCashValue('essential_monthly_expenses', Number(e.target.value))} />
          </div>
          <button onClick={runCashIntelligence} className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Calcular caja</button>
          {cashError && <div className="text-xs text-red-300">{cashError}</div>}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
            <div className="bg-gray-900/60 rounded-lg p-3"><div className="text-gray-500">Balance con eventos</div><div className="text-white font-bold">{cashProjection?.balance_after_known_events == null ? 'N/A' : `${money(cashProjection.balance_after_known_events)} ${cashProjection.currency}`}</div><div className="text-gray-500">{cashProjection?.status || 'Sin cálculo'}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-3"><div className="text-gray-500">Proyectado</div><div className="text-white font-bold">{cashProjection?.projected_balance == null ? 'No disponible' : `${money(cashProjection.projected_balance)} ${cashProjection.currency}`}</div><div className="text-gray-500">Confianza {cashProjection?.confidence || 'N/A'}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-3"><div className="text-gray-500">Safe-to-Spend</div><div className="text-white font-bold">{safeResult?.safe_to_spend == null ? 'No evaluable' : `${money(safeResult.safe_to_spend)} ${safeResult.currency}`}</div><div className="text-gray-500">Runway {runwayResult?.coverage_months == null ? 'N/A' : `${runwayResult.coverage_months.toFixed(1)} meses`}</div></div>
          </div>
        </section>

        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-bold text-white">Scenario Lab</h3>
          <div className="grid grid-cols-2 gap-2">
            <select className={inputClass} value={scenarioType} onChange={(e) => { setScenarioType(e.target.value as ScenarioType); setScenarioResult(null); }}>
              <option value="CASH">Caja</option>
              <option value="DEBT">Deuda</option>
              <option value="GOAL">Meta</option>
            </select>
            <input className={inputClass} placeholder="Moneda" value={scenarioForm.currency} onChange={(e) => setScenarioValue('currency', e.target.value.toUpperCase())} />
            {scenarioType === 'CASH' && <>
              <input className={inputClass} type="number" placeholder="Balance inicial" value={scenarioForm.starting_balance} onChange={(e) => setScenarioValue('starting_balance', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Reserva" value={scenarioForm.reserve_floor} onChange={(e) => setScenarioValue('reserve_floor', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Horizonte días" value={scenarioForm.horizon_days} onChange={(e) => setScenarioValue('horizon_days', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Cambio gasto semanal" value={scenarioForm.weekly_variable_spend_delta} onChange={(e) => setScenarioValue('weekly_variable_spend_delta', Number(e.target.value))} />
            </>}
            {scenarioType === 'DEBT' && <>
              <input className={inputClass} type="number" placeholder="Saldo deuda" value={scenarioForm.balance} onChange={(e) => setScenarioValue('balance', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Pago mensual" value={scenarioForm.monthly_payment} onChange={(e) => setScenarioValue('monthly_payment', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Pago extra" value={scenarioForm.extra_payment} onChange={(e) => setScenarioValue('extra_payment', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Tasa % E.A." value={scenarioForm.annual_effective_rate_pct} onChange={(e) => setScenarioValue('annual_effective_rate_pct', Number(e.target.value))} />
            </>}
            {scenarioType === 'GOAL' && <>
              <input className={inputClass} type="number" placeholder="Actual" value={scenarioForm.current_amount} onChange={(e) => setScenarioValue('current_amount', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Meta" value={scenarioForm.target_amount} onChange={(e) => setScenarioValue('target_amount', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Aporte actual" value={scenarioForm.monthly_contribution} onChange={(e) => setScenarioValue('monthly_contribution', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Aporte escenario" value={scenarioForm.monthly_contribution_override} onChange={(e) => setScenarioValue('monthly_contribution_override', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Periodos" value={scenarioForm.periods} onChange={(e) => setScenarioValue('periods', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Tasa % E.A." value={scenarioForm.annual_effective_rate_pct} onChange={(e) => setScenarioValue('annual_effective_rate_pct', Number(e.target.value))} />
            </>}
          </div>
          <button onClick={runScenario} className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Evaluar escenario</button>
          {scenarioError && <div className="text-xs text-red-300">{scenarioError}</div>}
          {(() => {
            const metric = scenarioMainMetric();
            if (!metric) return <div className="text-xs text-gray-500 bg-gray-900/60 rounded-lg p-3">Sin escenario todavía.</div>;
            return (
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-gray-900/60 rounded-lg p-3"><div className="text-gray-500">Referencia</div><div className="text-white font-bold">{metric.baseline == null ? 'N/A' : `${money(Number(metric.baseline))} ${metric.currency}`}</div></div>
                <div className="bg-gray-900/60 rounded-lg p-3"><div className="text-gray-500">Escenario</div><div className="text-white font-bold">{metric.scenario == null ? 'N/A' : `${money(Number(metric.scenario))} ${metric.currency}`}</div></div>
                <div className="bg-gray-900/60 rounded-lg p-3"><div className="text-gray-500">Delta</div><div className="text-white font-bold">{metric.delta == null ? 'N/A' : `${money(Number(metric.delta))} ${metric.currency}`}</div></div>
                <div className="col-span-3 text-[11px] text-gray-500">Estado {scenarioResult?.status} · métricas: {(scenarioResult?.affected_metrics || []).join(', ') || 'N/A'}</div>
              </div>
            );
          })()}
        </section>

        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-bold text-white">Agenda financiera</h3>
          {(['TODAY', 'NEXT_7_DAYS', 'LATER'] as const).map((group) => (
            <div key={group}>
              <div className="text-xs font-bold text-gray-400 mb-1">{group === 'TODAY' ? 'Hoy' : group === 'NEXT_7_DAYS' ? 'Próximos 7 días' : 'Después'}</div>
              {eventGroups[group].slice(0, 6).map((event) => (
                <div key={event.id} className="flex justify-between gap-2 text-xs border-b border-gray-800 py-1">
                  <span className="truncate">{event.label}<span className="text-gray-500"> · {event.date} · {event.certainty} · {event.confidence}</span></span>
                  <span className={event.direction === 'INFLOW' ? 'text-emerald-300' : 'text-red-300'}>{money(event.amount)} {event.currency}</span>
                </div>
              ))}
              {eventGroups[group].length === 0 && <div className="text-xs text-gray-600 mb-2">Sin eventos esperados.</div>}
            </div>
          ))}
        </section>

        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-bold text-white">Calculadoras</h3>
          <select className={inputClass} value={calculatorKind} onChange={(e) => { setCalculatorKind(e.target.value as CalculatorKind); setCalcResult(null); }}>
            <option value="savings-goal">Meta de ahorro</option>
            <option value="compound">Interés compuesto / DCA</option>
            <option value="emergency-fund">Fondo de emergencia</option>
            <option value="debt-payoff">Pago de deuda</option>
            <option value="opportunity-cost">Costo de oportunidad</option>
          </select>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} placeholder="Moneda" value={calcForm.currency} onChange={(e) => setCalcValue('currency', e.target.value.toUpperCase())} />
            {calculatorKind === 'savings-goal' && <>
              <input className={inputClass} type="number" placeholder="Meta" value={calcForm.target} onChange={(e) => setCalcValue('target', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Actual" value={calcForm.current_amount} onChange={(e) => setCalcValue('current_amount', Number(e.target.value))} />
            </>}
            {calculatorKind === 'compound' && <>
              <input className={inputClass} type="number" placeholder="Principal" value={calcForm.principal} onChange={(e) => setCalcValue('principal', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Aporte periódico" value={calcForm.periodic_contribution} onChange={(e) => setCalcValue('periodic_contribution', Number(e.target.value))} />
            </>}
            {calculatorKind === 'emergency-fund' && <>
              <input className={inputClass} type="number" placeholder="Recursos líquidos" value={calcForm.liquid_resources} onChange={(e) => setCalcValue('liquid_resources', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Gastos esenciales/mes" value={calcForm.essential_monthly_expenses} onChange={(e) => setCalcValue('essential_monthly_expenses', Number(e.target.value))} />
            </>}
            {calculatorKind === 'debt-payoff' && <>
              <input className={inputClass} type="number" placeholder="Saldo deuda" value={calcForm.balance} onChange={(e) => setCalcValue('balance', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Pago mensual" value={calcForm.monthly_payment} onChange={(e) => setCalcValue('monthly_payment', Number(e.target.value))} />
              <input className={inputClass} type="number" placeholder="Pago extra" value={calcForm.extra_payment} onChange={(e) => setCalcValue('extra_payment', Number(e.target.value))} />
            </>}
            {calculatorKind === 'opportunity-cost' && <input className={inputClass} type="number" placeholder="Monto" value={calcForm.amount} onChange={(e) => setCalcValue('amount', Number(e.target.value))} />}
            {calculatorKind !== 'emergency-fund' && <>
              <input className={inputClass} type="number" placeholder="Tasa % E.A." value={calcForm.annual_effective_rate_pct} onChange={(e) => setCalcValue('annual_effective_rate_pct', Number(e.target.value))} />
              {calculatorKind !== 'debt-payoff' && <input className={inputClass} type="number" placeholder="Periodos" value={calcForm.periods} onChange={(e) => setCalcValue('periods', Number(e.target.value))} />}
            </>}
          </div>
          <button onClick={runSelectedCalculator} className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Calcular</button>
          {calcError && <div className="text-xs text-red-300">{calcError}</div>}
          <div className="bg-gray-900/60 rounded-lg p-3">{renderCalculatorResult()}</div>
          {calcResult?.assumptions && <div className="text-[11px] text-gray-500">Supuestos: tasa efectiva anual, sin FX, moneda única del cálculo.</div>}
        </section>

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
