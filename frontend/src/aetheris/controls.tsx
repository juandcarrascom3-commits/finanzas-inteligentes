import React, { useEffect, useRef, useState } from 'react';

const controlClass =
  'min-h-10 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] placeholder:text-[var(--a-muted)] transition-colors focus:border-[var(--a-brand)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

type FieldFrameProps = {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
};

function FieldFrame({ id, label, hint, error, children }: FieldFrameProps) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">{label}</label>
      {children}
      {hint && <p id={`${id}-hint`} className="a-meta mt-1.5">{hint}</p>}
      {error && <p id={`${id}-error`} className="mt-1.5 text-xs text-[var(--a-negative)]">{error}</p>}
    </div>
  );
}

export type FieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (raw: string) => void;
  placeholder?: string;
  hint?: string;
  error?: string;
  invalid?: boolean;
  disabled?: boolean;
  list?: string;
};

export function Field({ id, label, value, onChange, placeholder, hint, error, invalid, disabled, list }: FieldProps) {
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') || undefined;
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error}>
      <input
        id={id}
        className={controlClass}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        list={list}
        aria-invalid={invalid || Boolean(error) || undefined}
        aria-describedby={describedBy}
      />
    </FieldFrame>
  );
}

const formatMoney = (value: number) => new Intl.NumberFormat('es-CO', {
  maximumFractionDigits: 8,
  useGrouping: true,
}).format(value);

/**
 * Política de parsing monetario para el locale visual es-CO. Determinista:
 *
 *  - Espacios y símbolos de moneda ($, €, …) se eliminan: nunca llegan al
 *    valor canónico. Cualquier otro carácter no numérico rechaza el keystroke
 *    (el campo controlado no cambia).
 *  - ',' es SIEMPRE decimal (nunca agrupador). Más de un ',' → rechazado.
 *  - Varios '.' → todos agrupadores:  12.000.000 → 12000000
 *  - Un solo '.' con exactamente 3 dígitos después → agrupador:
 *      1.500 → 1500        (intención agrupadora, contexto monetario es-CO)
 *  - Un solo '.' con otra cantidad de dígitos → decimal:
 *      1,5 o 1.5 → 1.5      (decimales permitidos: format admite 8 fracciones)
 *  - '.' + ',': los '.' se eliminan y la ',' es decimal (1.500,50 → 1500.5).
 *  - Signo '-' inicial solo si `allowNegative` (sign) lo permite; si no, el
 *    keystroke se rechaza. Un '-' a medias conserva el draft sin emitir.
 *  - '' → emite 0 (contrato numérico actual de MoneyField; paridad con V1).
 */
const CURRENCY_SYMBOLS = /[$€£¥¢₡₱₲₿]/g;
const NUMERIC_BODY = /^\d*(?:\.\d*)?$/;

type MoneyParseOutcome = { draft: string; value: number | null };

const parseMoneyDraft = (raw: string, allowNegative: boolean): MoneyParseOutcome | null => {
  const compact = raw.replace(/[\s\u00A0]/g, '').replace(CURRENCY_SYMBOLS, '');
  if (compact === '') return { draft: '', value: 0 };
  if (compact === ',' || compact === '.') return { draft: compact, value: 0 };
  if (compact === '-') return allowNegative ? { draft: '-', value: null } : null;

  const negative = compact.startsWith('-');
  if (negative && !allowNegative) return null;
  const body = negative ? compact.slice(1) : compact;
  if (body.includes('-')) return null;

  const commas = (body.match(/,/g) || []).length;
  if (commas > 1) return null;

  let normalized: string;
  if (commas === 1) {
    normalized = body.replace(/\./g, '').replace(',', '.');
  } else {
    const dots = (body.match(/\./g) || []).length;
    if (dots === 0) {
      normalized = body;
    } else if (dots === 1) {
      const fraction = body.split('.')[1] || '';
      normalized = fraction.length === 3 ? body.replace('.', '') : body;
    } else {
      normalized = body.replace(/\./g, '');
    }
  }

  if (!NUMERIC_BODY.test(normalized)) return null;
  const magnitude = Number(normalized);
  if (!Number.isFinite(magnitude)) return null;
  const value = negative ? -magnitude : magnitude;
  return { draft: compact, value: value === 0 ? 0 : value };
};

export type MoneyFieldProps = {
  id: string;
  label: string;
  value: number;
  onChange: (value: number) => void;
  currency: string;
  hint?: string;
  error?: string;
  disabled?: boolean;
  allowNegative?: boolean;
};

export function MoneyField({ id, label, value, onChange, currency, hint, error, disabled, allowNegative = false }: MoneyFieldProps) {
  // null → presentación formateada; string → representación editable/canónica.
  const [draft, setDraft] = useState<string | null>(null);
  const lastEmitted = useRef(value);

  // Cambios externos del contrato re-sincronizan la presentación; los
  // cambios que nosotros mismos emitimos conservan el draft en edición.
  useEffect(() => {
    if (value !== lastEmitted.current) setDraft(null);
    lastEmitted.current = value;
  }, [value]);

  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') || undefined;

  return (
    <FieldFrame id={id} label={label} hint={hint} error={error}>
      <div className="flex min-h-10 overflow-hidden rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] transition-colors focus-within:border-[var(--a-brand)] focus-within:shadow-[var(--a-focus-ring)]">
        <span className="flex items-center border-r border-[var(--a-line)] bg-[var(--a-surface)] px-3 text-[11px] font-bold uppercase tracking-wide text-[var(--a-secondary)]" aria-hidden="true">
          {currency}
        </span>
        <input
          id={id}
          type="text"
          inputMode="decimal"
          className="min-w-0 flex-1 bg-transparent px-3 py-2 text-right text-sm font-semibold tabular-nums text-[var(--a-text)] outline-none disabled:cursor-not-allowed disabled:opacity-60"
          value={draft !== null ? draft : formatMoney(value)}
          disabled={disabled}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error) || undefined}
          onFocus={() => setDraft(String(value))}
          onChange={(event) => {
            const outcome = parseMoneyDraft(event.target.value, allowNegative);
            if (!outcome) return; // keystroke inválido: el controlado no cambia
            setDraft(outcome.draft);
            if (outcome.value !== null) {
              lastEmitted.current = outcome.value;
              onChange(outcome.value);
            }
          }}
          onBlur={() => setDraft(null)}
        />
      </div>
    </FieldFrame>
  );
}

