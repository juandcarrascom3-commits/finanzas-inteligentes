import React from 'react';
import { AlertTriangle, CheckCircle2, CircleHelp, Clock3, Info, MinusCircle } from 'lucide-react';

export type DeltaDirection = 'positive' | 'negative' | 'warning' | 'neutral' | 'analytical';
export type DataStateKind = 'READY' | 'PARTIAL' | 'STALE' | 'EMPTY' | 'UNEVALUABLE';

const toneColor: Record<DeltaDirection, string> = {
  positive: 'var(--a-positive)',
  negative: 'var(--a-negative)',
  warning: 'var(--a-warning)',
  neutral: 'var(--a-secondary)',
  analytical: 'var(--a-analytical)',
};

const stateCopy: Record<DataStateKind, { label: string; icon: React.ElementType; tone: DeltaDirection }> = {
  READY: { label: 'Disponible', icon: CheckCircle2, tone: 'positive' },
  PARTIAL: { label: 'Cobertura parcial', icon: CircleHelp, tone: 'warning' },
  STALE: { label: 'Datos sin actualizar', icon: Clock3, tone: 'warning' },
  EMPTY: { label: 'Sin datos aplicables', icon: MinusCircle, tone: 'neutral' },
  UNEVALUABLE: { label: 'Información insuficiente', icon: AlertTriangle, tone: 'analytical' },
};

export function DeltaMetric({ value, direction = 'neutral', detail }: { value: string; direction?: DeltaDirection; detail?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm font-semibold" style={{ color: toneColor[direction] }}>
      <span aria-hidden="true">{direction === 'negative' ? '↓' : direction === 'neutral' ? '•' : '↑'}</span>
      <span>{value}</span>
      {detail && <span className="a-meta font-normal text-[11px]">{detail}</span>}
    </span>
  );
}

export function InlineMetric({ label, value, delta, direction }: { label: string; value: string; delta?: string; direction?: DeltaDirection }) {
  return (
    <div className="min-w-0">
      <div className="a-meta">{label}</div>
      <div className="mt-1 flex flex-wrap items-baseline gap-2">
        <span className="text-xl font-bold tabular-nums text-[var(--a-text)]">{value}</span>
        {delta && <DeltaMetric value={delta} direction={direction} />}
      </div>
    </div>
  );
}

export function AmbientTrajectory({ values, label, caption = 'Trayectoria basada en datos disponibles.' }: { values: number[]; label: string; caption?: string }) {
  const width = 420;
  const height = 132;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const points = values.map((value, index) => {
    const x = values.length === 1 ? 0 : (index / (values.length - 1)) * width;
    const y = height - ((value - min) / Math.max(1, max - min)) * (height - 18) - 9;
    return `${x},${y}`;
  });
  const path = `M ${points.join(' L ')}`;
  const fill = `${path} L ${width},${height} L 0,${height} Z`;

  return (
    <figure className="m-0" aria-label={label}>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-36 w-full overflow-visible" role="img">
        <title>{label}</title>
        <path d={fill} fill="url(#a-trajectory-fill)" />
        <path d={path} fill="none" stroke="var(--a-brand)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <defs>
          <linearGradient id="a-trajectory-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--a-brand)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="var(--a-brand)" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
      <figcaption className="a-meta">{caption}</figcaption>
    </figure>
  );
}

export function HeroMetric({
  label,
  context,
  value,
  delta,
  trajectory,
  trajectoryCaption,
}: {
  label: string;
  context: string;
  value: string;
  delta?: { label: string; direction: DeltaDirection; detail: string };
  trajectory?: number[];
  trajectoryCaption?: string;
}) {
  const hasTrajectory = !!trajectory && trajectory.length > 1;
  return (
    <section className={`grid gap-6 ${hasTrajectory ? 'lg:grid-cols-[minmax(0,0.92fr)_minmax(260px,0.72fr)]' : ''}`}>
      <div>
        <div className="a-page-kicker">{label}</div>
        <div className="mt-4 text-[clamp(48px,8vw,96px)] font-[760] leading-none tracking-normal tabular-nums">{value}</div>
        <p className="a-page-subtitle">{context}</p>
        {delta && (
          <div className="mt-5">
            <DeltaMetric value={delta.label} direction={delta.direction} detail={delta.detail} />
          </div>
        )}
      </div>
      {hasTrajectory && (
        <div className="self-end">
          <AmbientTrajectory values={trajectory} label="Trayectoria financiera" caption={trajectoryCaption} />
        </div>
      )}
    </section>
  );
}

