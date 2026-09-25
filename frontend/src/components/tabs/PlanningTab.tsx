import React, { useState } from 'react';
import { Budget, CalculatorKind, CalculatorResult, CashProjectionResult, Category, FinancialEvent, MonthlyReview, RecurringRule, SafeToSpendResult, ScenarioEvaluationResult, ScenarioType } from '../../types';
import { DataState, DeltaDirection, InlineMetric } from '../../aetheris/primitives';

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

/* ---------------------------------------------------------------------------
   Aetheris · capa visual de Plan
   Jerarquía: canvas → elevated (Monthly Review) → surface (workspace)
              → hundido (herramientas) → rail de atención.
   Sin matemáticas nuevas, sin contratos nuevos: solo presentación.
--------------------------------------------------------------------------- */

const inputClass =
  'w-full rounded-[12px] border border-[var(--a-line)] bg-black/10 px-3 py-2 text-xs text-[var(--a-text)] placeholder:text-[var(--a-muted)] focus:outline-none focus:border-[var(--a-brand)] focus:ring-1 focus:ring-[var(--a-brand)]';

/** Acción primaria de página: sólo "Guardar cierre mensual". */
const btnPrimary =
  'rounded-[12px] border border-[var(--a-brand)] bg-[var(--a-brand)] px-3.5 py-2 text-xs font-bold text-[var(--a-bg)] transition-colors hover:opacity-90';

/** Ejecutar una herramienta: identidad Aetheris, no verde. */
const btnRun =
  'w-full rounded-[12px] border border-[var(--a-brand)] bg-[var(--a-active)] px-3.5 py-2 text-xs font-bold text-[var(--a-brand)] transition-colors hover:bg-white/[0.11]';

/** Acción secundaria neutra. */
const btnQuiet =
  'rounded-[12px] border border-[var(--a-line)] bg-[var(--a-surface)] px-3 py-1.5 text-xs font-semibold text-[var(--a-secondary)] transition-colors hover:bg-[var(--a-elevated)]';

/** Semántica: verde = confirmar/positivo, rojo = rechazar/negativo. */
const btnPositive =
  'rounded-[12px] border border-[var(--a-line)] bg-[var(--a-active)] px-3 py-1.5 text-xs font-semibold text-[var(--a-positive)] transition-colors hover:border-[var(--a-positive)]';

const btnNegative =
  'rounded-[12px] border border-[var(--a-line)] bg-[var(--a-active)] px-3 py-1.5 text-xs font-semibold text-[var(--a-negative)] transition-colors hover:border-[var(--a-negative)]';

const tileClass = 'rounded-[12px] border border-[var(--a-line)] bg-black/10 p-3';
const errorClass = 'rounded-[12px] border border-[var(--a-line)] bg-black/10 p-3 text-xs text-[var(--a-negative)]';
const rowClass = 'flex items-baseline justify-between gap-3 border-b border-[var(--a-line)] py-1.5 last:border-b-0';
const listLabel = 'text-xs font-bold text-[var(--a-secondary)]';
const colDivider = 'min-w-0 lg:border-l lg:border-[var(--a-line)] lg:pl-6';

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

