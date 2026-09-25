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

const parseMoneyDraft = (draft: string, allowNegative: boolean): number | null => {
  const compact = draft.replace(/\s/g, '');
  if (compact === '' || compact === '-' || compact === ',' || compact === '.') return 0;
  if (!allowNegative && compact.startsWith('-')) return null;
  const separators = compact.match(/[.,]/g) || [];
  const normalized = separators.length > 1
    ? compact.replace(/[.,]/g, '')
    : compact.replace(',', '.');
  if (!/^-?\d*(?:\.\d*)?$/.test(normalized)) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
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
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value));

  useEffect(() => {
    if (!editing) setDraft(String(value));
  }, [editing, value]);
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
          value={editing ? draft : formatMoney(value)}
          disabled={disabled}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error) || undefined}
          onFocus={() => { setDraft(String(value)); setEditing(true); }}
          onChange={(event) => {
            const next = event.target.value;
            const parsed = parseMoneyDraft(next, allowNegative);
            if (parsed === null) return;
            setDraft(next);
            onChange(parsed);
          }}
          onBlur={() => setEditing(false)}
        />
      </div>
    </FieldFrame>
  );
}

export type MetricInputProps = {
  id: string;
  label: string;
  value: number;
  onChange: (value: number) => void;
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
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(' ') || undefined;
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error}>
      <div className="flex min-h-10 overflow-hidden rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] transition-colors focus-within:border-[var(--a-brand)] focus-within:shadow-[var(--a-focus-ring)]">
        <input
          id={id}
          type="number"
          inputMode="decimal"
          className="min-w-0 flex-1 bg-transparent px-3 py-2 text-right text-sm font-semibold tabular-nums text-[var(--a-text)] outline-none disabled:cursor-not-allowed disabled:opacity-60"
          value={value}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error) || undefined}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (!Number.isFinite(next) || (!allowNegative && next < 0)) return;
            onChange(next);
          }}
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
