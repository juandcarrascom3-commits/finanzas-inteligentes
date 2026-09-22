import React, { useState } from 'react';
import { AlertTriangle, Eye, Info } from 'lucide-react';
import { DashboardSummary, DataSourceInfo, FinancialInboxResult, MonthlyReview, TimelineItem, UnderstandSummary } from '../types';
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
  if (level === 'LOW') return 'PARTIAL';
  return 'UNEVALUABLE';
};

const inboxState = (status?: string): DataStateKind => {
  if (status === 'READY') return 'READY';
  if (status === 'EMPTY') return 'EMPTY';
  if (status === 'PARTIAL') return 'PARTIAL';
  return 'UNEVALUABLE';
};

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
      summary: 'Evidencia canónica del periodo actual frente al periodo anterior.',
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
            trajectoryCaption="Serie temporal canónica del dashboard; no se interpolan puntos."
          />

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <InlineMetric
              label="Cashflow"
              value={money(changeMetric?.current ?? dashboard.cashflow?.cashflow, primaryCurrency, privacyMode)}
              delta={changeMetric ? money(changeMetric.delta, primaryCurrency, privacyMode) : undefined}
              direction={deltaDirection(changeMetric?.delta)}
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
            <div className="a-surface p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="a-module-title">Qué cambió</h2>
                  <p className="a-meta mt-1">Comparación canónica del periodo; la explicación se abre bajo demanda.</p>
                </div>
                <button type="button" onClick={openChange} className="a-motion rounded-full border border-[var(--a-line)] px-3 py-1.5 text-xs text-[var(--a-secondary)]">
                  Ver evidencia
                </button>
              </div>
              <div className="mt-5 space-y-3">
                {contributors.slice(0, 5).map((item) => (
                  <div key={`${item.category}-${item.currency}`} className="flex items-center justify-between gap-3 border-b border-[var(--a-line)] pb-3 last:border-b-0">
                    <span className="min-w-0 truncate text-sm text-[var(--a-secondary)]">{item.category}</span>
                    <DeltaMetric value={money(item.delta, item.currency || primaryCurrency, privacyMode)} direction={deltaDirection(item.delta)} />
                  </div>
                ))}
                {contributors.length === 0 && <DataState state="EMPTY" title="Sin contribuciones destacadas" detail="El backend no devolvió contributors para este periodo." />}
              </div>
            </div>

            <div className="a-surface p-5">
              <h2 className="a-module-title">Estado de datos</h2>
              <div className="mt-4 grid gap-3">
                <DataState
                  state={confidenceState(understand?.data_confidence?.level || understand?.what_changed.data_confidence?.level)}
                  title={understand?.data_confidence?.level === 'HIGH' ? 'Información disponible' : 'Información limitada'}
                  detail={(understand?.data_confidence?.reasons || understand?.what_changed.data_confidence?.reasons || ['Se muestra lo disponible sin ocultar limitaciones.'])[0]}
                />
                <DataState
                  state={inboxState(financialInbox?.status)}
                  title="Financial Inbox"
                  detail={financialInbox ? `${financialInbox.summary.urgent_count} urgentes · ${financialInbox.summary.attention_count} atención · ${financialInbox.summary.watch_count} watch` : 'Sin inbox cargado todavía.'}
                />
              </div>
            </div>
          </section>

          <section className="mt-5 grid gap-5 lg:grid-cols-[1fr_0.68fr]">
            <div className="a-surface p-5">
              <h2 className="a-module-title">Cash / trayectoria principal</h2>
              {hasTrajectory ? (
                <p className="a-meta mt-1">Se usa la serie real `dashboard.temporal_evolution` como vista temporal primaria.</p>
              ) : (
                <DataState state="UNEVALUABLE" title="Sin serie temporal suficiente" detail="No se fabrica trayectoria cuando el backend no entrega puntos reales." />
              )}
              {monthlyReview && (
                <div className="mt-5 grid gap-3 sm:grid-cols-3">
                  <InlineMetric label="Ingresos" value={money(monthlyReview.facts.income, primaryCurrency, privacyMode)} direction="positive" />
                  <InlineMetric label="Gastos" value={money(monthlyReview.facts.expenses, primaryCurrency, privacyMode)} direction="negative" />
                  <InlineMetric label="Cierre estimado" value={money(monthlyReview.forecast.projected_balance, primaryCurrency, privacyMode)} direction="analytical" />
                </div>
              )}
            </div>

            <div className="a-surface p-5">
              <h2 className="a-module-title">Próximo</h2>
              <p className="a-meta mt-1">Timeline canónico del Financial Inbox.</p>
              <div className="mt-5">
                {upcoming.length > 0 ? <Timeline items={upcoming} /> : <DataState state="EMPTY" title="Sin próximos eventos" detail="No hay eventos en el horizonte configurado." />}
              </div>
            </div>
          </section>
        </section>

        <aside className="a-elevated h-fit p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="a-module-title">Attention</h2>
              <p className="a-meta mt-1">Severidades canónicas del Financial Inbox.</p>
            </div>
            <Info className="h-4 w-4 text-[var(--a-info)]" aria-hidden="true" />
          </div>

          <div className="mt-5 space-y-3">
            {[...urgentAttention, ...watchAttention].slice(0, 6).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => openAttention(item)}
                className="a-motion w-full rounded-[15px] border border-[var(--a-line)] bg-black/10 p-3 text-left"
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${item.severity === 'URGENT' ? 'text-[var(--a-negative)]' : item.severity === 'ATTENTION' ? 'text-[var(--a-warning)]' : 'text-[var(--a-info)]'}`} aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block text-[10px] font-bold uppercase tracking-wide text-[var(--a-muted)]">{item.severity}</span>
                    <span className="mt-1 block text-xs font-bold text-[var(--a-text)]">{item.title}</span>
                    <span className="a-meta mt-1 block">{item.summary}</span>
                  </span>
                </div>
              </button>
            ))}
            {attentionItems.length === 0 && <DataState state="EMPTY" title="Sin señales prioritarias" detail="Financial Inbox no reporta asuntos en este horizonte." />}
          </div>

          <div className="a-floating mt-5 rounded-[18px] border border-[var(--a-line)] p-4">
            <div className="flex items-center gap-2 text-xs font-bold text-[var(--a-text)]">
              <Eye className="h-4 w-4 text-[var(--a-info)]" aria-hidden="true" />
              Disclosures
            </div>
            <p className="a-meta mt-2">Selecciona una señal o “Qué cambió” para ver explicación y evidencia, sin traer datos crudos al Overview.</p>
          </div>
        </aside>
      </div>

      <Inspector item={inspectorItem} onClose={() => setInspectorItem(null)} />
    </div>
  );
}
