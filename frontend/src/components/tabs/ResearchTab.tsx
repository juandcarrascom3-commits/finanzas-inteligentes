import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, BookOpen, ExternalLink, RefreshCw, Search, X } from 'lucide-react';
import { fetchResearchItems } from '../../services/api';
import type { ResearchItem } from '../../types';
import { DataState } from '../../aetheris/primitives';
import { Button } from '../../aetheris/controls';
import { ResearchImportDock } from './ResearchImportDock';

/**
 * Tope de consulta del listado GET. Es un límite de lectura, no una
 * afirmación de que el corpus completo esté representado.
 */
const RESEARCH_QUERY_LIMIT = 1000;

const fieldClass =
  'min-h-10 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] placeholder:text-[var(--a-muted)] transition-colors focus:border-[var(--a-brand)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

const EPISTEMIC_LABEL: Record<string, string> = {
  FACT: 'Hecho',
  REPORTED: 'Reporte',
  ANALYSIS: 'Análisis',
  UNSPECIFIED: 'Sin clasificar',
};

/** Tratamiento neutral: la etiqueta describe el origen, nunca confiabilidad. */
const EPISTEMIC_NOTE: Record<string, string> = {
  FACT: 'La fuente declara el contenido como hecho verificable. La etiqueta describe el origen declarado, no una validación propia.',
  REPORTED: 'La fuente relata el contenido sin verificarlo de forma independiente. La etiqueta describe el origen declarado, no una validación propia.',
  ANALYSIS: 'La fuente presenta interpretación u opinión. La etiqueta describe el origen declarado, no una validación propia.',
  UNSPECIFIED: 'La fuente no declaró una clasificación y ninguna se infiere.',
};

const NORMALIZATION_LABEL: Record<string, string> = {
  READY: 'Completa',
  PARTIAL: 'Parcial',
  UNKNOWN: 'Sin determinar',
};

/** Agrupación por metadatos de tiempo. Es presentación, no el enum Freshness. */
const BUCKETS = [
  { key: 'd7', label: 'Últimos 7 días' },
  { key: 'd30', label: '8–30 días' },
  { key: 'older', label: 'Más de 30 días' },
  { key: 'unknown', label: 'Sin fecha utilizable' },
];

const DAY_MS = 86_400_000;

function parseIso(value?: string | null): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function absoluteDate(iso: string): string {
  const parsed = Date.parse(iso);
  if (!Number.isFinite(parsed)) return 'Fecha no legible';
  return new Date(parsed).toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function absoluteDateTime(iso: string): string {
  const parsed = Date.parse(iso);
  if (!Number.isFinite(parsed)) return 'Fecha no legible';
  const date = new Date(parsed).toLocaleString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  });
  return `${date} UTC`;
}

function relativePhrase(diffMs: number): string | null {
  const abs = Math.abs(diffMs);
  if (abs < 60_000) return 'ahora mismo';
  if (abs < 3_600_000) return `hace ${Math.max(1, Math.round(abs / 60_000))} min`;
  if (abs < DAY_MS) return `hace ${Math.max(1, Math.round(abs / 3_600_000))} h`;
  if (abs < 30 * DAY_MS) return `hace ${Math.round(abs / DAY_MS)} días`;
  return null;
}

/** Fecha operativa de la fila: publicación si existe; si no, captura. */
function itemDate(item: ResearchItem): { iso: string; kind: 'Publicado' | 'Capturado' } | null {
  if (item.published_at && parseIso(item.published_at) !== null) {
    return { iso: item.published_at, kind: 'Publicado' };
  }
  if (item.fetched_at && parseIso(item.fetched_at) !== null) {
    return { iso: item.fetched_at, kind: 'Capturado' };
  }
  return null;
}

function timeLabel(item: ResearchItem): string {
  const date = itemDate(item);
  if (!date) return 'Sin fecha utilizable';
  const phrase = relativePhrase(Date.now() - (parseIso(date.iso) as number));
  return phrase ? `${date.kind} ${phrase}` : `${date.kind} ${absoluteDate(date.iso)}`;
}

function bucketIndex(item: ResearchItem): number {
  const parsed = parseIso(item.published_at) ?? parseIso(item.fetched_at);
  if (parsed === null) return 3;
  const days = (Date.now() - parsed) / DAY_MS;
  if (days <= 7) return 0;
  if (days <= 30) return 1;
  return 2;
}

