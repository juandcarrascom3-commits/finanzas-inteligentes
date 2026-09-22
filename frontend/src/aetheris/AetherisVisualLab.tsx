import React, { useState } from 'react';
import './tokens.css';
import { labFixture } from './labFixture';
import { AttentionSignal, DataState, HeroMetric, InlineMetric, Inspector, Timeline } from './primitives';

export function AetherisVisualLab() {
  const [selectedAttentionId, setSelectedAttentionId] = useState(labFixture.attention[0].id);
  const selectedAttention = labFixture.attention.find((item) => item.id === selectedAttentionId) || null;

  return (
    <div className="aetheris-lab">
      <div className="a-shell">
        <header>
          <div className="a-page-kicker">Aetheris 2.0 visual lab · example data</div>
          <h1 className="a-page-title">Calm Command Center</h1>
          <p className="a-page-subtitle">
            Vocabulario mínimo para una futura integración Overview-first: resumen, explicación, evidencia y datos crudos bajo demanda.
          </p>
        </header>

        <main className="a-workspace">
          <section className="a-canvas a-enter">
            <HeroMetric
              label={labFixture.label}
              context={labFixture.context}
              value={labFixture.value}
              delta={labFixture.delta}
              trajectory={labFixture.trajectory}
            />

            <div className="mt-8 grid gap-4 md:grid-cols-3">
              {labFixture.metrics.map((metric) => (
                <InlineMetric key={metric.label} {...metric} />
              ))}
            </div>

            <div className="mt-9 grid gap-5 lg:grid-cols-[1fr_0.72fr]">
              <section className="a-surface p-5">
                <div className="a-module-title">Qué cambió</div>
                <p className="a-meta mt-1">Lectura editorial primero; detalles debajo.</p>
                <div className="mt-5 space-y-3">
                  {labFixture.contributors.map((item) => (
                    <div key={item.label} className="flex items-center justify-between border-b border-[var(--a-line)] pb-3 last:border-b-0">
                      <span className="text-sm text-[var(--a-secondary)]">{item.label}</span>
                      <span className={`text-sm font-bold tabular-nums ${
                        item.tone === 'positive' ? 'text-[var(--a-positive)]' : item.tone === 'negative' ? 'text-[var(--a-negative)]' : 'text-[var(--a-analytical)]'
                      }`}>
                        {item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="a-surface p-5">
                <div className="a-module-title">Estados de datos</div>
                <p className="a-meta mt-1">Lenguaje humano sobre enums internos.</p>
                <div className="mt-4 grid gap-3">
                  {labFixture.dataStates.slice(0, 3).map((item) => (
                    <DataState key={item.state} {...item} />
                  ))}
                </div>
              </section>
            </div>

            <section className="mt-5 grid gap-5 lg:grid-cols-[1fr_0.72fr]">
              <div className="a-surface p-5">
                <div className="a-module-title">Cash trajectory</div>
                <p className="a-meta mt-1">La trayectoria queda integrada al contenido; no es un chart boxed.</p>
                <div className="mt-4 rounded-[18px] border border-[var(--a-line)] bg-black/10 p-4">
                  <HeroMetric
                    label="Balance proyectado"
                    context="Visual de laboratorio para probar jerarquía secundaria."
                    value="$14,800"
                    delta={{ label: '+$620', direction: 'positive', detail: 'rango ejemplo' }}
                    trajectory={[18, 21, 23, 22, 24, 27, 26, 30]}
                  />
                </div>
              </div>

              <div className="a-surface p-5">
                <div className="a-module-title">Upcoming</div>
                <p className="a-meta mt-1">Timeline compacto, editorial y legible.</p>
                <div className="mt-5">
                  <Timeline items={labFixture.timeline} />
                </div>
              </div>
            </section>
          </section>

          <aside className="a-elevated h-fit p-5">
            <div className="a-module-title">Attention</div>
            <p className="a-meta mt-1">Rail secundario: señales, salud de datos y resumen de inbox.</p>
            <div className="mt-5 space-y-3">
              {labFixture.attention.map((item) => (
                <AttentionSignal
                  key={item.id}
                  title={item.title}
                  summary={item.summary}
                  state={item.state}
                  selected={selectedAttentionId === item.id}
                  onSelect={() => setSelectedAttentionId(item.id)}
                />
              ))}
            </div>

            <div className="a-floating mt-5 rounded-[18px] border border-[var(--a-line)] p-4">
              <div className="a-module-title">Inbox summary</div>
              <p className="a-meta mt-1">1 requiere atención · 2 para revisar · 3 próximos eventos.</p>
            </div>
          </aside>
        </main>
      </div>

      <Inspector item={selectedAttention} onClose={() => setSelectedAttentionId('')} />
    </div>
  );
}

export default AetherisVisualLab;
