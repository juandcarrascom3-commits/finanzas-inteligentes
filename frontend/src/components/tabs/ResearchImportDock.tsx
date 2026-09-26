import { useEffect, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';
import { AlertTriangle, Info, RefreshCw } from 'lucide-react';
import { Button } from '../../aetheris/controls';
import { DataState, InlineMetric } from '../../aetheris/primitives';
import { ToolSurfaceDock } from '../../aetheris/ToolSurfaceDock';
import { previewResearch, ingestResearch, ResearchApiError } from '../../services/api';
import type { ResearchDecision, ResearchIngestResult, ResearchPreview } from '../../types';

/**
 * RF2 — Importar Research: pegar lote JSON → validación local → preview de
 * solo lectura → confirmación deliberada → ingest → recuperación de
 * stale / conflicto / nothing-to-apply.
 *
 * Invariantes: la preview nunca escribe ni auto-ingesta; el ingest usa
 * EXACTAMENTE el rawBatch que produjo la preview (nunca se reparsea);
 * el botón de confirmar solo existe con preview vigente y sin conflictos;
 * nunca se muestra texto crudo de excepciones del backend.
 */

type Phase =
  | 'idle'
  | 'parse_error'
  | 'previewing'
  | 'preview_ready'
  | 'ingesting'
  | 'stale'
  | 'nothing'
  | 'success'
  | 'api_error';

type UiError = { code?: string; message: string };

type ParseResult = { ok: true; batch: unknown[] } | { ok: false; message: string };

/** Tope global de filas renderizadas; los conteos del backend siempre son exactos. */
const PREVIEW_ROW_CAP = 200;
/** Límite de transporte del backend (MAX_IMPORT_PLAN_ITEMS). */
const RESEARCH_BATCH_MAX = 5000;

const FALLBACK_ERROR = 'No se pudo completar la operación de Research.';
const FORMAT_422_ERROR =
  'El backend rechazó el formato del lote: se espera una lista de hasta 5000 elementos con la forma esperada.';
const PARSE_EMPTY = 'Pega un lote JSON antes de previsualizar.';
const PARSE_INVALID = 'El texto no es JSON válido. Revisa el lote pegado.';
const PARSE_SHAPE = 'Se espera un objeto JSON o una lista de objetos.';
const NOTHING_COPY = 'No hay elementos nuevos ni modificados que aplicar.';
const STALE_COPY = 'La vista previa ya no refleja el estado actual; vuelva a generarla.';

const textareaClass =
  'min-h-40 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 font-mono text-sm text-[var(--a-text)] placeholder:text-[var(--a-muted)] transition-colors focus:border-[var(--a-brand)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

/** Vocabulario cerrado de changed_fields (DELTA_CHANGED_FIELDS del backend). */
const CHANGED_FIELD_LABEL: Record<string, string> = {
  title: 'Título',
  url: 'URL',
  published_at: 'Fecha de publicación',
  summary: 'Resumen',
  epistemic: 'Clasificación',
  entity_tickers: 'Entidades',
};

/** Códigos estables de motivos → copia fija. Nunca excepciones crudas. */
const REASON_COPY: Record<string, string> = {
  /* REJECTED (ValueError estable de normalize_research_item). */
  TITLE_REQUIRED: 'Falta el título.',
  SOURCE_ID_REQUIRED: 'Falta la fuente (source_id).',
  SOURCE_ID_INVALID: 'La fuente no tiene un identificador válido.',
  FETCHED_AT_REQUIRED: 'Falta la fecha de captura (fetched_at).',
  TIMESTAMP_REQUIRED: 'Falta una fecha requerida.',
  INVALID_RESEARCH_ITEM_INPUT: 'El elemento no es un objeto de Research válido.',
  RESEARCH_ID_REQUIRED: 'El elemento no tiene identidad estable.',
  /* CONFLICT. */
  IN_BATCH_CONFLICT: 'La misma identidad aparece con contenido distinto dentro del lote.',
  /* Avisos sobre elementos aceptados (tokens estables de normalización). */
  url_unparsed: 'URL no interpretable.',
  external_ref_not_identifiable: 'Referencia externa no identificable; se derivó una.',
  ticker_unnormalized: 'Tickers no normalizados.',
  invalid_timestamp: 'Fecha no legible; se descartó.',
  epistemic_unspecified: 'Sin clasificación declarada.',
};

/** Orden de grupos = prioridad de render bajo el cap global. */
const GROUPS: Array<{ key: 'conflict' | 'rejected' | 'writes' | 'unchanged'; label: string; statuses: ResearchDecision['status'][] }> = [
  { key: 'conflict', label: 'Conflicto', statuses: ['CONFLICT'] },
  { key: 'rejected', label: 'No se aplicará', statuses: ['REJECTED'] },
  { key: 'writes', label: 'Nuevo y con cambios', statuses: ['NEW', 'CHANGED'] },
  { key: 'unchanged', label: 'Sin cambios', statuses: ['UNCHANGED'] },
];

function parseBatch(text: string): ParseResult {
  const trimmed = text.trim();
  if (!trimmed) return { ok: false, message: PARSE_EMPTY };
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return { ok: false, message: PARSE_INVALID };
  }
  let batch: unknown[];
  if (Array.isArray(parsed)) batch = parsed;
  else if (parsed !== null && typeof parsed === 'object') batch = [parsed];
  else return { ok: false, message: PARSE_SHAPE };
  if (batch.length > RESEARCH_BATCH_MAX) {
    return { ok: false, message: `El lote tiene ${batch.length} elementos; el máximo es ${RESEARCH_BATCH_MAX}.` };
  }
  return { ok: true, batch };
}

