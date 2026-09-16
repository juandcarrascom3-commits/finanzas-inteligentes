import React, { useState } from 'react';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Portfolio from './pages/Portfolio';
import Markets from './pages/Markets';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import AiInsightModal from './components/modals/AiInsightModal';
import { 
  CalendarView, DcaSimulator, RiskRadar, Academy, 
  DiscoverView, WatchlistView, AllocationView, ExploreView 
} from './pages/Placeholders';

type Tab = 
  | 'dashboard' | 'portfolio' | 'markets' | 'analytics' | 'settings'
  | 'calendar' | 'dca' | 'risk' | 'academy'
  | 'discover' | 'watchlist' | 'allocation' | 'explore';

function renderPage(tab: Tab): React.ReactNode {
  switch (tab) {
    case 'dashboard':  return <Dashboard />;
    case 'portfolio':  return <Portfolio />;
    case 'markets':    return <Markets />;
    case 'analytics':  return <Analytics />;
    case 'settings':   return <Settings />;
    case 'calendar':   return <CalendarView />;
    case 'dca':        return <DcaSimulator />;
    case 'risk':       return <RiskRadar />;
    case 'academy':    return <Academy />;
    case 'discover':   return <DiscoverView />;
    case 'watchlist':  return <WatchlistView />;
    case 'allocation': return <AllocationView />;
    case 'explore':    return <ExploreView />;
    default:           return <Dashboard />;
  }
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <>
      <Layout
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab as Tab)}
        isSidebarCollapsed={isSidebarCollapsed}
        onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        onOpenAi={() => setIsAiModalOpen(true)}
        isAiOpen={isAiModalOpen}
      >
        {renderPage(activeTab)}
      </Layout>

      {/* AI Insight Modal */}
      <AiInsightModal
        isOpen={isAiModalOpen}
        onClose={() => setIsAiModalOpen(false)}
      />
    </>
  );
}

export default App;
