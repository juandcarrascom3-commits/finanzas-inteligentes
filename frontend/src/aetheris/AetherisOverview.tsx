import React, { useState } from 'react';
import { AlertTriangle, Info } from 'lucide-react';
import { DashboardSummary, DataSourceInfo, FinancialInboxResult, MonthlyReview, TimelineItem, UnderstandSummary } from '../types';
import { Button } from './controls';
import { DataState, DataStateKind, DeltaDirection, DeltaMetric, HeroMetric, InlineMetric, Inspector, Timeline } from './primitives';

interface AetherisOverviewProps {
  dashboard: DashboardSummary;
  understand: UnderstandSummary | null;
  financialInbox: FinancialInboxResult | null;
  monthlyReview: MonthlyReview | null;
  dataSource?: DataSourceInfo;
  currency: 'USD' | 'COP';
  privacyMode: boolean;
}

type InspectorItem = { title: string; summary: string; evidence: string[] };

const money = (value: number | undefined | null, currencyCode: string, privacyMode: boolean) => {
  if (privacyMode) return '••••';
  return `${currencyCode} ${(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
};

const pct = (value: number | null | undefined) => value === null || value === undefined ? 'N/D' : `${value >= 0 ? '+' : ''}${value}%`;

const deltaDirection = (value: number | undefined | null): DeltaDirection => {
  if (value === null || value === undefined || value === 0) return 'neutral';
  return value > 0 ? 'positive' : 'negative';
};

const confidenceState = (level?: string): DataStateKind => {
  if (level === 'HIGH') return 'READY';
  if (level === 'MEDIUM') return 'PARTIAL';
  return 'UNEVALUABLE';
};

const inboxState = (status?: string): DataStateKind => {
  if (status === 'READY') return 'READY';
  if (status === 'EMPTY') return 'EMPTY';
  if (status === 'PARTIAL') return 'PARTIAL';
  return 'UNEVALUABLE';
};

// Copia visible de severidad; el valor canónico del backend no se altera.
const severityCopy: Record<string, string> = {
  URGENT: 'Urgente',
  ATTENTION: 'Atención',
  WATCH: 'Seguimiento',
  INFO: 'Info',
};

const severityLabel = (severity: string) => severityCopy[severity] || severity;

const timelineItems = (items: TimelineItem[]) => items.slice(0, 5).map((item) => ({
  label: item.title,
  when: item.temporal_relation === 'NOW' ? 'NOW' as const : 'FUTURE' as const,
  detail: [item.date, item.amount != null && item.currency ? `${item.currency} ${item.amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : null, item.certainty || item.confidence].filter(Boolean).join(' · '),
}));

