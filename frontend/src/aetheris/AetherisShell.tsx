import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import type { AetherisTab } from './Sidebar';
import './tokens.css';

export type { AetherisTab } from './Sidebar';

interface AetherisShellProps {
  activeTab: AetherisTab;
  onSelectTab: (tab: AetherisTab) => void;
  header: React.ReactNode;
  children: React.ReactNode;
  sourceLabel?: string;
  /**
   * Slot estructural para acciones de chrome (F1+). Opcional y no renderizado
   * mientras no reciba contenido: nunca debe mostrar UI vacía ni placeholder.
   */
  actions?: React.ReactNode;
}

export function AetherisShell({
  activeTab,
  onSelectTab,
  header,
  children,
  sourceLabel,
  actions,
}: AetherisShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="aetheris-lab min-h-screen">
      <div className="a-shell-grid" data-collapsed={sidebarCollapsed ? 'true' : 'false'}>
        <Sidebar
          activeTab={activeTab}
          onSelectTab={onSelectTab}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((value) => !value)}
          sourceLabel={sourceLabel}
        />

        <div className="min-w-0">
          <div className="border-b border-[var(--a-line)] bg-[var(--a-chrome-bg)]">
            {header}
            {actions}
          </div>
          <main className="min-w-0 px-5 py-6 lg:px-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
