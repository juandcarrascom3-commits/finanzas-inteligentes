import React from 'react';
import { BarChart3, Compass, Database, LineChart, PanelLeftClose, PanelLeftOpen, Target } from 'lucide-react';

export type AetherisTab = 'overview' | 'plan' | 'invest' | 'datos';

interface NavItem {
  id: AetherisTab;
  label: string;
  description: string;
  icon: React.ElementType;
}

/**
 * Solo destinos reales de la app. No añadir entradas placeholder:
 * cada destino debe tener una pestaña con datos conectados detrás.
 */
const navItems: NavItem[] = [
  { id: 'overview', label: 'Overview', description: 'Estado financiero', icon: Compass },
  { id: 'plan', label: 'Plan', description: 'Presupuesto y calendario', icon: Target },
  { id: 'invest', label: 'Invest', description: 'Portafolio y ledger', icon: LineChart },
  { id: 'datos', label: 'Datos', description: 'Fuentes y control', icon: Database },
];

interface SidebarProps {
  activeTab: AetherisTab;
  onSelectTab: (tab: AetherisTab) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  sourceLabel?: string;
}

export function Sidebar({
  activeTab,
  onSelectTab,
  collapsed,
  onToggleCollapse,
  sourceLabel,
}: SidebarProps) {
  return (
    <aside className="border-r border-[var(--a-line)] bg-[var(--a-bg)] px-4 py-5 max-[920px]:border-b max-[920px]:border-r-0">
      <div className={`flex items-center gap-3 ${collapsed ? 'justify-center' : 'justify-between'}`}>
        {!collapsed && (
          <div className="min-w-0">
            <div className="a-page-kicker">Finance</div>
            <div className="mt-1 truncate text-lg font-bold text-[var(--a-text)]">Aetheris 2.0</div>
          </div>
        )}
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-expanded={!collapsed}
          aria-controls="a-sidebar-nav"
          aria-label={collapsed ? 'Expandir navegación lateral' : 'Colapsar navegación lateral'}
          title={collapsed ? 'Expandir navegación' : 'Colapsar navegación'}
          className="a-motion shrink-0 rounded-[12px] border border-[var(--a-line)] p-2 text-[var(--a-muted)] hover:border-[var(--a-line-strong)] hover:text-[var(--a-text)]"
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
          ) : (
            <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>

      <nav
        id="a-sidebar-nav"
        aria-label="Navegación principal"
        className="mt-8 grid gap-2 max-[920px]:mt-5 max-[920px]:grid-cols-4 max-[640px]:grid-cols-2"
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectTab(item.id)}
              aria-current={isActive ? 'page' : undefined}
              title={collapsed ? item.label : undefined}
              className={`a-motion flex items-center gap-3 rounded-[16px] border px-3 py-3 text-left ${
                collapsed ? 'justify-center px-0' : ''
              } ${isActive ? 'bg-[var(--a-active)]' : 'bg-transparent hover:bg-[var(--a-hover)]'}`}
              style={{ borderColor: isActive ? 'var(--a-brand)' : 'transparent' }}
            >
              <Icon
                className="h-4 w-4 shrink-0"
                style={{ color: isActive ? 'var(--a-brand)' : 'var(--a-muted)' }}
                aria-hidden="true"
              />
              {collapsed ? (
                <span className="sr-only">{item.label}</span>
              ) : (
                <span className="min-w-0">
                  <span className="block text-sm font-bold text-[var(--a-text)]">{item.label}</span>
                  <span className="a-meta block truncate max-[640px]:hidden">{item.description}</span>
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {!collapsed && (
        <div className="a-surface mt-8 p-3 max-[920px]:hidden">
          <div className="flex items-center gap-2 text-xs font-bold text-[var(--a-text)]">
            <BarChart3 className="h-4 w-4 text-[var(--a-info)]" aria-hidden="true" />
            Fuente activa
          </div>
          <p className="a-meta mt-2">{sourceLabel || 'Sin información de fuente todavía.'}</p>
        </div>
      )}
    </aside>
  );
}