function epistemicLabel(item: ResearchItem): string {
  return EPISTEMIC_LABEL[item.epistemic] ?? 'Sin clasificar';
}

function normalizationLabel(item: ResearchItem): string {
  return NORMALIZATION_LABEL[item.normalization_status] ?? 'Sin determinar';
}

function needsNormalizationWarning(item: ResearchItem): boolean {
  return item.normalization_status === 'PARTIAL' || item.normalization_status === 'UNKNOWN';
}

function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[92px_minmax(0,1fr)] items-start gap-2">
      <dt className="a-meta">{label}</dt>
      <dd className="min-w-0 break-words text-xs text-[var(--a-secondary)]">{children}</dd>
    </div>
  );
}

type LoadStatus = 'loading' | 'ready' | 'error';

export function ResearchTab() {
  const [items, setItems] = useState<ResearchItem[]>([]);
  const [status, setStatus] = useState<LoadStatus>('loading');
  const [sourceFilter, setSourceFilter] = useState('');
  const [epistemicFilter, setEpistemicFilter] = useState('');
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [knownSources, setKnownSources] = useState<string[]>([]);
  const rowRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const requestIdRef = useRef(0);
  /* RF2: dock de importación, estado local del tab (patrón PlanningTab). */
  const [openImport, setOpenImport] = useState(false);
  const importLauncherRef = useRef<HTMLButtonElement>(null);

  const load = useCallback(async (sourceId: string, epistemic: string) => {
    const requestId = ++requestIdRef.current;
    setStatus('loading');
    try {
      const data = await fetchResearchItems({
        source_id: sourceId || undefined,
        epistemic: epistemic || undefined,
        limit: RESEARCH_QUERY_LIMIT,
      });
      if (requestId !== requestIdRef.current) return;
      setItems(data);
      setKnownSources((previous) => {
        const merged = new Set(previous);
        data.forEach((item) => merged.add(item.source_id));
        return Array.from(merged).sort();
      });
      setStatus('ready');
    } catch (error) {
      if (requestId !== requestIdRef.current) return;
      console.error('Error loading research items:', error);
      setItems([]);
      setStatus('error');
    }
  }, []);

  // Lazy-load al montar; re-consulta solo cuando cambian los filtros del servidor.
  useEffect(() => {
    load(sourceFilter, epistemicFilter);
  }, [load, sourceFilter, epistemicFilter]);

  const closeInspector = useCallback(() => {
    const previousId = selectedId;
    setSelectedId(null);
    if (previousId) rowRefs.current[previousId]?.focus();
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        const row = rowRefs.current[selectedId];
        setSelectedId(null);
        row?.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [selectedId]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((item) => {
      const haystack = [
        item.title,
        item.summary ?? '',
        item.source_id,
        ...(item.entity_tickers ?? []),
      ]
        .join('\n')
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [items, query]);

  const groups = useMemo(() => {
    const buckets = BUCKETS.map((bucket) => ({ ...bucket, items: [] as ResearchItem[] }));
    visible.forEach((item) => buckets[bucketIndex(item)].items.push(item));
    return buckets.filter((bucket) => bucket.items.length > 0);
  }, [visible]);

  const selected = useMemo(
    () => (selectedId ? items.find((item) => item.id === selectedId) ?? null : null),
    [items, selectedId]
  );

  const hasServerFilters = Boolean(sourceFilter || epistemicFilter);
  const hasActiveFilters = hasServerFilters || Boolean(query.trim());

  const clearFilters = () => {
    setSourceFilter('');
    setEpistemicFilter('');
    setQuery('');
  };

  return (
    <div className="a-enter">
      <div
        className={
          openImport
            ? 'grid gap-[var(--a-stack)] min-[1041px]:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]'
            : 'a-workspace mt-0'
        }
      >
        <section className="a-canvas" aria-labelledby="research-title">
          <div className="a-page-kicker">Research</div>
          <h1 id="research-title" className="a-page-title">Conocimiento externo</h1>
          <p className="a-page-subtitle">
            Artículos y notas persistidos desde fuentes externas, con su procedencia,
            clasificación declarada y estado de normalización a la vista.
          </p>

          <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="min-w-0">
              <label htmlFor="research-source" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">
                Fuente
              </label>
              <select
                id="research-source"
                className={fieldClass}
                value={sourceFilter}
                onChange={(event) => setSourceFilter(event.target.value)}
              >
                <option value="">Todas las fuentes</option>
                {knownSources.map((source) => (
                  <option key={source} value={source}>{source}</option>
                ))}
              </select>
            </div>

            <div className="min-w-0">
              <label htmlFor="research-epistemic" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">
                Clasificación
              </label>
              <select
                id="research-epistemic"
                className={fieldClass}
                value={epistemicFilter}
                onChange={(event) => setEpistemicFilter(event.target.value)}
              >
                <option value="">Todas</option>
                <option value="FACT">Hecho</option>
                <option value="REPORTED">Reporte</option>
                <option value="ANALYSIS">Análisis</option>
                <option value="UNSPECIFIED">Sin clasificar</option>
              </select>
            </div>

            <div className="min-w-0 sm:col-span-2 lg:col-span-1">
              <label htmlFor="research-query" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">
                Buscar
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--a-muted)]" aria-hidden="true" />
                <input
                  id="research-query"
                  type="search"
                  className={`${fieldClass} pl-9`}
                  placeholder="Título, resumen, fuente o ticker"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="a-meta max-w-[62ch]">
              Fuente y clasificación se aplican en el servidor; la búsqueda de texto opera
              sobre los {items.length} elementos cargados. La consulta usa un límite de{' '}
              {RESEARCH_QUERY_LIMIT} registros y no representa el corpus completo.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                ref={importLauncherRef}
                variant={openImport ? 'operational' : 'quiet'}
                aria-pressed={openImport}
                onClick={() => setOpenImport((current) => !current)}
              >
                Importar Research
              </Button>
              <Button
                variant="quiet"
                onClick={() => load(sourceFilter, epistemicFilter)}
                disabled={status === 'loading'}
              >
                <RefreshCw className="mr-1.5 inline h-3.5 w-3.5" aria-hidden="true" />
                Actualizar
              </Button>
            </div>
          </div>

          <div className="mt-6 border-t border-[var(--a-line)] pt-5" aria-live="polite">
            {status === 'loading' && (
              <p className="a-meta">Cargando elementos de Research…</p>
            )}

            {status === 'error' && (
              <div className="grid gap-3">
                <DataState
                  state="UNEVALUABLE"
                  title="Research no disponible"
                  detail="No se pudo leer la lista de elementos en este momento."
                />
                <div>
                  <Button variant="operational" onClick={() => load(sourceFilter, epistemicFilter)}>
                    Reintentar
                  </Button>
                </div>
              </div>
            )}

            {status === 'ready' && items.length === 0 && !hasActiveFilters && (
              <DataState
                state="EMPTY"
                title="Sin investigación todavía"
                detail="Aún no hay elementos de Research persistidos en el backend local."
              />
            )}

            {status === 'ready' && items.length === 0 && hasActiveFilters && (
              <div className="grid gap-3">
                <DataState
                  state="EMPTY"
                  title="Sin resultados con los filtros actuales"
                  detail="Ningún elemento cargado cumple la fuente o clasificación seleccionada."
                />
                <div>
                  <Button variant="quiet" onClick={clearFilters}>Limpiar filtros</Button>
                </div>
              </div>
            )}

            {status === 'ready' && items.length > 0 && visible.length === 0 && (
              <div className="grid gap-3">
                <DataState
                  state="EMPTY"
                  title="Sin coincidencias en la búsqueda"
                  detail="Ningún elemento cargado coincide con el texto ingresado."
                />
                <div>
                  <Button variant="quiet" onClick={() => setQuery('')}>Limpiar búsqueda</Button>
                </div>
              </div>
            )}

            {status === 'ready' && visible.length > 0 && (
              <p className="a-meta">
                {visible.length} de {items.length} elementos cargados visibles
              </p>
            )}

            {status === 'ready' && groups.map((group) => (
              <section key={group.key} className="mt-6" aria-labelledby={`research-group-${group.key}`}>
                <div className="flex items-baseline justify-between gap-3">
                  <h2 id={`research-group-${group.key}`} className="a-page-kicker">{group.label}</h2>
                  <span className="a-meta">{group.items.length}</span>
                </div>
                <div className="mt-2 border-t border-[var(--a-line)]">
                  {group.items.map((item) => {
                    const isSelected = item.id === selectedId;
                    const date = itemDate(item);
                    const tickers = item.entity_tickers ?? [];
                    return (
                      <button
                        key={item.id}
                        ref={(node) => { rowRefs.current[item.id] = node; }}
                        type="button"
                        onClick={() => setSelectedId(item.id)}
                        aria-pressed={isSelected}
                        className={`a-motion w-full border-b border-l-2 border-[var(--a-line)] px-3 py-3.5 text-left ${
                          isSelected ? 'bg-[var(--a-active)]' : 'hover:bg-[var(--a-hover)]'
                        }`}
                        style={{ borderLeftColor: isSelected ? 'var(--a-brand)' : 'transparent' }}
                      >
                        <span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                          <span className="min-w-0 break-words text-sm font-semibold text-[var(--a-text)]">
                            {item.title}
                          </span>
                          <span className="a-meta">{item.source_id}</span>
                          <span className="a-meta">{timeLabel(item)}</span>
                          <span className="inline-flex items-center rounded-full border border-[var(--a-line)] bg-[var(--a-surface)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.06em] text-[var(--a-muted)]">
                            {epistemicLabel(item)}
                          </span>
                        </span>

                        {tickers.length > 0 && (
                          <span className="mt-2 flex flex-wrap items-center gap-1.5">
                            {tickers.map((ticker) => (
                              <span
                                key={ticker}
                                className="rounded-full bg-[var(--a-active)] px-2 py-0.5 text-[10px] font-bold tracking-wide text-[var(--a-secondary)]"
                              >
                                {ticker}
                              </span>
                            ))}
                          </span>
                        )}

                        {needsNormalizationWarning(item) && (
                          <span className="mt-2 flex items-center gap-1.5 a-meta text-[var(--a-warning)]">
                            <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                            Normalización {normalizationLabel(item).toLowerCase()}
                            {date ? null : ' · sin fecha utilizable'}
                          </span>
                        )}
                        {item.published_at && date && parseIso(item.published_at) === null && (
                          <span className="a-meta mt-1 block">Fecha de publicación no legible; se usa la captura.</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        </section>

        {openImport && (
          <ResearchImportDock
            triggerRef={importLauncherRef}
            onClose={() => setOpenImport(false)}
            onApplied={() => load(sourceFilter, epistemicFilter)}
          />
        )}

        <aside
          className={`a-elevated h-fit p-5 ${openImport ? 'min-[1041px]:col-span-2' : ''}`}
          aria-labelledby="research-inspector-title"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="a-page-kicker">Inspector</div>
              <h2 id="research-inspector-title" className="a-module-title mt-2 break-words">
                {selected ? selected.title : 'Detalle del elemento'}
              </h2>
            </div>
            {selectedId && (
              <Button variant="quiet" onClick={closeInspector} aria-label="Cerrar inspector" title="Cerrar inspector (Esc)">
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </Button>
            )}
          </div>

          {!selectedId && (
            <div className="mt-4">
              <p className="a-meta">
                Selecciona un registro del flujo para revisar su procedencia, fechas,
                clasificación declarada y estado de normalización.
              </p>
              <div className="mt-4 flex items-center gap-2 text-xs text-[var(--a-muted)]">
                <BookOpen className="h-4 w-4" aria-hidden="true" />
                Nada se selecciona hasta que lo pidas.
              </div>
            </div>
          )}

          {selectedId && !selected && (
            <div className="mt-4 grid gap-3">
              <DataState
                state="UNEVALUABLE"
                title="Elemento no disponible"
                detail="El registro seleccionado ya no está entre los elementos cargados."
              />
              <div>
                <Button variant="quiet" onClick={closeInspector}>Cerrar</Button>
              </div>
            </div>
          )}

          {selected && (
            <div key={selected.id} className="a-enter mt-4">
              <section aria-label="Resumen">
                <h3 className="a-module-title">Resumen</h3>
                {selected.summary ? (
                  <p className="mt-1.5 break-words text-sm leading-relaxed text-[var(--a-secondary)]">
                    {selected.summary}
                  </p>
                ) : (
                  <p className="a-meta mt-1.5">Sin resumen persistido para este elemento.</p>
                )}
              </section>

              <section className="mt-5" aria-label="Procedencia">
                <h3 className="a-module-title">Procedencia</h3>
                <dl className="mt-2">
                  <MetaRow label="Fuente">{selected.source_id}</MetaRow>
                  <MetaRow label="Publicado">
                    {selected.published_at && parseIso(selected.published_at) !== null ? (
                      <time dateTime={selected.published_at}>{absoluteDateTime(selected.published_at)}</time>
                    ) : (
                      'Sin fecha de publicación utilizable'
                    )}
                  </MetaRow>
                  <MetaRow label="Capturado">
                    {selected.fetched_at && parseIso(selected.fetched_at) !== null ? (
                      <time dateTime={selected.fetched_at}>{absoluteDateTime(selected.fetched_at)}</time>
                    ) : (
                      'Sin fecha de captura utilizable'
                    )}
                  </MetaRow>
                  <MetaRow label="Proveedor">{selected.provider || 'No declarado'}</MetaRow>
                  <MetaRow label="Método">{selected.ingestion_method || 'No declarado'}</MetaRow>
                  <MetaRow label="URL">
                    {selected.url ? (
                      <a
                        href={selected.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-start gap-1 text-[var(--a-brand)] underline underline-offset-2 break-all"
                      >
                        {selected.url.length > 96 ? `${selected.url.slice(0, 96)}…` : selected.url}
                        <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                      </a>
                    ) : (
                      'Sin URL registrada'
                    )}
                  </MetaRow>
                </dl>
              </section>

              <section className="mt-5" aria-label="Clasificación">
                <h3 className="a-module-title">Clasificación</h3>
                <p className="mt-1.5 text-sm font-bold text-[var(--a-text)]">{epistemicLabel(selected)}</p>
                <p className="a-meta mt-1">
                  Valor del backend: <span className="font-bold">{selected.epistemic}</span>.
                  {' '}{EPISTEMIC_NOTE[selected.epistemic] ?? 'Clasificación no reconocida por la interfaz.'}
                </p>
              </section>

              <section className="mt-5" aria-label="Entidades">
                <h3 className="a-module-title">Entidades</h3>
                {(selected.entity_tickers ?? []).length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(selected.entity_tickers ?? []).map((ticker) => (
                      <span
                        key={ticker}
                        className="rounded-full bg-[var(--a-active)] px-2 py-0.5 text-[11px] font-bold tracking-wide text-[var(--a-secondary)]"
                      >
                        {ticker}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="a-meta mt-1">Sin tickers asociados en la persistencia.</p>
                )}
              </section>

              <section className="mt-5" aria-label="Normalización">
                <h3 className="a-module-title">Normalización</h3>
                <p className={`mt-1.5 flex items-center gap-2 text-sm font-semibold ${
                  needsNormalizationWarning(selected) ? 'text-[var(--a-warning)]' : 'text-[var(--a-secondary)]'
                }`}>
                  {needsNormalizationWarning(selected) && (
                    <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                  )}
                  {normalizationLabel(selected)}
                  <span className="a-meta font-normal">Valor del backend: {selected.normalization_status}</span>
                </p>
                {(selected.reasons ?? []).length > 0 ? (
                  <ul className="mt-2 space-y-1">
                    {(selected.reasons ?? []).map((reason) => (
                      <li key={reason} className="a-meta rounded-[var(--a-radius-sm)] bg-[var(--a-active)] px-2.5 py-1.5">
                        {reason}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="a-meta mt-1">Sin observaciones de normalización registradas.</p>
                )}
              </section>

              <details className="mt-5 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3">
                <summary className="cursor-pointer text-xs font-bold text-[var(--a-secondary)]">
                  Detalles técnicos
                </summary>
                <dl className="mt-3">
                  <MetaRow label="Id">
                    <span className="break-all font-mono">{selected.id}</span>
                  </MetaRow>
                  <MetaRow label="External ref">
                    <span className="break-all font-mono">{selected.external_ref}</span>
                  </MetaRow>
                  <MetaRow label="Content hash">
                    <span className="break-all font-mono">{selected.content_hash}</span>
                  </MetaRow>
                </dl>
              </details>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

export default ResearchTab;