export type MetricInputProps = {
  id: string;
  label: string;
  value: number;
  /**
   * Emite '' cuando el usuario vacía el campo: el vacío se conserva en el
   * contrato y los handlers existentes lo convierten con sus reglas actuales
   * (Number(x || …)), por lo que los payloads finales no cambian.
   */
  onChange: (value: number | '') => void;
  unit: string;
  hint?: string;
  error?: string;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  allowNegative?: boolean;
};

export function MetricInput({ id, label, value, onChange, unit, hint, error, min, max, step, disabled, allowNegative = false }: MetricInputProps) {
  // null → presentación del contrato; string → draft (incluye '' sticky).
  const [draft, setDraft] = useState<string | null>(null);
  const lastEmitted = useRef<number | ''>(value);

  useEffect(() => {
    // El contrato consumidor envuelve con Number(): Number('') === 0.
    const expected = lastEmitted.current === '' ? 0 : lastEmitted.current;
    if (value !== expected) setDraft(null);
    lastEmitted.current = value;
  }, [value]);

  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') || undefined;
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error}>
      <div className="flex min-h-10 overflow-hidden rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] transition-colors focus-within:border-[var(--a-brand)] focus-within:shadow-[var(--a-focus-ring)]">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          className="min-w-0 flex-1 bg-transparent px-3 py-2 text-right text-sm font-semibold tabular-nums text-[var(--a-text)] outline-none disabled:cursor-not-allowed disabled:opacity-60"
          value={draft !== null ? draft : String(value)}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error) || undefined}
          onChange={(event) => {
            const raw = event.target.value;
            if (raw === '') {
              // Usuario vació el campo: conserva vacío (F-04), no emite 0.
              setDraft('');
              lastEmitted.current = '';
              onChange('');
              return;
            }
            const next = Number(raw);
            if (!Number.isFinite(next) || (!allowNegative && next < 0)) return;
            setDraft(raw);
            lastEmitted.current = next;
            onChange(next);
          }}
          onBlur={() => setDraft((current) => (current === '' ? '' : null))}
        />
        <span className="flex items-center border-l border-[var(--a-line)] bg-[var(--a-surface)] px-3 text-[11px] font-bold text-[var(--a-secondary)]" aria-hidden="true">
          {unit}
        </span>
      </div>
    </FieldFrame>
  );
}

export type SegmentOption<T extends string> = { value: T; label: string };

export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
  disabled = false,
}: {
  label: string;
  value: T;
  options: SegmentOption<T>[];
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const move = (index: number, direction: -1 | 1) => {
    const nextIndex = (index + direction + options.length) % options.length;
    onChange(options[nextIndex].value);
    refs.current[nextIndex]?.focus();
  };

  return (
    <fieldset className="min-w-0" disabled={disabled}>
      <legend className="mb-1.5 text-xs font-bold text-[var(--a-secondary)]">{label}</legend>
      <div className="grid min-h-10 auto-cols-fr grid-flow-col overflow-hidden rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-0.5" role="radiogroup" aria-label={label}>
        {options.map((option, index) => {
          const selected = option.value === value;
          return (
            <button
              key={option.value}
              ref={(node) => { refs.current[index] = node; }}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(option.value)}
              onKeyDown={(event) => {
                if (event.key === 'ArrowLeft') { event.preventDefault(); move(index, -1); }
                if (event.key === 'ArrowRight') { event.preventDefault(); move(index, 1); }
              }}
              className={`min-h-9 min-w-0 rounded-[calc(var(--a-radius-sm)-3px)] px-2 text-xs font-bold transition-colors ${selected ? 'bg-[var(--a-brand)] text-[var(--a-bg)]' : 'text-[var(--a-muted)] hover:bg-[var(--a-hover)] hover:text-[var(--a-text)]'}`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export type ButtonVariant = 'primary' | 'operational' | 'quiet' | 'positive' | 'negative';

const buttonVariant: Record<ButtonVariant, string> = {
  primary: 'border-[var(--a-brand)] bg-[var(--a-brand)] text-[var(--a-bg)] hover:brightness-95',
  operational: 'border-[var(--a-brand)] bg-[var(--a-active)] text-[var(--a-brand)] hover:bg-[var(--a-hover)]',
  quiet: 'border-[var(--a-line)] bg-[var(--a-surface)] text-[var(--a-secondary)] hover:bg-[var(--a-elevated)]',
  positive: 'border-[var(--a-line)] bg-[var(--a-active)] text-[var(--a-positive)] hover:border-[var(--a-positive)]',
  negative: 'border-[var(--a-line)] bg-[var(--a-active)] text-[var(--a-negative)] hover:border-[var(--a-negative)]',
};

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }>(
  function Button({ variant = 'quiet', className = '', ...props }, ref) {
    return (
      <button
        ref={ref}
        type="button"
        {...props}
        className={`a-motion min-h-10 rounded-[var(--a-radius-sm)] border px-3.5 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-60 [@media(pointer:coarse)]:min-h-11 ${buttonVariant[variant]} ${className}`}
      />
    );
  }
);