export function AetherisOverview({
  dashboard,
  understand,
  financialInbox,
  monthlyReview,
  dataSource,
  currency,
  privacyMode,
}: AetherisOverviewProps) {
  const [inspectorItem, setInspectorItem] = useState<InspectorItem | null>(null);
  const netWorth = dashboard.kpis.net_worth;
  const netWorthValue = currency === 'USD'
    ? money(netWorth.net_worth_usd, 'USD', privacyMode)
    : money(netWorth.net_worth_cop, 'COP', privacyMode);
  const equivalent = currency === 'USD'
    ? money(netWorth.net_worth_cop, 'COP', privacyMode)
    : money(netWorth.net_worth_usd, 'USD', privacyMode);
  const changeMetric = understand?.what_changed.metrics?.net_cash_flow;
  const primaryCurrency = understand?.what_changed.primary_currency || currency;
  const hasTrajectory = dashboard.temporal_evolution.length > 1;
  const trajectory = hasTrajectory ? dashboard.temporal_evolution.map((point) => point.portfolio_usd) : undefined;
  const contributors = understand?.what_changed.category_contributors || understand?.what_changed.explain?.contributors || [];
  const attentionItems = financialInbox?.attention_items || [];
  const urgentAttention = attentionItems.filter((item) => item.severity === 'URGENT' || item.severity === 'ATTENTION');
  const watchAttention = attentionItems.filter((item) => item.severity === 'WATCH');
  const upcoming = financialInbox?.timeline ? timelineItems(financialInbox.timeline) : [];
  // Lista visible operativa del rail: única fuente para render y empty state.
  const visibleAttention = [...urgentAttention, ...watchAttention].slice(0, 6);
  // Nivel efectivo único de confianza: mismo fallback para state y title.
  const confidenceLevel = understand?.data_confidence?.level || understand?.what_changed?.data_confidence?.level;
  const confidenceKind = confidenceState(confidenceLevel);
  const confidenceTitle = confidenceKind === 'READY'
    ? 'Información disponible'
    : confidenceKind === 'PARTIAL' ? 'Información limitada' : 'Información insuficiente';

  const openAttention = (item: FinancialInboxResult['attention_items'][number]) => {
    setInspectorItem({
      title: item.title,
      summary: item.summary,
      evidence: [
        `Severidad: ${item.severity}`,
        `Fuente: ${item.source}`,
        item.effective_date ? `Fecha efectiva: ${item.effective_date}` : 'Sin fecha efectiva',
        ...(item.actions || []).slice(0, 2).map((action) => `Acción: ${action}`),
      ],
    });
  };

  const openChange = () => {
    const reasons = understand?.what_changed.explain?.reasons || understand?.what_changed.interpretation || [];
    setInspectorItem({
      title: 'Qué cambió',
      summary: 'Evidencia del periodo actual frente al periodo anterior.',
      evidence: reasons.length > 0 ? reasons.slice(0, 4) : ['No hay explicación detallada disponible para este periodo.'],
    });
  };

  return (
    <div className="a-enter">
      <div className="a-workspace mt-0">
        <section className="a-canvas">
          <HeroMetric
            label="Estado financiero"
            value={netWorthValue}
            context={`Patrimonio neto desde datos locales persistidos. Equivalente: ${equivalent}. Fuente: ${dataSource?.profile || dataSource?.mode || 'sin fuente activa'}.`}
            delta={changeMetric ? {
              label: money(changeMetric.delta, primaryCurrency, privacyMode),
              direction: deltaDirection(changeMetric.delta),
              detail: 'cashflow vs periodo anterior',
            } : undefined}
            trajectory={trajectory}
            trajectoryCaption="Evolución registrada del patrimonio; no se estiman puntos faltantes."
          />

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <InlineMetric
              label="Cashflow"
              value={money(changeMetric?.current ?? dashboard.cashflow?.cashflow, primaryCurrency, privacyMode)}
            />
            <InlineMetric
              label="Tasa de ahorro"
              value={`${dashboard.kpis.savings_rate.savings_rate_pct}%`}
              delta={understand?.what_changed.metrics?.savings_rate ? `${understand.what_changed.metrics.savings_rate.delta >= 0 ? '+' : ''}${understand.what_changed.metrics.savings_rate.delta} pp` : undefined}
              direction={deltaDirection(understand?.what_changed.metrics?.savings_rate?.delta)}
            />
            <InlineMetric
              label="Rendimiento"
              value={`TWR ${pct(dashboard.kpis.twr_pct)}`}
              delta={`MWR ${pct(dashboard.kpis.mwr_pct)}`}
              direction="analytical"
            />
          </div>

          <section className="mt-9 grid gap-5 lg:grid-cols-[1fr_0.68fr]">
            <section className="a-surface p-5" aria-labelledby="overview-changed-title">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 id="overview-changed-title" className="a-module-title">Qué cambió</h2>
                  <p className="a-meta mt-1">Cómo se compara este periodo con el anterior; la evidencia se abre bajo demanda.</p>
                </div>
                <Button variant="quiet" onClick={openChange}>Ver evidencia</Button>
              </div>
              <div className="mt-5 space-y-3">
                {contributors.slice(0, 5).map((item) => (
                  <div key={`${item.category}-${item.currency}`} className="flex items-center justify-between gap-3 border-b border-[var(--a-line)] pb-3 last:border-b-0">
                    <span className="min-w-0 truncate text-sm text-[var(--a-secondary)]">{item.category}</span>
                    <DeltaMetric value={money(item.delta, item.currency || primaryCurrency, privacyMode)} direction={deltaDirection(item.delta)} />
                  </div>
                ))}
                {contributors.length === 0 && <DataState state="EMPTY" title="Sin desglose por categoría" detail="Este periodo no incluye desglose por categoría." />}
              </div>
            </section>

            <section className="a-surface p-5" aria-labelledby="overview-state-title">
              <h2 id="overview-state-title" className="a-module-title">Estado de datos</h2>
              <div className="mt-4 grid gap-3">
                <DataState
                  state={confidenceKind}
                  title={confidenceTitle}
                  detail={(understand?.data_confidence?.reasons || understand?.what_changed?.data_confidence?.reasons || ['Se muestra lo disponible sin ocultar limitaciones.'])[0]}
                />
                <DataState
                  state={inboxState(financialInbox?.status)}
                  title="Financial Inbox"
                  detail={financialInbox ? `Horizonte evaluado: ${financialInbox.horizon_days} días.` : 'Sin bandeja cargada todavía.'}
                />
              </div>
            </section>
          </section>

          <section className="mt-5 grid gap-5 lg:grid-cols-[1fr_0.68fr]">
            <section className="a-surface p-5" aria-labelledby="overview-close-title">
              <h2 id="overview-close-title" className="a-module-title">Cierre del periodo</h2>
              {monthlyReview ? (
                <>
                  <p className="a-meta mt-1">{monthlyReview.period}</p>
                  <div className="mt-5 grid gap-3 sm:grid-cols-3">
                    <InlineMetric label="Ingresos" value={money(monthlyReview.facts.income, primaryCurrency, privacyMode)} direction="positive" />
                    <InlineMetric label="Gastos" value={money(monthlyReview.facts.expenses, primaryCurrency, privacyMode)} direction="negative" />
                    <InlineMetric label="Cierre estimado" value={money(monthlyReview.forecast.projected_balance, primaryCurrency, privacyMode)} direction="analytical" />
                  </div>
                </>
              ) : (
                <div className="mt-5">
                  <DataState state="EMPTY" title="Sin cierre de periodo" detail="El cierre mensual todavía no está disponible." />
                </div>
              )}
            </section>

            <section className="a-surface p-5" aria-labelledby="overview-upcoming-title">
              <h2 id="overview-upcoming-title" className="a-module-title">Próximo</h2>
              <p className="a-meta mt-1">Próximos eventos del Financial Inbox.</p>
              <div className="mt-5">
                {upcoming.length > 0 ? <Timeline items={upcoming} /> : <DataState state="EMPTY" title="Sin próximos eventos" detail="No hay eventos en el horizonte configurado." />}
              </div>
            </section>
          </section>
        </section>

        <aside className="a-elevated h-fit p-5" aria-labelledby="overview-attention-title">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 id="overview-attention-title" className="a-module-title">Attention</h2>
              <p className="a-meta mt-1">Asuntos del Financial Inbox, de mayor a menor severidad.</p>
            </div>
            <Info className="h-4 w-4 text-[var(--a-info)]" aria-hidden="true" />
          </div>

          {financialInbox && (financialInbox.summary.urgent_count + financialInbox.summary.attention_count + financialInbox.summary.watch_count) > 0 && (
            <p className="a-meta mt-3">
              {financialInbox.summary.urgent_count} urgentes · {financialInbox.summary.attention_count} en atención · {financialInbox.summary.watch_count} en seguimiento
            </p>
          )}

          <div className="mt-5 space-y-3">
            {visibleAttention.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => openAttention(item)}
                className="a-motion w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-3 text-left"
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${item.severity === 'URGENT' ? 'text-[var(--a-negative)]' : item.severity === 'ATTENTION' ? 'text-[var(--a-warning)]' : 'text-[var(--a-info)]'}`} aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">{severityLabel(item.severity)}</span>
                    <span className="mt-1 block text-xs font-bold text-[var(--a-text)]">{item.title}</span>
                    <span className="a-meta mt-1 block">{item.summary}</span>
                  </span>
                </div>
              </button>
            ))}
            {visibleAttention.length === 0 && <DataState state="EMPTY" title="Sin señales prioritarias" detail="Financial Inbox no reporta asuntos en este horizonte." />}
          </div>

          <p className="a-meta mt-5">Selecciona una señal o “Qué cambió” para ver la explicación y su evidencia.</p>
        </aside>
      </div>

      <Inspector item={inspectorItem} onClose={() => setInspectorItem(null)} />
    </div>
  );
}