/** Solo copia documentada / fija: nunca texto crudo de excepciones. */
function toUiError(err: unknown): UiError {
  if (err instanceof ResearchApiError) {
    if (err.serverMessage) return { code: err.code, message: err.serverMessage };
    if (err.status === 422) return { code: err.code, message: FORMAT_422_ERROR };
    return { code: err.code, message: FALLBACK_ERROR };
  }
  return { message: FALLBACK_ERROR };
}

function reasonCopy(reason: string, status: ResearchDecision['status']): string {
  const known = REASON_COPY[reason];
  if (known) return known;
  /* Código desconocido en un rechazo: copia fija + token estable (no excepción). */
  if (status === 'REJECTED') return `Razón no reconocida por la interfaz (${reason}).`;
  return reason;
}

function statusBadge(status: ResearchDecision['status']): { label: string; className: string } {
  const base =
    'inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.06em]';
  switch (status) {
    case 'CONFLICT':
      return { label: 'Conflicto', className: `${base} border-[var(--a-negative)] text-[var(--a-negative)]` };
    case 'REJECTED':
      return { label: 'No se aplicará', className: `${base} border-[var(--a-line)] text-[var(--a-muted)]` };
    case 'NEW':
      return { label: 'Nuevo', className: `${base} border-[var(--a-brand)] text-[var(--a-brand)]` };
    case 'CHANGED':
      return { label: 'Con cambios', className: `${base} border-[var(--a-warning)] text-[var(--a-warning)]` };
    default:
      return { label: 'Sin cambios', className: `${base} border-[var(--a-line)] text-[var(--a-muted)]` };
  }
}

export interface ResearchImportDockProps {
  triggerRef: RefObject<HTMLButtonElement>;
  onClose: () => void;
  onApplied: () => void;
}