export function DataState({ state, title, detail }: { state: DataStateKind; title: string; detail: string }) {
  const copy = stateCopy[state];
  const Icon = copy.icon;
  return (
    <div className="flex gap-3 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3">
      <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: toneColor[copy.tone] }} aria-hidden="true" />
      <div>
        <div className="text-xs font-bold text-[var(--a-text)]">{title || copy.label}</div>
        <div className="a-meta">{detail}</div>
      </div>
    </div>
  );
}

export function AttentionSignal({
  title,
  summary,
  state,
  selected,
  onSelect,
}: {
  title: string;
  summary: string;
  state: DataStateKind;
  selected: boolean;
  onSelect: () => void;
}) {
  const copy = stateCopy[state];
  const Icon = copy.icon;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`a-motion w-full rounded-[var(--a-radius-sm)] border p-3 text-left ${selected ? 'bg-[var(--a-active)]' : 'bg-[var(--a-canvas)]'}`}
      style={{ borderColor: selected ? 'var(--a-brand)' : 'var(--a-line)' }}
    >
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: toneColor[copy.tone] }} aria-hidden="true" />
        <div className="min-w-0">
          <div className="text-xs font-bold text-[var(--a-text)]">{title}</div>
          <div className="a-meta mt-1">{copy.label} · {summary}</div>
        </div>
      </div>
    </button>
  );
}

export function Timeline({ items }: { items: Array<{ label: string; when: 'NOW' | 'FUTURE'; detail: string }> }) {
  return (
    <ol className="space-y-3">
      {items.map((item) => (
        <li key={`${item.when}-${item.label}`} className="grid grid-cols-[64px_1fr] gap-3">
          <span className="a-meta font-bold text-[var(--a-info)]">{item.when === 'NOW' ? 'Ahora' : 'Luego'}</span>
          <span>
            <span className="block text-sm font-semibold text-[var(--a-text)]">{item.label}</span>
            <span className="a-meta">{item.detail}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

export function Inspector({
  item,
  onClose,
}: {
  item: { title: string; summary: string; evidence: string[] } | null;
  onClose: () => void;
}) {
  if (!item) return null;

  return (
    <aside className="a-inspector a-enter fixed bottom-5 right-5 z-50 w-[min(420px,calc(100vw-32px))] rounded-[var(--a-radius)] border border-[var(--a-line-strong)] p-5" role="dialog" aria-modal="false" aria-label="Detalle de señal">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="a-page-kicker">Explicación y evidencia</div>
          <h2 className="mt-2 text-lg font-bold text-[var(--a-text)]">{item.title}</h2>
          <p className="a-page-subtitle mt-2 text-sm">{item.summary}</p>
        </div>
        <button type="button" onClick={onClose} className="rounded-full border border-[var(--a-line)] px-3 py-1 text-xs text-[var(--a-secondary)]">
          Cerrar
        </button>
      </div>
      <ul className="mt-4 space-y-2">
        {item.evidence.map((line) => (
          <li key={line} className="rounded-[var(--a-radius-sm)] bg-[var(--a-active)] px-3 py-2 text-xs text-[var(--a-secondary)]">
            <Info className="mr-2 inline h-3.5 w-3.5 text-[var(--a-info)]" aria-hidden="true" />
            {line}
          </li>
        ))}
      </ul>
    </aside>
  );
}
