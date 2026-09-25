import React, { useRef, useState } from 'react';
import { Budget, CalculatorKind, CalculatorResult, CashProjectionResult, Category, FinancialEvent, MonthlyReview, RecurringRule, SafeToSpendResult, ScenarioEvaluationResult, ScenarioType } from '../../types';
import { DataState, DeltaDirection, InlineMetric } from '../../aetheris/primitives';
import { Button, Field, MetricInput, MoneyField, SegmentedControl } from '../../aetheris/controls';
import { ToolSurfaceDock } from '../../aetheris/ToolSurfaceDock';

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

const selectClass =
  'min-h-10 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] focus:border-[var(--a-brand)] focus:outline-none';

const tileClass = 'rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3';
const errorClass = 'rounded-[var(--a-radius-sm)] border border-[var(--a-line-strong)] bg-[var(--a-canvas)] p-3 text-xs text-[var(--a-negative)]';
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
  const [openTool, setOpenTool] = useState<'scenario' | 'calculator' | null>(null);
  const scenarioLauncherRef = useRef<HTMLButtonElement>(null);
  const calculatorLauncherRef = useRef<HTMLButtonElement>(null);
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
      <div className={openTool ? 'grid gap-[var(--a-stack)] min-[1041px]:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]' : 'a-workspace mt-0'}>
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
                <p className="a-meta mt-1">Hechos del periodo, desviaciones, obligaciones próximas y acciones sugeridas.</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                {review && (
                  <span className="hidden rounded-full border border-[var(--a-line)] px-3 py-1 text-[11px] font-bold text-[var(--a-secondary)] md:inline-block">
                    {review.period}
                  </span>
                )}
                <Button variant="primary" onClick={onSaveSnapshot}>Guardar cierre mensual</Button>
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
                    <h3 className="a-page-kicker">Desviaciones</h3>

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
                    <h3 className="a-page-kicker">Próximos pagos</h3>
                    <div className="mt-4">
                      {review.upcoming_obligations.slice(0, 6).map((item, index) => (
                        <div key={`${item.merchant}-${item.date}-${index}`} className={rowClass}>
                          <span className="min-w-0 truncate text-xs text-[var(--a-secondary)]">{item.merchant}</span>
                          <span className="shrink-0 text-xs tabular-nums text-[var(--a-text)]">{item.date} · {money(item.amount)}</span>
                        </div>
                      ))}
                      {review.upcoming_obligations.length === 0 && <DataState state="EMPTY" title="Sin obligaciones próximas" detail="El backend no confirmó pagos con fecha dentro del horizonte." />}
                    </div>
                  </div>

                  <div className={colDivider}>
                    <h3 className="a-page-kicker">Acciones</h3>
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

          <section className="a-surface mt-5 p-4" aria-labelledby="plan-tool-launcher-title">
            <h2 id="plan-tool-launcher-title" className="a-module-title">Herramientas bajo demanda</h2>
            <p className="a-meta mt-1">Abre un instrumento sin perder el contexto de presupuesto, caja y atención.</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Button
                ref={scenarioLauncherRef}
                variant={openTool === 'scenario' ? 'operational' : 'quiet'}
                aria-pressed={openTool === 'scenario'}
                aria-controls="plan-scenario-dock"
                onClick={() => setOpenTool((current) => current === 'scenario' ? null : 'scenario')}
                className="h-auto min-h-11 justify-start text-left"
              >
                Scenario Lab · comparar decisiones
              </Button>
              <Button
                ref={calculatorLauncherRef}
                variant={openTool === 'calculator' ? 'operational' : 'quiet'}
                aria-pressed={openTool === 'calculator'}
                aria-controls="plan-calculator-dock"
                onClick={() => setOpenTool((current) => current === 'calculator' ? null : 'calculator')}
                className="h-auto min-h-11 justify-start text-left"
              >
                Calculadoras · resolver una pregunta
              </Button>
            </div>
          </section>

          {/* --------------------------------------------------------------
              3 · Workspace operativo — presupuesto y caja
          -------------------------------------------------------------- */}
          <section className="a-surface mt-5 p-5" aria-labelledby="plan-workspace-title">
            <h2 className="a-page-kicker" id="plan-workspace-title">Workspace operativo</h2>
            <p className="a-meta mt-1">Presupuesto del periodo y caja de corto plazo.</p>

            <div className="mt-5 grid gap-6 lg:grid-cols-2">
              {/* Presupuestos */}
              <div className="min-w-0">
                <h3 className="a-module-title">Presupuestos</h3>

                <div className="mt-4 grid gap-4">
                  <Field id="budget-category" label="Rubro" list="budget-categories" placeholder="Alimentación" value={budgetForm.category || ''} onChange={(value) => setBudgetForm({ ...budgetForm, category: value })} />
                  <MoneyField id="budget-limit" label="Límite" currency={budgetForm.currency || 'USD'} value={Number(budgetForm.monthly_limit ?? 0)} onChange={(value) => setBudgetForm({ ...budgetForm, monthly_limit: value })} />
                  <Field id="budget-currency" label="Moneda" placeholder="USD" value={budgetForm.currency || 'USD'} onChange={(value) => setBudgetForm({ ...budgetForm, currency: value.toUpperCase() })} />
                  <SegmentedControl
                    label="Periodo"
                    value={(budgetForm.period || 'MONTHLY') as 'MONTHLY' | 'WEEKLY' | 'YEARLY'}
                    options={[
                      { value: 'MONTHLY', label: 'Mensual' },
                      { value: 'WEEKLY', label: 'Semanal' },
                      { value: 'YEARLY', label: 'Anual' },
                    ]}
                    onChange={(value) => setBudgetForm({ ...budgetForm, period: value })}
                  />
                </div>
                <datalist id="budget-categories">{categories.map((c) => <option key={c.id} value={c.name} />)}</datalist>

                <label className="mt-3 flex items-center gap-2 text-xs text-[var(--a-secondary)]">
                  <input type="checkbox" checked={Boolean(budgetForm.is_active)} onChange={(e) => setBudgetForm({ ...budgetForm, is_active: e.target.checked })} />
                  Activo
                </label>

                <Button variant="operational" onClick={submitBudget} className="mt-4 w-full">Guardar presupuesto</Button>

                <div className="mt-4 max-h-72 space-y-2 overflow-auto">
                  {budgets.map((budget) => (
                    <div key={budget.id} className={`${tileClass} flex items-center justify-between gap-3`}>
                      <button type="button" className="min-w-0 flex-1 text-left text-xs" onClick={() => setBudgetForm(budget)}>
                        <span className="block font-semibold text-[var(--a-text)]">{budget.category}</span>
                        <span className="a-meta mt-1 block">{money(budget.monthly_limit)} {budget.currency} · {budget.period} · {budget.is_active ? 'Activo' : 'Inactivo'} · {budget.source}</span>
                      </button>
                      <Button variant="negative" onClick={() => onDeleteBudget(budget.id)} aria-label={`Eliminar presupuesto ${budget.category}`} className="shrink-0">Eliminar</Button>
                    </div>
                  ))}
                  {budgets.length === 0 && <DataState state="EMPTY" title="Sin presupuestos guardados" detail="Crea el primer presupuesto con el formulario anterior." />}
                </div>
              </div>

              {/* Caja corto plazo */}
              <div className="min-w-0 lg:border-l lg:border-[var(--a-line)] lg:pl-6">
                <h3 className="a-module-title">Caja corto plazo</h3>

                <div className="mt-4 grid gap-4">
                  <Field id="cash-currency" label="Moneda" value={String(cashForm.currency)} onChange={(value) => setCashValue('currency', value.toUpperCase())} />
                  <MetricInput id="cash-horizon" label="Horizonte" unit="días" value={Number(cashForm.horizon_days)} min={1} step={1} onChange={(value) => setCashValue('horizon_days', value)} />
                  <MoneyField id="cash-starting-balance" label="Disponible hoy" currency={String(cashForm.currency)} value={Number(cashForm.starting_balance)} onChange={(value) => setCashValue('starting_balance', value)} />
                  <MoneyField id="cash-reserve" label="Reserva protegida" currency={String(cashForm.currency)} value={Number(cashForm.reserve_floor)} hint="Cantidad que no se considera disponible para gasto." onChange={(value) => setCashValue('reserve_floor', value)} />
                  <MoneyField id="cash-essential-expenses" label="Costo de vida base" currency={String(cashForm.currency)} value={Number(cashForm.essential_monthly_expenses)} onChange={(value) => setCashValue('essential_monthly_expenses', value)} />
                </div>

                <Button variant="operational" onClick={runCashIntelligence} className="mt-4 w-full">Calcular proyección</Button>
                {cashError && <div role="alert" className={`${errorClass} mt-3`}>{cashError}</div>}

                <div className="mt-4" role="status" aria-live="polite">
                  {!cashProjection && !safeResult && !runwayResult ? (
                    <DataState state="EMPTY" title="Sin cálculo de caja" detail="Configura el horizonte y la reserva para calcular cierre, gasto seguro y runway." />
                  ) : (
                    <div className="a-elevated p-4">
                      <div className="grid gap-4 sm:grid-cols-3">
                        <InlineMetric label="Cierre proyectado" value={cashProjection?.projected_balance == null ? 'No disponible' : `${money(cashProjection.projected_balance)} ${cashProjection.currency}`} direction="analytical" />
                        <InlineMetric label="Safe-to-Spend" value={safeResult?.safe_to_spend == null ? 'No evaluable' : `${money(safeResult.safe_to_spend)} ${safeResult.currency}`} direction={safeResult?.safe_to_spend == null ? 'neutral' : signDirection(safeResult.safe_to_spend)} />
                        <InlineMetric label="Runway" value={runwayResult?.coverage_months == null ? 'N/A' : `${runwayResult.coverage_months.toFixed(1)} meses`} direction="neutral" />
                      </div>
                      <p className="a-meta mt-3">Balance con eventos: {cashProjection?.balance_after_known_events == null ? 'N/A' : `${money(cashProjection.balance_after_known_events)} ${cashProjection.currency}`} · Estado {cashProjection?.status || 'No disponible'} · Confianza {cashProjection?.confidence || 'N/A'}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>

        </section>

        {openTool === 'scenario' && (
          <ToolSurfaceDock id="plan-scenario-dock" title="Scenario Lab" description="Compara una referencia real contra un supuesto controlado." triggerRef={scenarioLauncherRef} onClose={() => setOpenTool(null)}>
            <div className="space-y-5">
              <section aria-labelledby="scenario-assumptions-title">
                <h3 id="scenario-assumptions-title" className="a-module-title">Supuestos</h3>
                <div className="mt-3 space-y-4">
                  <SegmentedControl label="Tipo" value={scenarioType} options={[{ value: 'CASH', label: 'Caja' }, { value: 'DEBT', label: 'Deuda' }, { value: 'GOAL', label: 'Meta' }]} onChange={(value) => { setScenarioType(value); setScenarioResult(null); }} />
                  <Field id="scenario-currency" label="Moneda" value={String(scenarioForm.currency)} onChange={(value) => setScenarioValue('currency', value.toUpperCase())} />
                  {scenarioType === 'CASH' && <>
                    <MoneyField id="scenario-starting-balance" label="Balance inicial" currency={String(scenarioForm.currency)} value={Number(scenarioForm.starting_balance)} onChange={(value) => setScenarioValue('starting_balance', value)} />
                    <MoneyField id="scenario-reserve" label="Reserva" currency={String(scenarioForm.currency)} value={Number(scenarioForm.reserve_floor)} onChange={(value) => setScenarioValue('reserve_floor', value)} />
                    <MetricInput id="scenario-horizon" label="Horizonte" unit="días" value={Number(scenarioForm.horizon_days)} min={1} step={1} onChange={(value) => setScenarioValue('horizon_days', value)} />
                    <MoneyField id="scenario-weekly-delta" label="Cambio de gasto semanal" currency={String(scenarioForm.currency)} value={Number(scenarioForm.weekly_variable_spend_delta)} allowNegative onChange={(value) => setScenarioValue('weekly_variable_spend_delta', value)} />
                  </>}
                  {scenarioType === 'DEBT' && <>
                    <MoneyField id="scenario-debt-balance" label="Saldo de deuda" currency={String(scenarioForm.currency)} value={Number(scenarioForm.balance)} onChange={(value) => setScenarioValue('balance', value)} />
                    <MoneyField id="scenario-monthly-payment" label="Pago mensual" currency={String(scenarioForm.currency)} value={Number(scenarioForm.monthly_payment)} onChange={(value) => setScenarioValue('monthly_payment', value)} />
                    <MoneyField id="scenario-extra-payment" label="Pago extra" currency={String(scenarioForm.currency)} value={Number(scenarioForm.extra_payment)} onChange={(value) => setScenarioValue('extra_payment', value)} />
                    <MetricInput id="scenario-debt-rate" label="Tasa efectiva anual" unit="% E.A." value={Number(scenarioForm.annual_effective_rate_pct)} min={0} step={0.01} onChange={(value) => setScenarioValue('annual_effective_rate_pct', value)} />
                  </>}
                  {scenarioType === 'GOAL' && <>
                    <MoneyField id="scenario-goal-current" label="Monto actual" currency={String(scenarioForm.currency)} value={Number(scenarioForm.current_amount)} onChange={(value) => setScenarioValue('current_amount', value)} />
                    <MoneyField id="scenario-goal-target" label="Meta" currency={String(scenarioForm.currency)} value={Number(scenarioForm.target_amount)} onChange={(value) => setScenarioValue('target_amount', value)} />
                    <MoneyField id="scenario-goal-contribution" label="Aporte actual" currency={String(scenarioForm.currency)} value={Number(scenarioForm.monthly_contribution)} onChange={(value) => setScenarioValue('monthly_contribution', value)} />
                    <MoneyField id="scenario-goal-override" label="Aporte del escenario" currency={String(scenarioForm.currency)} value={Number(scenarioForm.monthly_contribution_override)} onChange={(value) => setScenarioValue('monthly_contribution_override', value)} />
                    <MetricInput id="scenario-goal-periods" label="Periodos" unit="meses" value={Number(scenarioForm.periods)} min={1} step={1} onChange={(value) => setScenarioValue('periods', value)} />
                    <MetricInput id="scenario-goal-rate" label="Tasa efectiva anual" unit="% E.A." value={Number(scenarioForm.annual_effective_rate_pct)} min={0} step={0.01} onChange={(value) => setScenarioValue('annual_effective_rate_pct', value)} />
                  </>}
                </div>
                <Button variant="operational" onClick={runScenario} className="mt-5 w-full">Evaluar escenario</Button>
                {scenarioError && <div role="alert" className={`${errorClass} mt-3`}>{scenarioError}</div>}
              </section>
              <section aria-labelledby="scenario-result-title" role="status" aria-live="polite">
                <h3 id="scenario-result-title" className="a-module-title">Resultado</h3>
                <div className="mt-3">
                  {(() => {
                    const metric = scenarioMainMetric();
                    if (!metric) return <DataState state="EMPTY" title="Sin escenario todavía" detail="Evalúa los supuestos para comparar referencia, escenario y delta." />;
                    return (
                      <div className="a-elevated space-y-4 p-4">
                        <InlineMetric label={`Referencia · ${metric.label}`} value={metric.baseline == null ? 'N/A' : `${money(Number(metric.baseline))} ${metric.currency}`} direction="neutral" />
                        <InlineMetric label={`Escenario · ${metric.label}`} value={metric.scenario == null ? 'N/A' : `${money(Number(metric.scenario))} ${metric.currency}`} direction="analytical" />
                        <InlineMetric label="Delta" value={metric.delta == null ? 'N/A' : `${money(Number(metric.delta))} ${metric.currency}`} direction={signDirection(metric.delta)} />
                        <p className="a-meta">Estado {scenarioResult?.status} · métricas: {(scenarioResult?.affected_metrics || []).join(', ') || 'N/A'}</p>
                      </div>
                    );
                  })()}
                </div>
              </section>
            </div>
          </ToolSurfaceDock>
        )}
        {openTool === 'calculator' && (
          <ToolSurfaceDock id="plan-calculator-dock" title="Calculadoras" description="Configura una herramienta puntual y revisa su resultado." triggerRef={calculatorLauncherRef} onClose={() => setOpenTool(null)}>
            <div className="space-y-5">
              <section aria-labelledby="calculator-config-title">
                <h3 id="calculator-config-title" className="a-module-title">Elegir y configurar</h3>
                <div className="mt-3 space-y-4">
                  <div>
                    <label htmlFor="calculator-kind" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Herramienta</label>
                    <select id="calculator-kind" className={selectClass} value={calculatorKind} onChange={(event) => { setCalculatorKind(event.target.value as CalculatorKind); setCalcResult(null); }}>
                      <option value="savings-goal">Meta de ahorro</option>
                      <option value="compound">Interés compuesto / DCA</option>
                      <option value="emergency-fund">Fondo de emergencia</option>
                      <option value="debt-payoff">Pago de deuda</option>
                      <option value="opportunity-cost">Costo de oportunidad</option>
                    </select>
                  </div>
                  <Field id="calculator-currency" label="Moneda" value={String(calcForm.currency)} onChange={(value) => setCalcValue('currency', value.toUpperCase())} />
                  {calculatorKind === 'savings-goal' && <>
                    <MoneyField id="calculator-goal" label="Meta" currency={String(calcForm.currency)} value={Number(calcForm.target)} onChange={(value) => setCalcValue('target', value)} />
                    <MoneyField id="calculator-current" label="Ahorro actual" currency={String(calcForm.currency)} value={Number(calcForm.current_amount)} onChange={(value) => setCalcValue('current_amount', value)} />
                  </>}
                  {calculatorKind === 'compound' && <>
                    <MoneyField id="calculator-principal" label="Principal" currency={String(calcForm.currency)} value={Number(calcForm.principal)} onChange={(value) => setCalcValue('principal', value)} />
                    <MoneyField id="calculator-periodic-contribution" label="Aporte periódico" currency={String(calcForm.currency)} value={Number(calcForm.periodic_contribution)} onChange={(value) => setCalcValue('periodic_contribution', value)} />
                  </>}
                  {calculatorKind === 'emergency-fund' && <>
                    <MoneyField id="calculator-liquid-resources" label="Recursos líquidos" currency={String(calcForm.currency)} value={Number(calcForm.liquid_resources)} onChange={(value) => setCalcValue('liquid_resources', value)} />
                    <MoneyField id="calculator-essential-expenses" label="Gastos esenciales por mes" currency={String(calcForm.currency)} value={Number(calcForm.essential_monthly_expenses)} onChange={(value) => setCalcValue('essential_monthly_expenses', value)} />
                  </>}
                  {calculatorKind === 'debt-payoff' && <>
                    <MoneyField id="calculator-debt-balance" label="Saldo de deuda" currency={String(calcForm.currency)} value={Number(calcForm.balance)} onChange={(value) => setCalcValue('balance', value)} />
                    <MoneyField id="calculator-debt-payment" label="Pago mensual" currency={String(calcForm.currency)} value={Number(calcForm.monthly_payment)} onChange={(value) => setCalcValue('monthly_payment', value)} />
                    <MoneyField id="calculator-extra-payment" label="Pago extra" currency={String(calcForm.currency)} value={Number(calcForm.extra_payment)} onChange={(value) => setCalcValue('extra_payment', value)} />
                  </>}
                  {calculatorKind === 'opportunity-cost' && <MoneyField id="calculator-amount" label="Monto" currency={String(calcForm.currency)} value={Number(calcForm.amount)} onChange={(value) => setCalcValue('amount', value)} />}
                  {calculatorKind !== 'emergency-fund' && <>
                    <MetricInput id="calculator-rate" label="Tasa efectiva anual" unit="% E.A." value={Number(calcForm.annual_effective_rate_pct)} min={0} step={0.01} onChange={(value) => setCalcValue('annual_effective_rate_pct', value)} />
                    {calculatorKind !== 'debt-payoff' && <MetricInput id="calculator-periods" label="Periodos" unit="meses" value={Number(calcForm.periods)} min={1} step={1} onChange={(value) => setCalcValue('periods', value)} />}
                  </>}
                </div>
                <Button variant="operational" onClick={runSelectedCalculator} className="mt-5 w-full">Calcular</Button>
                {calcError && <div role="alert" className={`${errorClass} mt-3`}>{calcError}</div>}
              </section>
              <section aria-labelledby="calculator-result-title" role="status" aria-live="polite">
                <h3 id="calculator-result-title" className="a-module-title">Resultado</h3>
                <div className="a-elevated mt-3 p-4">{renderCalculatorResult()}</div>
                {calcResult?.assumptions && <p className="a-meta mt-2">Supuestos: tasa efectiva anual, sin FX, moneda única del cálculo.</p>}
              </section>
            </div>
          </ToolSurfaceDock>
        )}

        {/* ================================================================= */}
        {/* RAIL: atención / próximo                                           */}
        {/* ================================================================= */}
        <aside className={`a-surface h-fit p-5 ${openTool ? 'min-[1041px]:col-span-2' : ''}`} aria-labelledby="plan-attention-title">
          <h2 className="a-page-kicker" id="plan-attention-title">Atención / próximo</h2>
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
                    <Button variant="positive" onClick={() => onUpdateRecurring(item.id, 'confirmed')}>Confirmar</Button>
                    <Button variant="negative" onClick={() => onUpdateRecurring(item.id, 'rejected')}>Rechazar</Button>
                    <Button variant="quiet" onClick={() => onUpdateRecurring(item.id, 'ignored')}>Ignorar</Button>
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
