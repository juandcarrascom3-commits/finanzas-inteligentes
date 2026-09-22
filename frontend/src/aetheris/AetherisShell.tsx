import React from 'react';
import { BarChart3, Compass, Database, LineChart, Menu, Target } from 'lucide-react';
import './tokens.css';

export type AetherisTab = 'overview' | 'plan' | 'invest' | 'datos';

interface AetherisShellProps {
  activeTab: AetherisTab;
  onSelectTab: (tab: AetherisTab) => void;
  header: React.ReactNode;
  children: React.ReactNode;
  sourceLabel?: string;
}

const navItems: Array<{ id: AetherisTab; label: string; description: string; icon: React.ElementType }> = [
  { id: 'overview', label: 'Overview', description: 'Estado financiero', icon: Compass },
  { id: 'plan', label: 'Plan', description: 'Presupuesto y calendario', icon: Target },
  { id: 'invest', label: 'Invest', description: 'Portafolio y ledger', icon: LineChart },
  { id: 'datos', label: 'Datos', description: 'Fuentes y control', icon: Database },
];

export function AetherisShell({ activeTab, onSelectTab, header, children, sourceLabel }: AetherisShellProps) {
  return (
    <div className="aetheris-lab min-h-screen">
      <div className="grid min-h-screen grid-cols-[260px_minmax(0,1fr)] max-[920px]:grid-cols-1">
        <aside className="border-r border-[var(--a-line)] bg-black/10 px-4 py-5 max-[920px]:border-b max-[920px]:border-r-0">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="a-page-kicker">Finance</div>
              <div className="mt-1 text-lg font-bold text-[var(--a-text)]">Aetheris 2.0</div>
            </div>
            <Menu className="h-5 w-5 text-[var(--a-muted)]" aria-hidden="true" />
          </div>

          <nav aria-label="Navegación principal" className="mt-8 grid gap-2 max-[920px]:mt-5 max-[920px]:grid-cols-4 max-[640px]:grid-cols-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectTab(item.id)}
                  className={`a-motion rounded-[16px] border px-3 py-3 text-left ${
                    active ? 'bg-white/[0.075]' : 'bg-transparent hover:bg-white/[0.035]'
                  }`}
                  style={{ borderColor: active ? 'var(--a-brand)' : 'transparent' }}
                  aria-current={active ? 'page' : undefined}
                >
                  <span className="flex items-center gap-3">
                    <Icon className="h-4 w-4 shrink-0" style={{ color: active ? 'var(--a-brand)' : 'var(--a-muted)' }} aria-hidden="true" />
                    <span className="min-w-0">
                      <span className="block text-sm font-bold text-[var(--a-text)]">{item.label}</span>
                      <span className="a-meta block truncate max-[640px]:hidden">{item.description}</span>
                    </span>
                  </span>
                </button>
              );
            })}
          </nav>

          <div className="a-surface mt-8 p-3 max-[920px]:hidden">
            <div className="flex items-center gap-2 text-xs font-bold text-[var(--a-text)]">
              <BarChart3 className="h-4 w-4 text-[var(--a-info)]" aria-hidden="true" />
              Fuente activa
            </div>
            <p className="a-meta mt-2">{sourceLabel || 'Sin información de fuente todavía.'}</p>
          </div>
        </aside>

        <div className="min-w-0">
          <div className="border-b border-[var(--a-line)] bg-[rgba(7,10,15,0.78)]">
            {header}
          </div>
          <main className="min-w-0 px-5 py-6 lg:px-8">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
