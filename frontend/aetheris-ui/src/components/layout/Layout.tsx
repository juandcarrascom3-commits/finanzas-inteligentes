import React from 'react';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import FloatingDock from './FloatingDock';

interface LayoutProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  isSidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onOpenAi: () => void;
  isAiOpen: boolean;
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ 
  activeTab, 
  onSelectTab, 
  isSidebarCollapsed, 
  onToggleSidebar, 
  onOpenAi,
  isAiOpen,
  children 
}) => {
  return (
    <div className="text-gray-200 antialiased h-screen flex overflow-hidden selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Left Sidebar */}
      <Sidebar 
        activeTab={activeTab} 
        onSelectTab={onSelectTab} 
        isCollapsed={isSidebarCollapsed} 
        onToggleCollapse={onToggleSidebar} 
      />

      {/* Main Content Wrapper */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#0b0c11] relative overflow-hidden transition-all duration-300">
        {/* Top Navigation Bar */}
        <TopBar />

        {/* Page Content Area */}
        <main className="flex-1 relative overflow-hidden flex flex-col">
          {children}
        </main>
        
        {/* Floating Dock alongside main */}
        <FloatingDock 
          activeTab={activeTab}
          onSelectTab={onSelectTab}
          onOpenAi={onOpenAi}
          isAiOpen={isAiOpen}
        />
      </div>
    </div>
  );
};

export default Layout;
