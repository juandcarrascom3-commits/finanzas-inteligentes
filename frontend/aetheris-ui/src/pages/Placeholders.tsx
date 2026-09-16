import React from 'react';

const PlaceholderView: React.FC<{ title: string }> = ({ title }) => (
  <div className="h-full overflow-y-auto p-6 md:p-8 space-y-6 custom-scrollbar flex items-center justify-center">
    <div className="glass-panel relative z-10 w-full max-w-2xl mx-auto rounded-[32px] p-8 flex flex-col items-center justify-center text-center shadow-2xl min-h-[300px]">
      <h2 className="text-2xl font-medium tracking-tight text-white mb-2">{title}</h2>
      <p className="text-sm text-[#38e1e7] font-medium uppercase tracking-widest">Próximamente</p>
    </div>
  </div>
);

export const CalendarView = () => <PlaceholderView title="Calendario Económico" />;
export const DcaSimulator = () => <PlaceholderView title="Simulador DCA" />;
export const RiskRadar = () => <PlaceholderView title="Radar de Riesgo" />;
export const Academy = () => <PlaceholderView title="Academia Fintech" />;
export const DiscoverView = () => <PlaceholderView title="Descubrir" />;
export const WatchlistView = () => <PlaceholderView title="Watchlist" />;
export const AllocationView = () => <PlaceholderView title="Asignación (Allocation)" />;
export const ExploreView = () => <PlaceholderView title="Explorar" />;
