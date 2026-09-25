import React, { useEffect, useState } from 'react';
import { Lock, Unlock, CheckCircle2, AlertTriangle, Star, Play } from 'lucide-react';
import { Button, Field, MoneyField } from '../../aetheris/controls';
import { DataState } from '../../aetheris/primitives';
import { ToolSurfaceDock } from '../../aetheris/ToolSurfaceDock';
import { InvestmentThesis, Asset } from '../../types';
import type { InvestTool } from './WealthTab';

interface InvestmentThesisTabProps {
  theses: InvestmentThesis[];
  assets: Asset[];
  onSaveThesis: (thesis: Partial<InvestmentThesis>) => Promise<void>;
  onSimulatePurchase: (ticker: string, amountUsd: number) => Promise<any>;
  selectedTickerForSim?: string;
  openTool: InvestTool | null;
  onOpenTool: (tool: InvestTool | null) => void;
  thesisLauncherRef: React.RefObject<HTMLButtonElement>;
}

export const InvestmentThesisTab: React.FC<InvestmentThesisTabProps> = ({
  theses,
  assets,
  onSaveThesis,
  onSimulatePurchase,
  selectedTickerForSim,
  openTool,
  onOpenTool,
  thesisLauncherRef
}) => {
  // Selección honesta: contexto real si existe; si no, vacío (sin ticker inventado).
  const [selectedTicker, setSelectedTicker] = useState<string>(
    selectedTickerForSim || (theses.length > 0 ? theses[0].ticker : '')
  );

  // Active thesis or empty template
  const currentThesis = theses.find((t) => t.ticker === selectedTicker);

  const [thesisText, setThesisText] = useState<string>(currentThesis?.thesis_text || '');
  const [valuationGrade, setValuationGrade] = useState<number>(currentThesis?.valuation_grade ?? 3);
  const [timingContext, setTimingContext] = useState<string>(currentThesis?.timing_context || '');
  const [safetyMargin, setSafetyMargin] = useState<number>(currentThesis?.safety_margin ?? 20.0);

  const [criteria, setCriteria] = useState<{
    knows_business_model: boolean;
    debt_ebitda_healthy: boolean;
    margin_safety_above_20: boolean;
    timing_not_overbought: boolean;
    emotional_bias_checked: boolean;
  }>({
    knows_business_model: currentThesis?.criteria_details?.knows_business_model ?? false,
    debt_ebitda_healthy: currentThesis?.criteria_details?.debt_ebitda_healthy ?? false,
    margin_safety_above_20: currentThesis?.criteria_details?.margin_safety_above_20 ?? false,
    timing_not_overbought: currentThesis?.criteria_details?.timing_not_overbought ?? false,
    emotional_bias_checked: currentThesis?.criteria_details?.emotional_bias_checked ?? false,
  });

  const [simulationAmount, setSimulationAmount] = useState<number>(0);
  const [simulationResult, setSimulationResult] = useState<any>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Sync state when ticker changes
  const handleTickerChange = (ticker: string) => {
    setSelectedTicker(ticker);
    setSimulationResult(null);
    setSimulationError(null);
    const th = theses.find((t) => t.ticker === ticker);
    if (th) {
      setThesisText(th.thesis_text);
      setValuationGrade(th.valuation_grade);
      setTimingContext(th.timing_context);
      setSafetyMargin(th.safety_margin);
      setCriteria({
        knows_business_model: Boolean(th.criteria_details?.knows_business_model),
        debt_ebitda_healthy: Boolean(th.criteria_details?.debt_ebitda_healthy),
        margin_safety_above_20: Boolean(th.criteria_details?.margin_safety_above_20),
        timing_not_overbought: Boolean(th.criteria_details?.timing_not_overbought),
        emotional_bias_checked: Boolean(th.criteria_details?.emotional_bias_checked),
      });
    } else {
      setThesisText('');
      setValuationGrade(3);
      setTimingContext('');
      setSafetyMargin(20.0);
      setCriteria({
        knows_business_model: false,
        debt_ebitda_healthy: false,
        margin_safety_above_20: false,
        timing_not_overbought: false,
        emotional_bias_checked: false,
      });
    }
  };

  // Lanzamiento contextual: Posiciones/Watchlist/lanzador pueden reseleccionar
  // el ticker mientras el dock está montado.
  useEffect(() => {
    if (selectedTickerForSim && selectedTickerForSim !== selectedTicker) {
      handleTickerChange(selectedTickerForSim);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTickerForSim]);

  // Human safety evaluation logic
  const isAllCriteriaChecked =
    criteria.knows_business_model &&
    criteria.debt_ebitda_healthy &&
    criteria.margin_safety_above_20 &&
    criteria.timing_not_overbought &&
    criteria.emotional_bias_checked;

  const isGuardrailPassed = isAllCriteriaChecked && valuationGrade >= 3 && safetyMargin >= 20.0;

  const handleCheckboxToggle = (key: keyof typeof criteria) => {
    setCriteria((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      return next;
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSaveThesis({
        id: currentThesis?.id,
        ticker: selectedTicker,
        thesis_text: thesisText,
        valuation_grade: valuationGrade,
        timing_context: timingContext,
        safety_margin: safetyMargin,
        checklist_passed: isGuardrailPassed,
        criteria_details: criteria,
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleExecuteSimulation = async () => {
    setSimulationError(null);
    setSimulationResult(null);
    try {
      const res = await onSimulatePurchase(selectedTicker, simulationAmount);
      setSimulationResult(res);
    } catch (err: any) {
      setSimulationError(err.message || 'Error bloqueado por el Filtro Humano.');
    }
  };

  if (openTool !== 'thesis') return null;

  const selectClass = 'min-h-10 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] focus:border-[var(--a-brand)] focus:outline-none';
  const criteriaItems: Array<{ key: keyof typeof criteria; label: React.ReactNode }> = [
    { key: 'knows_business_model', label: <><strong>1. Comprensión del Negocio:</strong> Entiendo cómo monetiza y cuál es su ventaja competitiva (Moat).</> },
    { key: 'debt_ebitda_healthy', label: <><strong>2. Solvencia Financiera:</strong> Ratio Deuda Neta / EBITDA &lt; 3.0x o estructura financiera blindada.</> },
    { key: 'margin_safety_above_20', label: <><strong>3. Margen de Seguridad:</strong> El descuento sobre valor intrínseco estimado supera el 20%.</> },
    { key: 'timing_not_overbought', label: <><strong>4. Timing Técnico:</strong> El precio no se encuentra en euforia parabólica ni sobrecompra extrema.</> },
    { key: 'emotional_bias_checked', label: <><strong>5. Control de Sesgos:</strong> Tesis redactada con frialdad analítica, sin efecto rebaño (FOMO).</> },
  ];

  return (
    <ToolSurfaceDock
      id="invest-thesis-dock"
      title="Tesis de Inversión · Filtro Humano"
      description="Variables cualitativas obligatorias y descarte de sesgos antes de ejecutar compras."
      triggerRef={thesisLauncherRef}
      onClose={() => onOpenTool(null)}
    >
      <div className="space-y-5">
        {/* Selector de activo */}
        <div>
          <label htmlFor="invest-thesis-asset" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Activo</label>
          <select id="invest-thesis-asset" value={selectedTicker} onChange={(e) => handleTickerChange(e.target.value)} className={selectClass}>
            {!selectedTicker && <option value="">Seleccionar activo…</option>}
            {assets.map((a) => (
              <option key={a.ticker} value={a.ticker}>
                {a.ticker} - {a.name}
              </option>
            ))}
          </select>
        </div>

        {!selectedTicker ? (
          <DataState
            state="EMPTY"
            title="Sin activo seleccionado"
            detail="Elige un activo desde Posiciones o desde este selector para definir su tesis."
          />
        ) : (
          <>
            {/* ---------------------------------------------------------- */}
            {/* TESIS cualitativa                                           */}
            {/* ---------------------------------------------------------- */}
            <div className="space-y-4">
              {/* Valuation Grade (1 to 5 Stars) */}
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-[var(--a-secondary)]">Calificación de Valuación (Investing Pro Fair Value)</span>
                  <span className="text-[11px] font-bold text-[var(--a-text)]">
                    {valuationGrade === 5 ? 'Muy Infravalorado' : valuationGrade === 4 ? 'Infravalorado' : valuationGrade === 3 ? 'Valor Justo' : 'Sobrevalorado'}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setValuationGrade(star)}
                      aria-label={`Calificación ${star} de 5`}
                      aria-pressed={star <= valuationGrade}
                      className={`min-h-10 min-w-10 rounded-[var(--a-radius-sm)] border p-2 transition-colors ${
                        star <= valuationGrade
                          ? 'border-[var(--a-brand)] bg-[var(--a-active)] text-[var(--a-brand)]'
                          : 'border-[var(--a-line)] bg-[var(--a-canvas)] text-[var(--a-muted)] hover:bg-[var(--a-elevated)]'
                      }`}
                    >
                      <Star className="h-4 w-4 fill-current" aria-hidden="true" />
                    </button>
                  ))}
                  <span className="ml-1 text-xs tabular-nums text-[var(--a-secondary)]">({valuationGrade}/5)</span>
                </div>
              </div>

              {/* Margin of Safety % */}
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-[var(--a-secondary)]">Margen de Seguridad Deseado (%)</span>
                  <span className={`text-xs font-bold tabular-nums ${safetyMargin >= 20 ? 'text-[var(--a-positive)]' : 'text-[var(--a-negative)]'}`}>
                    {safetyMargin}% {safetyMargin < 20 && '(Mínimo 20% para desbloquear)'}
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="50"
                  step="1"
                  value={safetyMargin}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value);
                    setSafetyMargin(val);
                    setCriteria((prev) => ({ ...prev, margin_safety_above_20: val >= 20 }));
                  }}
                  aria-label="Margen de seguridad deseado"
                  className="mt-2 w-full cursor-pointer accent-[var(--a-brand)]"
                />
              </div>

              {/* Timing Context */}
              <Field
                id="invest-thesis-timing"
                label="Contexto de Timing • Momento Técnico y Macro"
                placeholder="Ej: Consolidación tras corrección en media de 200 periodos; catalizador de resultados."
                value={timingContext}
                onChange={setTimingContext}
              />

              {/* Qualitative Thesis Statement */}
              <div>
                <label htmlFor="invest-thesis-body" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">
                  Cuerpo de la Tesis de Inversión (Hipótesis Fundamental)
                </label>
                <textarea
                  id="invest-thesis-body"
                  rows={3}
                  placeholder="Describa el foso defensivo (Moat), retorno esperado y riesgos del negocio..."
                  value={thesisText}
                  onChange={(e) => setThesisText(e.target.value)}
                  className="min-h-20 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3 text-xs leading-relaxed text-[var(--a-text)] placeholder:text-[var(--a-muted)] focus:border-[var(--a-brand)] focus:outline-none"
                />
              </div>

              {/* Save Button */}
              <div className="flex justify-end pt-1">
                <Button variant="primary" onClick={handleSave} disabled={isSaving}>
                  <span className="inline-flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    {isSaving ? 'Guardando...' : 'Guardar y Certificar Tesis'}
                  </span>
                </Button>
              </div>
            </div>

            {/* ---------------------------------------------------------- */}
            {/* FILTRO HUMANO · guardrail + simulación                      */}
            {/* ---------------------------------------------------------- */}
            <div className="border-t border-[var(--a-line)] pt-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={isGuardrailPassed ? 'text-[var(--a-positive)]' : 'text-[var(--a-negative)]'}>
                    {isGuardrailPassed ? <Unlock className="h-4 w-4" aria-hidden="true" /> : <Lock className="h-4 w-4" aria-hidden="true" />}
                  </span>
                  <div className="min-w-0">
                    <div className="text-xs font-bold uppercase tracking-wider text-[var(--a-text)]">Filtro Humano: {selectedTicker}</div>
                    <div className="a-meta">{isGuardrailPassed ? 'Simulación Habilitada' : 'Operación Estrictamente Bloqueada'}</div>
                  </div>
                </div>
                <span className={`shrink-0 rounded-full border border-[var(--a-line)] bg-[var(--a-canvas)] px-2 py-0.5 text-[10px] font-bold ${isGuardrailPassed ? 'text-[var(--a-positive)]' : 'text-[var(--a-negative)]'}`}>
                  {isGuardrailPassed ? 'DESBLOQUEADO' : 'BLOQUEADO'}
                </span>
              </div>

              {/* 5 Mandatory Checkpoints */}
              <p className="a-meta mt-3">
                Para mitigar riesgos de capital, valide conscientemente los 5 filtros obligatorios:
              </p>
              <div className="mt-2 space-y-2">
                {criteriaItems.map((item) => (
                  <label
                    key={item.key}
                    className="flex cursor-pointer items-start gap-2.5 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2 transition-colors hover:bg-[var(--a-hover)]"
                  >
                    <input
                      type="checkbox"
                      checked={criteria[item.key]}
                      onChange={() => handleCheckboxToggle(item.key)}
                      className="mt-0.5 h-4 w-4 shrink-0 rounded accent-[var(--a-brand)]"
                    />
                    <span className="text-[11px] leading-[1.5] text-[var(--a-secondary)]">{item.label}</span>
                  </label>
                ))}
              </div>

              {/* Guardrail Enforcer & Purchase Simulator */}
              <div className="mt-4 border-t border-[var(--a-line)] pt-4">
                {!isGuardrailPassed ? (
                  <div className="rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3 text-xs text-[var(--a-negative)]">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                      <div>
                        <strong>Guardrail Activo:</strong> La simulación de órdenes de compra está estrictamente deshabilitada. Debe marcar los 5 criterios y asegurar un margen &ge; 20% para desbloquear la ejecución.
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2.5 text-xs text-[var(--a-positive)]">
                      <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span><strong>Filtro Humano Validado:</strong> Simulación de compra autorizada.</span>
                    </div>

                    <MoneyField
                      id="invest-thesis-sim-amount"
                      label="Monto de simulación"
                      value={simulationAmount}
                      onChange={setSimulationAmount}
                      currency="USD"
                    />

                    <Button variant="operational" className="w-full" onClick={handleExecuteSimulation}>
                      <span className="inline-flex items-center gap-1.5">
                        <Play className="h-3.5 w-3.5" aria-hidden="true" />
                        Simular Orden
                      </span>
                    </Button>

                    {simulationResult && (
                      <div className="rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2.5 text-[11px] tabular-nums text-[var(--a-secondary)]">
                        <div className="font-bold text-[var(--a-positive)]">Simulación Exitosa para {simulationResult.ticker}</div>
                        <div>Capital a Invertir: ${simulationResult.simulated_capital_usd} USD</div>
                        <div>Acciones Estimadas: {simulationResult.estimated_shares} unidades</div>
                        <div>Certificado por Filtro Humano: Sí</div>
                      </div>
                    )}

                    {simulationError && (
                      <div className="rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2.5 text-[11px] text-[var(--a-negative)]">
                        {simulationError}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </ToolSurfaceDock>
  );
};
