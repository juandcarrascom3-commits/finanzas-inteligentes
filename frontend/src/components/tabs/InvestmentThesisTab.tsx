import React, { useState } from 'react';
import { Shield, Lock, Unlock, CheckCircle2, AlertTriangle, Star, HelpCircle, ArrowRight, Play } from 'lucide-react';
import { InvestmentThesis, Asset } from '../../types';

interface InvestmentThesisTabProps {
  theses: InvestmentThesis[];
  assets: Asset[];
  onSaveThesis: (thesis: Partial<InvestmentThesis>) => Promise<void>;
  onSimulatePurchase: (ticker: string, amountUsd: number) => Promise<any>;
  selectedTickerForSim?: string;
}

export const InvestmentThesisTab: React.FC<InvestmentThesisTabProps> = ({
  theses,
  assets,
  onSaveThesis,
  onSimulatePurchase,
  selectedTickerForSim
}) => {
  const [selectedTicker, setSelectedTicker] = useState<string>(
    selectedTickerForSim || (theses.length > 0 ? theses[0].ticker : 'NVDA')
  );

  // Active thesis or empty template
  const currentThesis = theses.find((t) => t.ticker === selectedTicker);

  const [thesisText, setThesisText] = useState<string>(currentThesis?.thesis_text || '');
  const [valuationGrade, setValuationGrade] = useState<number>(currentThesis?.valuation_grade || 4);
  const [timingContext, setTimingContext] = useState<string>(currentThesis?.timing_context || '');
  const [safetyMargin, setSafetyMargin] = useState<number>(currentThesis?.safety_margin || 25.0);

  const [criteria, setCriteria] = useState<{
    knows_business_model: boolean;
    debt_ebitda_healthy: boolean;
    margin_safety_above_20: boolean;
    timing_not_overbought: boolean;
    emotional_bias_checked: boolean;
  }>({
    knows_business_model: currentThesis?.criteria_details?.knows_business_model ?? true,
    debt_ebitda_healthy: currentThesis?.criteria_details?.debt_ebitda_healthy ?? true,
    margin_safety_above_20: currentThesis?.criteria_details?.margin_safety_above_20 ?? (safetyMargin >= 20),
    timing_not_overbought: currentThesis?.criteria_details?.timing_not_overbought ?? true,
    emotional_bias_checked: currentThesis?.criteria_details?.emotional_bias_checked ?? false,
  });

  const [simulationAmount, setSimulationAmount] = useState<number>(2000);
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
      {/* LEFT COLUMN: Investing Pro Qualitative Thesis Form */}
      <div className="lg:col-span-7 bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-gray-800">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-md bg-purple-500/10 text-purple-400">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-tight">
                Tesis de Inversión &bull; Filtro Humano (Investing Pro)
              </h3>
              <p className="text-[11px] text-gray-400">
                Variables cualitativas obligatorias y descarte de sesgos antes de ejecutar compras
              </p>
            </div>
          </div>

          {/* Asset Picker */}
          <select
            value={selectedTicker}
            onChange={(e) => handleTickerChange(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-xs font-bold text-emerald-400 focus:outline-none focus:border-emerald-500"
          >
            {assets.map((a) => (
              <option key={a.ticker} value={a.ticker}>
                {a.ticker} - {a.name}
              </option>
            ))}
          </select>
        </div>

        {/* Qualitative Parameters Form */}
        <div className="space-y-4">
          {/* Valuation Grade (1 to 5 Stars) */}
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1.5 flex items-center justify-between">
              <span>Calificación de Valuación (Investing Pro Fair Value)</span>
              <span className="text-[11px] text-emerald-400 font-mono">
                {valuationGrade === 5 ? 'Muy Infravalorado' : valuationGrade === 4 ? 'Infravalorado' : valuationGrade === 3 ? 'Valor Justo' : 'Sobrevalorado'}
              </span>
            </label>
            <div className="flex items-center space-x-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setValuationGrade(star)}
                  className={`p-2 rounded-lg border transition-all ${
                    star <= valuationGrade
                      ? 'bg-amber-500/10 border-amber-500/40 text-amber-400'
                      : 'bg-gray-900 border-gray-800 text-gray-600'
                  }`}
                >
                  <Star className="w-4 h-4 fill-current" />
                </button>
              ))}
              <span className="text-xs text-gray-400 font-mono ml-2">({valuationGrade}/5)</span>
            </div>
          </div>

          {/* Margin of Safety % */}
          <div>
            <div className="flex justify-between items-center text-xs font-semibold text-gray-300 mb-1.5">
              <span>Margen de Seguridad Deseado (%)</span>
              <span className={`font-mono font-bold ${safetyMargin >= 20 ? 'text-emerald-400' : 'text-red-400'}`}>
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
              className="w-full accent-emerald-500 bg-gray-900 cursor-pointer h-1.5 rounded-lg"
            />
          </div>

          {/* Timing Context */}
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1.5">
              Contexto de Timing &bull; Momento Técnico y Macro
            </label>
            <input
              type="text"
              placeholder="Ej: Consolidación tras corrección en media de 200 periodos; catalizador de resultados."
              value={timingContext}
              onChange={(e) => setTimingContext(e.target.value)}
              className="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 font-sans"
            />
          </div>

          {/* Qualitative Thesis Statement */}
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1.5">
              Cuerpo de la Tesis de Inversión (Hipótesis Fundamental)
            </label>
            <textarea
              rows={3}
              placeholder="Describa el foso defensivo (Moat), retorno esperado y riesgos del negocio..."
              value={thesisText}
              onChange={(e) => setThesisText(e.target.value)}
              className="w-full bg-gray-900 border border-gray-800 rounded-lg p-3 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 leading-relaxed font-sans"
            />
          </div>

          {/* Save Button */}
          <div className="pt-2 flex justify-end">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-all flex items-center gap-1.5"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{isSaving ? 'Guardando...' : 'Guardar y Certificar Tesis'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* RIGHT COLUMN: 5-Point Safety Guardrail Checklist & Simulation Gatekeeper */}
      <div className="lg:col-span-5 bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg flex flex-col justify-between space-y-5">
        <div>
          {/* Header Guardrail Status */}
          <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
            <div className="flex items-center space-x-2">
              {isGuardrailPassed ? (
                <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-400">
                  <Unlock className="w-4 h-4" />
                </div>
              ) : (
                <div className="p-1.5 rounded-md bg-red-500/10 text-red-400">
                  <Lock className="w-4 h-4" />
                </div>
              )}
              <div>
                <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                  Filtro Humano: {selectedTicker}
                </h4>
                <p className="text-[10px] text-gray-400">
                  {isGuardrailPassed ? 'Simulación Habilitada' : 'Operación Estrictamente Bloqueada'}
                </p>
              </div>
            </div>

            <span className={`text-[10px] font-mono px-2 py-0.5 rounded border font-bold ${
              isGuardrailPassed
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-red-500/10 text-red-400 border-red-500/30'
            }`}>
              {isGuardrailPassed ? 'DESBLOQUEADO' : 'BLOQUEADO'}
            </span>
          </div>

          {/* 5 Mandatory Checkpoints */}
          <div className="space-y-2.5">
            <p className="text-[11px] text-gray-400 mb-2">
              Para mitigar riesgos de capital, valide conscientemente los 5 filtros obligatorios:
            </p>

            <label className="flex items-start space-x-2.5 p-2 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={criteria.knows_business_model}
                onChange={() => handleCheckboxToggle('knows_business_model')}
                className="mt-0.5 accent-emerald-500 rounded"
              />
              <span className="text-[11px] text-gray-200">
                <strong>1. Comprensión del Negocio:</strong> Entiendo cómo monetiza y cuál es su ventaja competitiva (Moat).
              </span>
            </label>

            <label className="flex items-start space-x-2.5 p-2 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={criteria.debt_ebitda_healthy}
                onChange={() => handleCheckboxToggle('debt_ebitda_healthy')}
                className="mt-0.5 accent-emerald-500 rounded"
              />
              <span className="text-[11px] text-gray-200">
                <strong>2. Solvencia Financiera:</strong> Ratio Deuda Neta / EBITDA &lt; 3.0x o estructura financiera blindada.
              </span>
            </label>

            <label className="flex items-start space-x-2.5 p-2 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={criteria.margin_safety_above_20}
                onChange={() => handleCheckboxToggle('margin_safety_above_20')}
                className="mt-0.5 accent-emerald-500 rounded"
              />
              <span className="text-[11px] text-gray-200">
                <strong>3. Margen de Seguridad:</strong> El descuento sobre valor intrínseco estimado supera el 20%.
              </span>
            </label>

            <label className="flex items-start space-x-2.5 p-2 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={criteria.timing_not_overbought}
                onChange={() => handleCheckboxToggle('timing_not_overbought')}
                className="mt-0.5 accent-emerald-500 rounded"
              />
              <span className="text-[11px] text-gray-200">
                <strong>4. Timing Técnico:</strong> El precio no se encuentra en euforia parabólica ni sobrecompra extrema.
              </span>
            </label>

            <label className="flex items-start space-x-2.5 p-2 rounded-lg bg-gray-900/60 border border-gray-800 hover:border-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={criteria.emotional_bias_checked}
                onChange={() => handleCheckboxToggle('emotional_bias_checked')}
                className="mt-0.5 accent-emerald-500 rounded"
              />
              <span className="text-[11px] text-gray-200">
                <strong>5. Control de Sesgos:</strong> Tesis redactada con frialdad analítica, sin efecto rebaño (FOMO).
              </span>
            </label>
          </div>
        </div>

        {/* Guardrail Enforcer & Purchase Simulator */}
        <div className="pt-3 border-t border-gray-800">
          {!isGuardrailPassed ? (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <strong>Guardrail Activo:</strong> La simulación de órdenes de compra está estrictamente deshabilitada. Debe marcar los 5 criterios y asegurar un margen &ge; 20% para desbloquear la ejecución.
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                <span><strong>Filtro Humano Validado:</strong> Simulación de compra autorizada.</span>
              </div>

              <div className="flex items-center space-x-2">
                <div className="relative flex-1">
                  <span className="absolute left-2.5 top-2 text-gray-500 font-mono text-xs">$</span>
                  <input
                    type="number"
                    value={simulationAmount}
                    onChange={(e) => setSimulationAmount(parseFloat(e.target.value) || 0)}
                    className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-6 pr-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-emerald-500"
                    placeholder="Monto USD..."
                  />
                </div>
                <button
                  onClick={handleExecuteSimulation}
                  className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all flex items-center space-x-1.5 shadow"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>Simular Orden</span>
                </button>
              </div>

              {simulationResult && (
                <div className="p-2.5 bg-gray-900/90 rounded-lg border border-emerald-500/30 text-[11px] font-mono space-y-1 text-gray-200">
                  <div className="text-emerald-400 font-bold">Simulación Exitosa para {simulationResult.ticker}</div>
                  <div>Capital a Invertir: ${simulationResult.simulated_capital_usd} USD</div>
                  <div>Acciones Estimadas: {simulationResult.estimated_shares} unidades</div>
                  <div>Certificado por Filtro Humano: Sí</div>
                </div>
              )}

              {simulationError && (
                <div className="p-2.5 bg-red-500/10 rounded-lg border border-red-500/30 text-[11px] text-red-300">
                  {simulationError}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
