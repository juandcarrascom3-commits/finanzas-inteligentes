import React from 'react';

interface FloatingDockProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  onOpenAi: () => void;
  isAiOpen?: boolean;
}

const FloatingDock: React.FC<FloatingDockProps> = ({ activeTab, onSelectTab, onOpenAi, isAiOpen }) => {
  if (activeTab === 'dashboard') return null;

  const aiOrbBaseClass = "glass-panel w-12 h-12 rounded-full flex items-center justify-center cursor-pointer transition-all duration-300 relative";
  const aiOrbActiveStyles = "bg-[#2dd4bf]/40 border-[#38e1e7] shadow-[0_0_30px_rgba(56,225,231,0.7)] scale-110 ring-2 ring-[#38e1e7]/50";
  const aiOrbInactiveStyles = "bg-[#2dd4bf]/20 border border-[#38e1e7]/40 shadow-[0_0_15px_rgba(56,225,231,0.30)] hover:scale-105";

  return (
    <div className="absolute bottom-5 left-1/2 -translate-x-1/2 z-[60] flex items-center gap-3">
      {/* Container 1: Isolated AI Orb Button */}
      <button
        onClick={onOpenAi}
        aria-label="Chatear con IA"
        title="Pulsa para chatear con IA"
        className={`${aiOrbBaseClass} ${isAiOpen ? aiOrbActiveStyles : aiOrbInactiveStyles}`}
      >
        <span className="absolute inset-0 rounded-full bg-[#38e1e7]/10 animate-ping" />
        <svg className="w-6 h-6 text-[#38e1e7] relative z-10" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
          <path d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z"
            strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* Container 2: Main Capsule */}
      <div className="glass-panel rounded-full px-5 py-2.5 border border-white/10 flex items-center gap-4 shadow-2xl backdrop-blur-2xl">
        
        {/* Discover */}
        <button
          onClick={() => onSelectTab('discover')}
          aria-label="Discover"
          title="Descubrir"
          className={`p-2 rounded-full transition ${activeTab === 'discover' ? 'text-white bg-white/10' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.042 21.672 13.684 16.6m0 0-2.51 2.225.569-9.47 5.227 7.917-3.286-.672ZM12 2.25V4.5m5.834.166-1.591 1.591M20.25 10.5H18M7.757 14.743l-1.59 1.59M6 10.5H3.75m4.007-4.243-1.59-1.59" />
          </svg>
        </button>

        {/* Watchlist */}
        <button
          onClick={() => onSelectTab('watchlist')}
          aria-label="Watchlist"
          title="Watchlist"
          className={`p-2 rounded-full transition ${activeTab === 'watchlist' ? 'text-white bg-white/10' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
          </svg>
        </button>

        {/* Allocation */}
        <button
          onClick={() => onSelectTab('allocation')}
          aria-label="Allocation"
          title="Allocation"
          className={`p-2 rounded-full transition ${activeTab === 'allocation' ? 'text-white bg-white/10' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6a7.5 7.5 0 1 0 7.5 7.5h-7.5V6Z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5H21A7.5 7.5 0 0 0 13.5 3v7.5Z" />
          </svg>
        </button>

        {/* Explore */}
        <button
          onClick={() => onSelectTab('explore')}
          aria-label="Explore"
          title="Explorar"
          className={`p-2 rounded-full transition ${activeTab === 'explore' ? 'text-white bg-white/10' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
          </svg>
        </button>

      </div>
    </div>
  );
};

export default FloatingDock;
