import React from 'react';
import { Activity, Layers, RefreshCw } from 'lucide-react';
import { DailyQuota } from '../types';

interface HeaderProps {
  currency: 'USD' | 'COP';
  setCurrency: (c: 'USD' | 'COP') => void;
  exchangeRate: number;
  quota?: DailyQuota;
  onRefresh: () => void;
  isLoading: boolean;
  privacyMode: boolean;
  setPrivacyMode: (value: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({
  currency,
  setCurrency,
  exchangeRate,
  quota,
  onRefresh,
  isLoading,
  privacyMode,
  setPrivacyMode
}) => {
  return (
    <header className="border-b border-[var(--a-line)] bg-[var(--a-chrome-bg)] backdrop-blur sticky top-0 z-40 px-4 lg:px-8 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand & Strategy Vision */}
        <div className="flex items-center space-x-3 w-full md:w-auto justify-between md:justify-start">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-lg bg-[var(--a-surface)] border border-[var(--a-line-strong)] flex items-center justify-center text-[var(--a-brand)]">
              <Layers className="w-5 h-5" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-[var(--a-text)] flex items-center gap-2">
                Finanzas Inteligentes
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-[var(--a-surface)] text-[var(--a-positive)] border border-[var(--a-line)]">
                  v0.4 Local
                </span>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-[var(--a-surface)] text-[var(--a-warning)] border border-[var(--a-line)]">
                  Manual / CSV / Wallet
                </span>
              </h1>
              <p className="text-xs text-[var(--a-secondary)] hidden sm:block">
                Estrategia, Crecimiento, Gestión Inteligente y Control de Riesgo
              </p>
            </div>
          </div>

          <div className="flex md:hidden items-center gap-2">
            <button
              type="button"
              onClick={onRefresh}
              disabled={isLoading}
              aria-label="Actualizar datos"
              title="Actualizar datos"
              aria-busy={isLoading}
              className="a-motion p-2 rounded-lg bg-[var(--a-surface)] hover:bg-[var(--a-elevated)] text-[var(--a-secondary)] border border-[var(--a-line)] transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-[var(--a-brand)]' : ''}`} aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Action Controls: Currency Switcher, API Quota Indicator, Refresh */}
        <div className="flex flex-wrap items-center justify-end gap-2.5 w-full md:w-auto">
          {/* Parity Info */}
          <div className="hidden lg:flex items-center text-xs text-[var(--a-secondary)] bg-[var(--a-surface)] px-2.5 py-1.5 rounded-md border border-[var(--a-line)] font-mono">
            <span className="text-[var(--a-muted)] mr-1.5">Tasa:</span>
            <span className="text-[var(--a-text)]">1 USD = {exchangeRate.toLocaleString()} COP</span>
          </div>

          {/* Daily API Quota Indicator */}
          {quota && (
            <div className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium bg-[var(--a-surface)] ${
              quota.is_quota_exhausted
                ? 'text-[var(--a-negative)] border-[var(--a-line-strong)]'
                : quota.used_requests > 20
                ? 'text-[var(--a-warning)] border-[var(--a-line-strong)]'
                : 'text-[var(--a-secondary)] border-[var(--a-line)]'
            }`}>
              <Activity className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Ingestión demo:</span>
              <span className="font-mono font-bold text-[var(--a-text)]">
                {quota.used_requests}/{quota.max_quota}
              </span>
              <span className="text-[10px] text-[var(--a-muted)]">/día</span>
            </div>
          )}

          {/* Privacy Toggle */}
          <button
            type="button"
            onClick={() => setPrivacyMode(!privacyMode)}
            aria-pressed={privacyMode}
            className={`px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors ${
              privacyMode
                ? 'bg-[var(--a-brand)] text-[var(--a-bg)] border-[var(--a-brand)]'
                : 'bg-[var(--a-surface)] text-[var(--a-secondary)] border-[var(--a-line-strong)] hover:bg-[var(--a-elevated)]'
            }`}
          >
            Privacidad
          </button>

          <div className="flex items-center bg-[var(--a-bg)] p-0.5 rounded-lg border border-[var(--a-line)]" role="group" aria-label="Moneda de visualización">
            <button
              type="button"
              onClick={() => setCurrency('USD')}
              aria-pressed={currency === 'USD'}
              aria-label="Mostrar importes en dólares"
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                currency === 'USD'
                  ? 'bg-[var(--a-brand)] text-[var(--a-bg)] shadow-sm'
                  : 'text-[var(--a-muted)] hover:text-[var(--a-text)]'
              }`}
            >
              USD ($)
            </button>
            <button
              type="button"
              onClick={() => setCurrency('COP')}
              aria-pressed={currency === 'COP'}
              aria-label="Mostrar importes en pesos colombianos"
              className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${
                currency === 'COP'
                  ? 'bg-[var(--a-brand)] text-[var(--a-bg)] shadow-sm'
                  : 'text-[var(--a-muted)] hover:text-[var(--a-text)]'
              }`}
            >
              COP ($)
            </button>
          </div>

          {/* Refresh Action */}
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            aria-busy={isLoading}
            className="a-motion hidden md:flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[var(--a-surface)] hover:bg-[var(--a-elevated)] text-[var(--a-secondary)] text-xs font-medium transition-colors border border-[var(--a-line-strong)]"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-[var(--a-brand)]' : ''}`} aria-hidden="true" />
            <span>Actualizar</span>
          </button>
        </div>
      </div>
    </header>
  );
};