export function ResearchImportDock({ triggerRef, onClose, onApplied }: ResearchImportDockProps) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [draft, setDraft] = useState('');
  const [rawBatch, setRawBatch] = useState<unknown[] | null>(null);
  const [preview, setPreview] = useState<ResearchPreview | null>(null);
  const [ingestResult, setIngestResult] = useState<ResearchIngestResult | null>(null);
  const [error, setError] = useState<UiError | null>(null);
  const resultsHeadingRef = useRef<HTMLHeadingElement>(null);
  const appliedRef = useRef(false);

  const busy = phase === 'previewing' || phase === 'ingesting';

  async function startPreview(batch: unknown[]): Promise<void> {
    setPhase('previewing');
    try {
      const result = await previewResearch(batch);
      setPreview(result);
      setPhase('preview_ready');
    } catch (err) {
      setPreview(null);
      setError(toUiError(err));
      setPhase('api_error');
    }
  }

  /** Entrada principal: parsea el draft LOCALMENTE y guarda el rawBatch exacto. */
  function handlePreviewClick(): void {
    const parsed = parseBatch(draft);
    if (!parsed.ok) {
      setPreview(null);
      setRawBatch(null);
      setError({ message: parsed.message });
      setPhase('parse_error');
      return;
    }
    setRawBatch(parsed.batch);
    setError(null);
    setIngestResult(null);
    setPreview(null);
    void startPreview(parsed.batch);
  }

  async function runIngest(batch: unknown[], hash: string): Promise<void> {
    setPhase('ingesting');
    setError(null);
    try {
      const result = await ingestResearch({ items: batch, preview_hash: hash, confirm_import: true });
      setIngestResult(result);
      setPreview(null);
      setPhase('success');
      if (!appliedRef.current) {
        appliedRef.current = true;
        onApplied();
      }
    } catch (err) {
      /* El estado de aprobación anterior se descarta siempre; draft/rawBatch no. */
      const ui = toUiError(err);
      const code = err instanceof ResearchApiError ? err.code : undefined;
      setPreview(null);
      setError({ code, message: ui.message });
      if (code === 'STALE_PREVIEW') setPhase('stale');
      else if (code === 'NOTHING_TO_APPLY') setPhase('nothing');
      else setPhase('api_error');
    }
  }

  function handleConfirm(): void {
    if (!preview || !rawBatch || !canConfirm) return;
    const n = preview.counts.new + preview.counts.changed;
    if (!window.confirm(`¿Aplicar ${n} elementos nuevos o modificados a Research?`)) return;
    void runIngest(rawBatch, preview.preview_hash);
  }

  /** Recuperación: re-previsualiza el rawBatch conservado (draft intacto). */
  function handleReviewAgain(): void {
    if (!rawBatch || busy) return;
    setError(null);
    void startPreview(rawBatch);
  }

  const writes = preview ? preview.counts.new + preview.counts.changed : 0;
  const canConfirm =
    phase === 'preview_ready' &&
    preview !== null &&
    !busy &&
    preview.counts.conflict === 0 &&
    writes > 0 &&
    Boolean(preview.preview_hash);

  const disabledReason = !preview
    ? null
    : preview.counts.conflict > 0
      ? 'Hay conflictos de identidad: la ingesta está bloqueada hasta corregir el lote pegado.'
      : writes === 0
        ? NOTHING_COPY
        : null;

  /* Cap GLOBAL de 200 filas consumido en orden de prioridad de grupos. */
  const renderedGroups = useMemo(() => {
    if (!preview) return [];
    let budget = PREVIEW_ROW_CAP;
    const out: Array<{ key: string; label: string; rows: ResearchDecision[]; total: number }> = [];
    for (const group of GROUPS) {
      const matching = preview.items.filter((row) => group.statuses.includes(row.status));
      if (matching.length === 0) continue;
      const rows = matching.slice(0, Math.max(0, budget));
      budget -= rows.length;
      out.push({ key: group.key, label: group.label, rows, total: matching.length });
      if (budget <= 0) break;
    }
    return out;
  }, [preview]);

  const renderedTotal = renderedGroups.reduce((sum, group) => sum + group.rows.length, 0);

  /* Señales entre fuentes: informativas, deduplicadas por ticker, sin bloqueo. */
  const signalChips = useMemo(() => {
    if (!preview) return [];
    const seen = new Set<string>();
    const chips: Array<{ ticker: string; sources: string }> = [];
    for (const signal of preview.cross_source_signals) {
      if (seen.has(signal.entity_ticker)) continue;
      seen.add(signal.entity_ticker);
      chips.push({ ticker: signal.entity_ticker, sources: signal.source_ids.join(' · ') });
    }
    return chips;
  }, [preview]);

  /* Tras cada preview nueva, el foco pasa al resultado. */
  useEffect(() => {
    if (phase === 'preview_ready') resultsHeadingRef.current?.focus();
  }, [phase]);

  const renderRow = (row: ResearchDecision, key: string) => {
    const badge = statusBadge(row.status);
    const reasons = row.reasons ?? [];
    const changedFields = row.changed_fields ?? [];
    return (
      <div key={key} className="rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2.5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className={badge.className}>{badge.label}</span>
          <span className="a-meta break-words">{row.source_id ?? 'Sin identificador'}</span>
          <span className="a-meta break-words">{row.external_ref ?? 'Sin referencia externa'}</span>
          {row.id && <span className="a-meta break-all font-mono">{row.id}</span>}
        </div>
        {row.status === 'CHANGED' && changedFields.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-bold text-[var(--a-secondary)]">Cambios:</span>
            {changedFields.map((field) => (
              <span
                key={field}
                className="rounded-full bg-[var(--a-active)] px-2 py-0.5 text-[10px] font-bold tracking-wide text-[var(--a-secondary)]"
              >
                {CHANGED_FIELD_LABEL[field] ?? field}
              </span>
            ))}
          </div>
        )}
        {reasons.length > 0 && (
          <ul className="mt-1.5 space-y-0.5">
            {reasons.map((reason) => (
              <li key={reason} className="a-meta">
                {reasonCopy(reason, row.status)}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  return (
    <ToolSurfaceDock
      id="research-import-dock"
      title="Importar Research"
      description="Pega un lote JSON, revisa la vista previa en solo lectura y confirma la aplicación. Nada se escribe hasta que confirmas."
      triggerRef={triggerRef}
      onClose={onClose}
    >
      {/* 1. Entrada — único método V1: pegar JSON. */}
      <div>
        <label htmlFor="research-import-input" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">
          Lote JSON de Research
        </label>
        <textarea
          id="research-import-input"
          rows={6}
          className={textareaClass}
          placeholder='[{"source_id": "...", "external_ref": "...", "title": "...", "fetched_at": "..."}]'
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={busy}
          aria-invalid={phase === 'parse_error'}
          aria-describedby={phase === 'parse_error' ? 'research-import-parse-error' : undefined}
        />
        {phase === 'parse_error' && error && (
          <p id="research-import-parse-error" role="alert" className="mt-1.5 text-xs text-[var(--a-negative)]">
            {error.message}
          </p>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="quiet" onClick={handlePreviewClick} disabled={busy}>
          <RefreshCw className="mr-1.5 inline h-3.5 w-3.5" aria-hidden="true" />
          Previsualizar
        </Button>
      </div>

      {/* 2. Anuncios de fase (aria-live único y persistente). */}
      <div role="status" aria-live="polite" className="mt-4">
        {phase === 'previewing' && <p className="a-meta">Generando vista previa de solo lectura…</p>}
        {phase === 'preview_ready' && preview && (
          <p className="a-meta">
            Vista previa lista: {preview.items.length} resultados. Nada se aplica hasta que confirmes.
          </p>
        )}
        {phase === 'ingesting' && <p className="a-meta">Aplicando el lote en Research…</p>}
        {phase === 'stale' && <p className="a-meta">{error?.message ?? STALE_COPY}</p>}
        {phase === 'nothing' && <p className="a-meta">{NOTHING_COPY}</p>}
        {phase === 'success' && ingestResult && (
          <p className="a-meta">
            Lote aplicado: {ingestResult.write_counts.inserted} insertados, {ingestResult.write_counts.updated}{' '}
            actualizados, {ingestResult.write_counts.unchanged} sin cambios.
          </p>
        )}
        {phase === 'api_error' && error && <p className="a-meta">{error.message}</p>}
      </div>

      {/* 3. Resultado — solo lectura. */}
      {preview && (
        <section className="mt-5 border-t border-[var(--a-line)] pt-4" aria-labelledby="research-preview-heading">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3
              id="research-preview-heading"
              ref={resultsHeadingRef}
              tabIndex={-1}
              className="a-module-title outline-none"
            >
              Vista previa de resultados
            </h3>
            <span className="inline-flex items-center rounded-full border border-[var(--a-line)] bg-[var(--a-surface)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.06em] text-[var(--a-muted)]">
              Solo lectura
            </span>
          </div>

          {/* Conteos exactos del backend. */}
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            <InlineMetric label="Nuevo" value={String(preview.counts.new)} />
            <InlineMetric label="Con cambios" value={String(preview.counts.changed)} />
            <InlineMetric label="Sin cambios" value={String(preview.counts.unchanged)} />
            <InlineMetric label="Conflicto" value={String(preview.counts.conflict)} />
            <InlineMetric label="No se aplicará" value={String(preview.counts.rejected)} />
            <InlineMetric label="Avisos" value={String(preview.counts.warnings)} />
          </div>

          {/* Conflicto: bloquea la ingesta; sin botón de ignorar. */}
          {preview.counts.conflict > 0 && (
            <div className="mt-4 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-active)] p-3">
              <p className="flex items-center gap-1.5 text-xs font-bold text-[var(--a-negative)]">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                Conflicto de identidad: la ingesta está bloqueada
              </p>
              <p className="a-meta mt-1.5">
                La misma identidad aparece con contenido distinto dentro del lote. La ingesta no puede continuar:
                corrige el lote pegado y revisa de nuevo.
              </p>
              <div className="mt-2">
                <Button variant="quiet" onClick={handlePreviewClick} disabled={busy}>
                  Revisar de nuevo
                </Button>
              </div>
            </div>
          )}

          {/* Señal entre fuentes: informativa, nunca conflicto. */}
          {signalChips.length > 0 && (
            <div className="mt-3 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] px-3 py-2">
              <p className="flex items-center gap-1.5 text-xs font-bold text-[var(--a-secondary)]">
                <Info className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                Posible duplicado entre fuentes (informativo)
              </p>
              <ul className="mt-1 space-y-0.5">
                {signalChips.map((chip) => (
                  <li key={chip.ticker} className="a-meta">
                    {chip.ticker} · fuentes: {chip.sources} · no bloquea la ingesta.
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Grupos en orden de prioridad bajo el cap global. */}
          <div className="mt-4 grid gap-3">
            {renderedGroups.map((group) => (
              <section key={group.key} aria-labelledby={`research-import-group-${group.key}`}>
                <div className="flex items-baseline justify-between gap-3 border-t border-[var(--a-line)] pt-3">
                  <h4 id={`research-import-group-${group.key}`} className="a-page-kicker">
                    {group.label}
                  </h4>
                  <span className="a-meta">{group.total}</span>
                </div>
                <div className="mt-2 grid gap-1.5">
                  {group.rows.map((row, index) => renderRow(row, `${group.key}-${index}`))}
                </div>
                {group.rows.length < group.total && (
                  <p className="a-meta mt-1.5">
                    Mostrando {group.rows.length} de {group.total} en este grupo.
                  </p>
                )}
                {group.key === 'rejected' && (
                  <p className="a-meta mt-1.5">Los elementos rechazados no se aplican y no bloquean la ingesta.</p>
                )}
                {group.key === 'writes' && preview.counts.changed > 0 && (
                  <p className="a-meta mt-1.5">
                    El backend indica qué campos cambiaron; los valores anteriores no están disponibles.
                  </p>
                )}
              </section>
            ))}
            <p className="a-meta">
              Mostrando {renderedTotal} de {preview.items.length} resultados
            </p>
          </div>

          {/* 4. Confirmación deliberada (nunca automática). */}
          <div className="mt-4 border-t border-[var(--a-line)] pt-4">
            <Button variant="primary" onClick={handleConfirm} disabled={!canConfirm}>
              Confirmar importación
            </Button>
            {phase === 'preview_ready' && !canConfirm && disabledReason && (
              <p className="a-meta mt-1.5">{disabledReason}</p>
            )}
            <p className="a-meta mt-1.5">
              La vista previa es solo lectura; nada se escribe hasta que confirmas.
            </p>
          </div>
        </section>
      )}

      {/* 5. STALE_PREVIEW: sin reintento automático; draft y rawBatch conservados. */}
      {phase === 'stale' && (
        <div className="mt-4 grid gap-3">
          <DataState
            state="STALE"
            title="Vista previa desactualizada"
            detail={error?.message ?? STALE_COPY}
          />
          <p className="a-meta">
            Se requiere una nueva vista previa antes de aplicar. El lote pegado ({rawBatch?.length ?? 0} elementos)
            se conserva.
            {error?.code ? ` Código: ${error.code}.` : ''}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="operational" onClick={handleReviewAgain} disabled={busy || !rawBatch}>
              <RefreshCw className="mr-1.5 inline h-3.5 w-3.5" aria-hidden="true" />
              Revisar de nuevo
            </Button>
            <Button variant="quiet" onClick={onClose}>
              Cerrar
            </Button>
          </div>
        </div>
      )}

      {/* 6. NOTHING_TO_APPLY: informativo, no es un fallo. */}
      {phase === 'nothing' && (
        <div className="mt-4 grid gap-3">
          <DataState state="EMPTY" title="Nada que aplicar" detail={NOTHING_COPY} />
          <div className="flex flex-wrap gap-2">
            <Button variant="operational" onClick={handleReviewAgain} disabled={busy || !rawBatch}>
              Revisar de nuevo
            </Button>
            <Button variant="quiet" onClick={onClose}>
              Cerrar
            </Button>
          </div>
        </div>
      )}

      {/* 7. APPLIED: conteos exactos; el dock permanece abierto. */}
      {phase === 'success' && ingestResult && (
        <div className="mt-4 grid gap-3">
          <DataState
            state="READY"
            title="Lote aplicado en Research"
            detail="La lista persistida se actualizó con el resultado de la ingesta."
          />
          <div className="grid grid-cols-3 gap-2">
            <InlineMetric label="Insertados" value={String(ingestResult.write_counts.inserted)} />
            <InlineMetric label="Actualizados" value={String(ingestResult.write_counts.updated)} />
            <InlineMetric label="Sin cambios" value={String(ingestResult.write_counts.unchanged)} />
          </div>
          {!ingestResult.audit.recorded && (
            <p className="a-meta">Escritura aplicada; el registro de auditoría no se confirmó.</p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="quiet" onClick={onClose}>
              Cerrar
            </Button>
          </div>
        </div>
      )}

      {/* 8. Errores de API: copia fija + código estable, nunca excepción cruda. */}
      {phase === 'api_error' && error && (
        <div className="mt-4 grid gap-3">
          <div className="rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-active)] p-3">
            <p className="text-xs font-bold text-[var(--a-negative)]">No se pudo completar la operación</p>
            <p className="a-meta mt-1">{error.message}</p>
            {error.code && <p className="a-meta mt-1 font-mono">Código: {error.code}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {rawBatch && (
              <Button variant="operational" onClick={handleReviewAgain} disabled={busy}>
                Revisar de nuevo
              </Button>
            )}
            <Button variant="quiet" onClick={onClose}>
              Cerrar
            </Button>
          </div>
        </div>
      )}
    </ToolSurfaceDock>
  );
}

export default ResearchImportDock;
