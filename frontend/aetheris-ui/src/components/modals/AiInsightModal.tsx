import React from 'react';

interface AiInsightModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const AiInsightModal: React.FC<AiInsightModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-[50] flex items-end sm:items-center justify-center p-4 bg-black/70 backdrop-blur-md"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-modal-title"
    >
      {/* Modal Panel */}
      <div className="glass-panel w-full max-w-md rounded-[32px] p-6 text-white border border-white/10 shadow-2xl relative">

        {/* Close button */}
        <button
          onClick={onClose}
          aria-label="Cerrar"
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-gray-400 hover:text-white transition"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M6 18 18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>

        {/* AI Badge */}
        <p className="text-[#38e1e7] text-xs font-bold tracking-widest uppercase mb-2 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#38e1e7] animate-pulse inline-block" />
          DESCUBRIR • IA RADAR
        </p>

        {/* Title */}
        <h2 id="ai-modal-title" className="text-xl font-bold tracking-tight text-white mb-2">
          Una ola de nuevos compradores está descubriendo NVDA
        </h2>

        {/* Description */}
        <p className="text-xs text-gray-400 mb-6 leading-relaxed">
          El volumen de compra de <span className="text-white font-medium">NVIDIA (NVDA)</span> ha
          aumentado un <span className="text-[#38e1e7] font-semibold">+340%</span> en las últimas 48h,
          impulsado principalmente por nuevos inversores. Los modelos cuantitativos de IA detectan
          un patrón de acumulación inusual con alta confianza.
        </p>

        {/* Metric: Compradores por primera vez */}
        <div className="mb-4">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-xs font-medium text-gray-300">Compradores por primera vez</span>
            <span className="text-xs font-bold text-[#38e1e7]">80%</span>
          </div>
          <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-2 bg-gradient-to-r from-[#38e1e7] to-[#2dd4bf] rounded-full"
              style={{ width: '80%' }}
            />
          </div>
        </div>

        {/* Metric: Volviendo */}
        <div className="mb-2">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-xs font-medium text-gray-300">Volviendo</span>
            <span className="text-xs font-bold text-gray-400">20%</span>
          </div>
          <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
            <div className="h-2 bg-white/10 rounded-full" style={{ width: '20%' }} />
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-[10px] text-gray-500 my-4 text-center">
          El capital está en riesgo. Información cuantitativa, no asesoramiento.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col gap-2">
          <button className="rounded-full bg-[#171920] hover:bg-[#20232b] border border-white/10 py-3 px-4 text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer w-full">
            <svg className="w-4 h-4 text-[#38e1e7]" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
              <path d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Visita la página de NVDA
          </button>

          <button className="rounded-full bg-[#171920] hover:bg-[#20232b] border border-white/10 py-3 px-4 text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer w-full">
            <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
              <path d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
                strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Añade NVDA a la lista de seguimiento
          </button>
        </div>
      </div>
    </div>
  );
};

export default AiInsightModal;