const signDirection = (value: number | null | undefined): DeltaDirection => {
  if (value === null || value === undefined || value === 0) return 'neutral';
  return value > 0 ? 'positive' : 'negative';
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
    if (!calcResult) return <DataState state="EMPTY" title="Sin cálculo todavía" detail="Elige una calculadora, revisa los supuestos y ejecuta el cálculo." />;
    if (calculatorKind === 'savings-goal') return <div className="text-xs text-[var(--a-secondary)]">Aporte requerido: <span className="font-bold text-[var(--a-text)]">{calcResult.required_contribution == null ? 'No evaluable' : `${money(calcResult.required_contribution)} ${calcResult.currency}`}</span><div className="a-meta">Estado: {calcResult.status || calcResult.reason}</div></div>;
    if (calculatorKind === 'compound') return <div className="text-xs text-[var(--a-secondary)]">Valor futuro: <span className="font-bold text-[var(--a-text)]">{money(calcResult.future_value || 0)} {calcResult.currency}</span><div className="a-meta">Crecimiento: {money(calcResult.growth || 0)}</div></div>;
    if (calculatorKind === 'emergency-fund') return <div className="text-xs text-[var(--a-secondary)]">Cobertura: <span className="font-bold text-[var(--a-text)]">{calcResult.coverage_months == null ? 'No evaluable' : `${calcResult.coverage_months.toFixed(2)} meses`}</span><div className="a-meta">{calcResult.reason || calcResult.evaluability}</div></div>;
    if (calculatorKind === 'debt-payoff') return <div className="text-xs text-[var(--a-secondary)]">Estado: <span className="font-bold text-[var(--a-text)]">{calcResult.payoff_status}</span><div className="a-meta">Periodos: {calcResult.periods ?? 'N/A'} · Interés: {calcResult.total_interest == null ? 'N/A' : money(calcResult.total_interest)}</div></div>;
    return <div className="text-xs text-[var(--a-secondary)]">Costo de oportunidad: <span className="font-bold text-[var(--a-text)]">{money(calcResult.opportunity_cost || 0)} {calcResult.currency}</span><div className="a-meta">Valor supuesto: {money(calcResult.assumed_future_value || 0)}</div></div>;
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
    <div className="a-enter">
      <div className="a-workspace mt-0">
        {/* ================================================================= */}
        {/* CANVAS: periodo → workspace → herramientas                         */}
        {/* ================================================================= */}
        <section className="a-canvas">
          <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="min-w-0">
              <div className="a-page-kicker">Plan</div>
              <p className="a-page-subtitle mt-3">
                Cómo va el periodo, qué necesita atención, qué viene y dónde actuar, sobre datos locales persistidos.
              </p>
            </div>
            <div className="a-meta shrink-0">
              {review ? `${review.period} · ${review.range.from} → ${review.range.to}` : 'Sin periodo cargado todavía.'}
            </div>
          </header>

          {/* --------------------------------------------------------------
              1 · Monthly Review — entrada principal de Plan
          -------------------------------------------------------------- */}
          <section className="a-elevated mt-7 p-5 md:p-6" aria-labelledby="plan-review-title">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h2 id="plan-review-title" className="text-lg font-bold text-[var(--a-text)]">Monthly Review</h2>
                <p className="a-meta mt-1">Resumen → desviaciones → recurrentes → próximo mes → acciones</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {review && (
                  <span className="hidden rounded-full border border-[var(--a-line)] px-3 py-1 text-[11px] font-bold text-[var(--a-secondary)] md:inline-block">
                    {review.period}
                  </span>
                )}
                <button type="button" onClick={onSaveSnapshot} className={btnPrimary}>Guardar cierre mensual</button>
              </div>
            </div>

            {review ? (
              <>
                {/* 1a · resumen del periodo */}
                <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <InlineMetric label="Ingresos" value={money(review.facts.income)} direction="positive" />
                  <InlineMetric label="Gastos" value={money(review.facts.expenses)} direction="negative" />
                  <InlineMetric label="Cashflow" value={money(review.facts.cashflow)} direction={signDirection(review.facts.cashflow)} />
                  <InlineMetric label="Tasa de ahorro" value={`${review.facts.savings_rate_pct}%`} direction={signDirection(review.facts.savings_rate_pct)} />
                </div>

                <div className="my-6 h-px bg-[var(--a-line)]" />

                {/* 1b · desviaciones | próximos pagos | acciones */}
                <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]">
                  <div className="min-w-0">
                    <div className="a-page-kicker">Desviaciones</div>

                    <div className={`${listLabel} mt-4`}>Plan vs actual</div>
                    <div className="mt-2">
                      {(review.plan_vs_actual || []).slice(0, 6).map((item) => (
                        <div key={item.category} className={rowClass}>
                          <span className="min-w-0 text-xs text-[var(--a-secondary)]">
                            {item.category}
                            <span className="a-meta"> · {planLabel[item.status] || item.status}</span>
                          </span>
                          <span className={`shrink-0 text-xs font-bold tabular-nums ${item.status === 'OVER_PLAN' ? 'text-[var(--a-negative)]' : item.status === 'ON_PLAN' ? 'text-[var(--a-warning)]' : 'text-[var(--a-positive)]'}`}>
                            {money(item.variance)} {item.currency}
                          </span>
                        </div>
                      ))}
                      {(review.plan_vs_actual || []).length === 0 && <DataState state="EMPTY" title="Sin presupuestos comparables" detail="No hay presupuestos del periodo listos para comparar contra el gasto real." />}
                    </div>

                    <div className={`${listLabel} mt-5`}>Ritmo de presupuesto</div>
                    <div className="mt-2">
                      {(review.budget_burn || []).slice(0, 4).map((item) => (
                        <div key={`${item.category}-${item.currency}`} className={rowClass}>
                          <span className="min-w-0 text-xs text-[var(--a-secondary)]">
                            {item.category}
                            <span className="a-meta"> · {paceLabel[item.pace_status || ''] || item.pace_status}</span>
                          </span>
                          <span className="shrink-0 text-xs font-bold tabular-nums text-[var(--a-text)]">
                            {money(item.pace_projection || item.projected_close)} {item.currency}
                          </span>
                        </div>
                      ))}
                      {(review.budget_burn || []).length === 0 && <p className="a-meta">Sin ritmo de presupuesto calculado para este periodo.</p>}
                    </div>
                  </div>

                  <div className={colDivider}>
                    <div className="a-page-kicker">Próximos pagos</div>
                    <div className="mt-4">
                      {review.upcoming_obligations.slice(0, 6).map((item) => (
                        <div key={`${item.merchant}-${item.date}`} className={rowClass}>
                          <span className="min-w-0 truncate text-xs text-[var(--a-secondary)]">{item.merchant}</span>
                          <span className="shrink-0 text-xs tabular-nums text-[var(--a-text)]">{item.date} · {money(item.amount)}</span>
                        </div>
                      ))}
                      {review.upcoming_obligations.length === 0 && <DataState state="EMPTY" title="Sin obligaciones próximas" detail="El backend no confirmó pagos con fecha dentro del horizonte." />}
                    </div>
                  </div>

                  <div className={colDivider}>
                    <div className="a-page-kicker">Acciones</div>
                    <div className="mt-4">
                      {review.action_items.slice(0, 6).map((item, index) => (
                        <div key={`${item.type}-${index}`} className="border-b border-[var(--a-line)] py-2 last:border-b-0">
                          <div className="text-xs font-semibold text-[var(--a-text)]">{item.reason}</div>
                          <div className="mt-0.5 text-[11px] font-semibold leading-[1.5] text-[var(--a-brand)]">{item.action}</div>
                        </div>
                      ))}
                      {review.action_items.length === 0 && <DataState state="EMPTY" title="Sin acciones críticas" detail="El cierre no reporta pendientes que bloqueen el periodo." />}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="mt-6">
                <DataState
                  state="EMPTY"
                  title="Sin cierre de periodo"
                  detail="Aún no hay un MonthlyReview disponible. El resto de Plan sigue operativo con sus datos propios."
                />
              </div>
            )}
          </section>

          {/* --------------------------------------------------------------
              3 · Workspace operativo — presupuesto y caja
          -------------------------------------------------------------- */}
          <section className="a-surface mt-5 p-5" aria-labelledby="plan-workspace-title">
            <div className="a-page-kicker" id="plan-workspace-title">Workspace operativo</div>
            <p className="a-meta mt-1">Presupuesto del periodo y caja de corto plazo.</p>

            <div className="mt-5 grid gap-6 lg:grid-cols-2">
              {/* Presupuestos */}
              <div className="min-w-0">
                <h3 className="a-module-title">Presupuestos</h3>

                <div className="mt-4 grid grid-cols-2 gap-2">
                  <input className={inputClass} list="budget-categories" placeholder="Categoría" aria-label="Categoría del presupuesto" value={budgetForm.category || ''} onChange={(e) => setBudgetForm({ ...budgetForm, category: e.target.value })} />
                  <input className={inputClass} type="number" placeholder="Importe" aria-label="Límite mensual del presupuesto" value={budgetForm.monthly_limit ?? 0} onChange={(e) => setBudgetForm({ ...budgetForm, monthly_limit: Number(e.target.value) })} />
                  <input className={inputClass} placeholder="Moneda" aria-label="Moneda del presupuesto" value={budgetForm.currency || 'USD'} onChange={(e) => setBudgetForm({ ...budgetForm, currency: e.target.value.toUpperCase() })} />
                  <select className={inputClass} aria-label="Periodo del presupuesto" value={budgetForm.period || 'MONTHLY'} onChange={(e) => setBudgetForm({ ...budgetForm, period: e.target.value })}>
                    <option value="MONTHLY">Mensual</option>
                    <option value="WEEKLY">Semanal</option>
                    <option value="YEARLY">Anual</option>
                  </select>
                </div>
                <datalist id="budget-categories">{categories.map((c) => <option key={c.id} value={c.name} />)}</datalist>

                <label className="mt-3 flex items-center gap-2 text-xs text-[var(--a-secondary)]">
                  <input type="checkbox" checked={Boolean(budgetForm.is_active)} onChange={(e) => setBudgetForm({ ...budgetForm, is_active: e.target.checked })} />
                  Activo
                </label>

                <button type="button" onClick={submitBudget} className={`${btnRun} mt-3`}>Guardar presupuesto</button>

                <div className="mt-4 max-h-72 space-y-2 overflow-auto">
                  {budgets.map((budget) => (
                    <div key={budget.id} className={`${tileClass} flex items-center justify-between gap-2`}>
                      <button type="button" className="min-w-0 flex-1 text-left text-xs" onClick={() => setBudgetForm(budget)}>
                        <span className="font-semibold text-[var(--a-text)]">{budget.category}</span>
                        <span className="a-meta"> · {money(budget.monthly_limit)} {budget.currency} · {budget.source}</span>
                      </button>
                      <button type="button" onClick={() => onDeleteBudget(budget.id)} aria-label={`Eliminar presupuesto ${budget.category}`} className="shrink-0 text-xs font-semibold text-[var(--a-negative)] transition-colors hover:text-[var(--a-negative)]">
                        Eliminar
                      </button>
                    </div>
                  ))}
                  {budgets.length === 0 && <DataState state="EMPTY" title="Sin presupuestos guardados" detail="Crea el primer presupuesto con el formulario anterior." />}
                </div>
              </div>

              {/* Caja corto plazo */}
              <div className="min-w-0 lg:border-l lg:border-[var(--a-line)] lg:pl-6">
                <h3 className="a-module-title">Caja corto plazo</h3>

                <div className="mt-4 grid grid-cols-2 gap-2">
                  <input className={inputClass} placeholder="Moneda" aria-label="Moneda de la proyección de caja" value={cashForm.currency} onChange={(e) => setCashValue('currency', e.target.value.toUpperCase())} />
                  <input className={inputClass} type="number" placeholder="Horizonte días" aria-label="Horizonte en días" value={cashForm.horizon_days} onChange={(e) => setCashValue('horizon_days', Number(e.target.value))} />
                  <input className={inputClass} type="number" placeholder="Balance inicial" aria-label="Balance inicial" value={cashForm.starting_balance} onChange={(e) => setCashValue('starting_balance', Number(e.target.value))} />
                  <input className={inputClass} type="number" placeholder="Reserva mínima" aria-label="Reserva mínima" value={cashForm.reserve_floor} onChange={(e) => setCashValue('reserve_floor', Number(e.target.value))} />
                  <input className={inputClass} type="number" placeholder="Gasto esencial mensual" aria-label="Gasto esencial mensual" value={cashForm.essential_monthly_expenses} onChange={(e) => setCashValue('essential_monthly_expenses', Number(e.target.value))} />
                </div>

                <button type="button" onClick={runCashIntelligence} className={`${btnRun} mt-3`}>Calcular caja</button>
                {cashError && <div role="alert" className={`${errorClass} mt-3`}>{cashError}</div>}

                <div className="mt-4 grid grid-cols-1 gap-2 text-xs sm:grid-cols-3" role="status" aria-live="polite">
                  <div className={tileClass}>
                    <div className="a-meta">Balance con eventos</div>
                    <div className="mt-1 font-bold tabular-nums text-[var(--a-text)]">{cashProjection?.balance_after_known_events == null ? 'N/A' : `${money(cashProjection.balance_after_known_events)} ${cashProjection.currency}`}</div>
                    <div className="a-meta mt-0.5">{cashProjection?.status || 'Sin cálculo'}</div>
                  </div>
                  <div className={tileClass}>
                    <div className="a-meta">Proyectado</div>
                    <div className="mt-1 font-bold tabular-nums text-[var(--a-text)]">{cashProjection?.projected_balance == null ? 'No disponible' : `${money(cashProjection.projected_balance)} ${cashProjection.currency}`}</div>
                    <div className="a-meta mt-0.5">Confianza {cashProjection?.confidence || 'N/A'}</div>
                  </div>
                  <div className={tileClass}>
                    <div className="a-meta">Safe-to-Spend</div>
                    <div className="mt-1 font-bold tabular-nums text-[var(--a-text)]">{safeResult?.safe_to_spend == null ? 'No evaluable' : `${money(safeResult.safe_to_spend)} ${safeResult.currency}`}</div>
                    <div className="a-meta mt-0.5">Runway {runwayResult?.coverage_months == null ? 'N/A' : `${runwayResult.coverage_months.toFixed(1)} meses`}</div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* --------------------------------------------------------------
              4 · Herramientas secundarias — huidas deliberadamente
          -------------------------------------------------------------- */}
          <section className="mt-5 rounded-[var(--a-radius)] border border-[var(--a-line)] bg-black/10 p-5" aria-labelledby="plan-tools-title">
            <div className="a-page-kicker" id="plan-tools-title">Herramientas secundarias</div>
            <p className="a-meta mt-1">Escenarios comparados y calculadoras puntuales.</p>

            <div className="mt-5 grid gap-6 lg:grid-cols-2">
              {/* Scenario Lab */}
              <div className="min-w-0">
                <h3 className="a-module-title">Scenario Lab</h3>

                <div className="mt-4 grid grid-cols-2 gap-2">
                  <select className={inputClass} aria-label="Tipo de escenario" value={scenarioType} onChange={(e) => { setScenarioType(e.target.value as ScenarioType); setScenarioResult(null); }}>
                    <option value="CASH">Caja</option>
                    <option value="DEBT">Deuda</option>
                    <option value="GOAL">Meta</option>
                  </select>
                  <input className={inputClass} placeholder="Moneda" aria-label="Moneda del escenario" value={scenarioForm.currency} onChange={(e) => setScenarioValue('currency', e.target.value.toUpperCase())} />
                  {scenarioType === 'CASH' && <>
                    <input className={inputClass} type="number" placeholder="Balance inicial" aria-label="Balance inicial del escenario" value={scenarioForm.starting_balance} onChange={(e) => setScenarioValue('starting_balance', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Reserva" aria-label="Reserva del escenario" value={scenarioForm.reserve_floor} onChange={(e) => setScenarioValue('reserve_floor', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Horizonte días" aria-label="Horizonte del escenario en días" value={scenarioForm.horizon_days} onChange={(e) => setScenarioValue('horizon_days', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Cambio gasto semanal" aria-label="Cambio de gasto semanal en el escenario" value={scenarioForm.weekly_variable_spend_delta} onChange={(e) => setScenarioValue('weekly_variable_spend_delta', Number(e.target.value))} />
                  </>}
                  {scenarioType === 'DEBT' && <>
                    <input className={inputClass} type="number" placeholder="Saldo deuda" aria-label="Saldo de la deuda" value={scenarioForm.balance} onChange={(e) => setScenarioValue('balance', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Pago mensual" aria-label="Pago mensual" value={scenarioForm.monthly_payment} onChange={(e) => setScenarioValue('monthly_payment', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Pago extra" aria-label="Pago extra" value={scenarioForm.extra_payment} onChange={(e) => setScenarioValue('extra_payment', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Tasa % E.A." aria-label="Tasa efectiva anual porcentual" value={scenarioForm.annual_effective_rate_pct} onChange={(e) => setScenarioValue('annual_effective_rate_pct', Number(e.target.value))} />
                  </>}
                  {scenarioType === 'GOAL' && <>
                    <input className={inputClass} type="number" placeholder="Actual" aria-label="Monto actual de la meta" value={scenarioForm.current_amount} onChange={(e) => setScenarioValue('current_amount', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Meta" aria-label="Monto objetivo de la meta" value={scenarioForm.target_amount} onChange={(e) => setScenarioValue('target_amount', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Aporte actual" aria-label="Aporte mensual actual" value={scenarioForm.monthly_contribution} onChange={(e) => setScenarioValue('monthly_contribution', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Aporte escenario" aria-label="Aporte mensual del escenario" value={scenarioForm.monthly_contribution_override} onChange={(e) => setScenarioValue('monthly_contribution_override', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Periodos" aria-label="Periodos de la meta" value={scenarioForm.periods} onChange={(e) => setScenarioValue('periods', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Tasa % E.A." aria-label="Tasa efectiva anual porcentual" value={scenarioForm.annual_effective_rate_pct} onChange={(e) => setScenarioValue('annual_effective_rate_pct', Number(e.target.value))} />
                  </>}
                </div>

                <button type="button" onClick={runScenario} className={`${btnRun} mt-3`}>Evaluar escenario</button>
                {scenarioError && <div role="alert" className={`${errorClass} mt-3`}>{scenarioError}</div>}

                <div className="mt-4" role="status" aria-live="polite">
                  {(() => {
                    const metric = scenarioMainMetric();
                    if (!metric) return <DataState state="EMPTY" title="Sin escenario todavía" detail="Evalúa un escenario para comparar la referencia contra el resultado." />;
                    return (
                      <>
                        <div className="grid grid-cols-3 gap-2 text-xs">
                          <div className={tileClass}>
                            <div className="a-meta">Referencia</div>
                            <div className="mt-1 font-bold tabular-nums text-[var(--a-text)]">{metric.baseline == null ? 'N/A' : `${money(Number(metric.baseline))} ${metric.currency}`}</div>
                          </div>
                          <div className={tileClass}>
                            <div className="a-meta">Escenario</div>
                            <div className="mt-1 font-bold tabular-nums text-[var(--a-text)]">{metric.scenario == null ? 'N/A' : `${money(Number(metric.scenario))} ${metric.currency}`}</div>
                          </div>
                          <div className={tileClass}>
                            <div className="a-meta">Delta</div>
                            <div className="mt-1 font-bold tabular-nums text-[var(--a-analytical)]">{metric.delta == null ? 'N/A' : `${money(Number(metric.delta))} ${metric.currency}`}</div>
                          </div>
                        </div>
                        <p className="a-meta mt-2">Estado {scenarioResult?.status} · métricas: {(scenarioResult?.affected_metrics || []).join(', ') || 'N/A'}</p>
                      </>
                    );
                  })()}
                </div>
              </div>

              {/* Calculadoras */}
              <div className="min-w-0 lg:border-l lg:border-[var(--a-line)] lg:pl-6">
                <h3 className="a-module-title">Calculadoras</h3>

                <select className={`${inputClass} mt-4`} aria-label="Calculadora seleccionada" value={calculatorKind} onChange={(e) => { setCalculatorKind(e.target.value as CalculatorKind); setCalcResult(null); }}>
                  <option value="savings-goal">Meta de ahorro</option>
                  <option value="compound">Interés compuesto / DCA</option>
                  <option value="emergency-fund">Fondo de emergencia</option>
                  <option value="debt-payoff">Pago de deuda</option>
                  <option value="opportunity-cost">Costo de oportunidad</option>
                </select>

                <div className="mt-2 grid grid-cols-2 gap-2">
                  <input className={inputClass} placeholder="Moneda" aria-label="Moneda del cálculo" value={calcForm.currency} onChange={(e) => setCalcValue('currency', e.target.value.toUpperCase())} />
                  {calculatorKind === 'savings-goal' && <>
                    <input className={inputClass} type="number" placeholder="Meta" aria-label="Meta de ahorro" value={calcForm.target} onChange={(e) => setCalcValue('target', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Actual" aria-label="Ahorro actual" value={calcForm.current_amount} onChange={(e) => setCalcValue('current_amount', Number(e.target.value))} />
                  </>}
                  {calculatorKind === 'compound' && <>
                    <input className={inputClass} type="number" placeholder="Principal" aria-label="Principal del interés compuesto" value={calcForm.principal} onChange={(e) => setCalcValue('principal', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Aporte periódico" aria-label="Aporte periódico" value={calcForm.periodic_contribution} onChange={(e) => setCalcValue('periodic_contribution', Number(e.target.value))} />
                  </>}
                  {calculatorKind === 'emergency-fund' && <>
                    <input className={inputClass} type="number" placeholder="Recursos líquidos" aria-label="Recursos líquidos" value={calcForm.liquid_resources} onChange={(e) => setCalcValue('liquid_resources', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Gastos esenciales/mes" aria-label="Gastos esenciales por mes" value={calcForm.essential_monthly_expenses} onChange={(e) => setCalcValue('essential_monthly_expenses', Number(e.target.value))} />
                  </>}
                  {calculatorKind === 'debt-payoff' && <>
                    <input className={inputClass} type="number" placeholder="Saldo deuda" aria-label="Saldo de la deuda" value={calcForm.balance} onChange={(e) => setCalcValue('balance', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Pago mensual" aria-label="Pago mensual de la deuda" value={calcForm.monthly_payment} onChange={(e) => setCalcValue('monthly_payment', Number(e.target.value))} />
                    <input className={inputClass} type="number" placeholder="Pago extra" aria-label="Pago extra de la deuda" value={calcForm.extra_payment} onChange={(e) => setCalcValue('extra_payment', Number(e.target.value))} />
                  </>}
                  {calculatorKind === 'opportunity-cost' && <input className={inputClass} type="number" placeholder="Monto" aria-label="Monto para costo de oportunidad" value={calcForm.amount} onChange={(e) => setCalcValue('amount', Number(e.target.value))} />}
                  {calculatorKind !== 'emergency-fund' && <>
                    <input className={inputClass} type="number" placeholder="Tasa % E.A." aria-label="Tasa efectiva anual porcentual" value={calcForm.annual_effective_rate_pct} onChange={(e) => setCalcValue('annual_effective_rate_pct', Number(e.target.value))} />
                    {calculatorKind !== 'debt-payoff' && <input className={inputClass} type="number" placeholder="Periodos" aria-label="Periodos del cálculo" value={calcForm.periods} onChange={(e) => setCalcValue('periods', Number(e.target.value))} />}
                  </>}
                </div>

                <button type="button" onClick={runSelectedCalculator} className={`${btnRun} mt-3`}>Calcular</button>
                {calcError && <div role="alert" className={`${errorClass} mt-3`}>{calcError}</div>}

                <div className={`${tileClass} mt-4`} role="status" aria-live="polite">
                  {renderCalculatorResult()}
                </div>
                {calcResult?.assumptions && <div className="a-meta mt-2">Supuestos: tasa efectiva anual, sin FX, moneda única del cálculo.</div>}
              </div>
            </div>
          </section>
        </section>

        {/* ================================================================= */}
        {/* RAIL: atención / próximo                                           */}
        {/* ================================================================= */}
        <aside className="a-surface h-fit p-5" aria-labelledby="plan-attention-title">
          <div className="a-page-kicker" id="plan-attention-title">Atención / próximo</div>
          <p className="a-meta mt-1">Agenda financiera y candidatos recurrentes detectados.</p>

          {/* Agenda financiera */}
          <div className="mt-5">
            <h3 className="a-module-title">Agenda financiera</h3>

            {financialEvents.length === 0 ? (
              <div className="mt-3">
                <DataState state="EMPTY" title="Sin eventos esperados" detail="No hay eventos recurrentes ni comprometidos en el horizonte configurado." />
              </div>
            ) : (
              <div className="mt-3">
                {(['TODAY', 'NEXT_7_DAYS', 'LATER'] as const).map((group) => (
                  <div key={group} className="mb-4 last:mb-0">
                    <div className="a-meta font-bold">{group === 'TODAY' ? 'Hoy' : group === 'NEXT_7_DAYS' ? 'Próximos 7 días' : 'Después'}</div>
                    <div className="mt-1">
                      {eventGroups[group].slice(0, 6).map((event) => (
                        <div key={event.id} className={rowClass}>
                          <span className="min-w-0">
                            <span className="block truncate text-xs font-semibold text-[var(--a-text)]">{event.label}</span>
                            <span className="a-meta">{event.date} · {event.certainty} · {event.confidence}</span>
                          </span>
                          <span className={`shrink-0 text-xs font-bold tabular-nums ${event.direction === 'INFLOW' ? 'text-[var(--a-positive)]' : 'text-[var(--a-negative)]'}`}>
                            {money(event.amount)} {event.currency}
                          </span>
                        </div>
                      ))}
                      {eventGroups[group].length === 0 && <p className="a-meta pb-1">Sin eventos esperados.</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="my-5 h-px bg-[var(--a-line)]" />

          {/* Recurrentes */}
          <div>
            <h3 className="a-module-title">Recurrentes</h3>

            <div className="mt-3 max-h-96 space-y-2 overflow-auto">
              {recurring.map((item) => (
                <div key={item.id} className={`${tileClass} space-y-2`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-xs font-bold text-[var(--a-text)]">{item.merchant}</div>
                      <div className="a-meta mt-0.5">{item.frequency} · {item.category} · {money(item.typical_amount)}</div>
                    </div>
                    <span className="shrink-0 rounded-full border border-[var(--a-line)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">
                      {item.status}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => onUpdateRecurring(item.id, 'confirmed')} className={btnPositive}>Confirmar</button>
                    <button type="button" onClick={() => onUpdateRecurring(item.id, 'rejected')} className={btnNegative}>Rechazar</button>
                    <button type="button" onClick={() => onUpdateRecurring(item.id, 'ignored')} className={btnQuiet}>Ignorar</button>
                  </div>
                </div>
              ))}
              {recurring.length === 0 && <DataState state="EMPTY" title="Sin candidatos recurrentes" detail="Todavía no se detectaron movimientos repetidos en las transacciones." />}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};
