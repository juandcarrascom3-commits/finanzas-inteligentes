import React from 'react';

export interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

interface ToolItem {
  id: string;
  label: string;
  emoji: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: (
      <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
        <rect height="8" rx="2" width="8" x="3" y="3" />
        <rect height="8" rx="2" width="8" x="13" y="3" />
        <rect height="8" rx="2" width="8" x="3" y="13" />
        <rect height="8" rx="2" width="8" x="13" y="13" />
      </svg>
    ),
  },
  {
    id: 'portfolio',
    label: 'Portfolio',
    icon: (
      <svg className="w-5 h-5 flex-shrink-0 stroke-current fill-none stroke-2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
        <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4" />
        <path d="M3 5v14a2 2 0 0 0 2 2h16v-5" />
        <path d="M18 12a2 2 0 0 0 0 4h4v-4Z" />
      </svg>
    ),
  },
  {
    id: 'markets',
    label: 'Markets',
    icon: (
      <svg className="w-5 h-5 flex-shrink-0 stroke-current fill-none stroke-2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
        <polyline points="17 6 23 6 23 12" />
      </svg>
    ),
  },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: (
      <svg className="w-5 h-5 flex-shrink-0 stroke-current fill-none stroke-2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
        <line x1="18" x2="18" y1="20" y2="10" />
        <line x1="12" x2="12" y1="20" y2="4" />
        <line x1="6" x2="6" y1="20" y2="14" />
      </svg>
    ),
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: (
      <svg className="w-5 h-5 flex-shrink-0 stroke-current fill-none stroke-2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
];

const TOOLS: ToolItem[] = [
  { id: 'calendar', label: 'Calendario\nEcon.', emoji: '📅' },
  { id: 'dca', label: 'Simulador\nDCA', emoji: '🔁' },
  { id: 'risk', label: 'Radar de\nRiesgo', emoji: '🛡️' },
  { id: 'academy', label: 'Academia\nFintech', emoji: '🎓' },
];

const Sidebar: React.FC<SidebarProps> = ({ activeTab, onSelectTab, isCollapsed, onToggleCollapse }) => {
  return (
    <aside
      className={`${isCollapsed ? 'w-20' : 'w-64'} flex-shrink-0 bg-[#0e1015] border-r border-white/5 flex flex-col py-6 px-4 select-none z-20 overflow-y-auto transition-all duration-300 ease-in-out custom-scrollbar`}
      data-purpose="main-sidebar"
    >
      <div className="flex-1 space-y-8">
        {/* Brand Logo - clickable to toggle */}
        <div 
          className={`flex items-center ${isCollapsed ? 'justify-center' : 'gap-3 px-3'} cursor-pointer`}
          onClick={onToggleCollapse}
          title="Toggle Sidebar"
        >
          <div aria-hidden="true" className="w-6 h-6 flex-shrink-0 flex flex-col justify-between py-0.5">
            <div className="w-full h-2 bg-white rounded-sm" />
            <div className="w-3/5 h-2 bg-white rounded-sm" />
          </div>
          {!isCollapsed && (
            <span className="text-white font-bold tracking-wider text-base uppercase whitespace-nowrap overflow-hidden">
              FINTECH PRO
            </span>
          )}
        </div>

        {/* Navigation Menu */}
        <nav aria-label="Main Navigation" className="space-y-1.5">
          {NAV_ITEMS.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={[
                  'w-full flex items-center py-3 rounded-xl font-medium text-sm transition duration-150 text-left',
                  isCollapsed ? 'justify-center px-0' : 'gap-3 px-3.5',
                  isActive
                    ? 'bg-[#1d1f27] text-white'
                    : 'text-gray-400 hover:text-white hover:bg-white/5',
                ].join(' ')}
                aria-current={isActive ? 'page' : undefined}
              >
                {item.icon}
                {!isCollapsed && <span className="whitespace-nowrap overflow-hidden">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Tools Section */}
        <div>
          {!isCollapsed && (
            <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1 mb-3">
              Herramientas
            </p>
          )}
          <div className={isCollapsed ? 'flex flex-col gap-2' : 'grid grid-cols-2 gap-2'}>
            {TOOLS.map((tool) => (
              <button
                key={tool.id}
                onClick={() => onSelectTab(tool.id)}
                title={isCollapsed ? tool.label.replace('\n', ' ') : undefined}
                className={`bg-white/[0.02] hover:bg-white/[0.06] border border-white/5 rounded-xl transition group flex flex-col ${isCollapsed ? 'items-center justify-center p-3' : 'p-3 text-left'}`}
                aria-label={tool.label.replace('\n', ' ')}
              >
                <span className={`text-lg leading-none block ${isCollapsed ? '' : 'mb-1.5'}`}>{tool.emoji}</span>
                {!isCollapsed && (
                  <span className="text-[11px] font-medium text-gray-400 group-hover:text-gray-200 transition leading-tight whitespace-pre-line">
                    {tool.label}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Bottom: Add Funds CTA ────────────── */}
      <div className="mt-6 pt-5 border-t border-white/5 flex justify-center">
        <button 
          title="Añadir Fondos"
          className={`bg-[#2dd4bf] text-black font-bold py-3 rounded-full hover:bg-[#38e1e7] transition shadow-lg text-xs uppercase tracking-wider text-center flex items-center justify-center ${isCollapsed ? 'w-10 h-10 p-0' : 'w-full'}`}
        >
          {isCollapsed ? '+' : '+ Añadir Fondos'}
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
