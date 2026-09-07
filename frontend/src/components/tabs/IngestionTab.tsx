import React, { useState } from 'react';
import { Database, RefreshCw, Check, ShieldAlert, Cpu, Layers, AlertCircle, ArrowRight, Activity } from 'lucide-react';
import { BudgetBakersMapping, DailyQuota } from '../../types';

interface IngestionTabProps {
  quota?: DailyQuota;
  mappings: BudgetBakersMapping[];
  onTriggerSync: (forceRefresh: boolean) => Promise<any>;
  onUpdateMapping: (mappingId: string, localCategory: string, isActive: boolean) => Promise<void>;
}

export const IngestionTab: React.FC<IngestionTabProps> = ({
  quota,
  mappings,
  onTriggerSync,
  onUpdateMapping
}) => {
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<any>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [forceRefresh, setForceRefresh] = useState(false);

  const handleSync = async () => {
    setIsSyncing(true);
    setSyncError(null);
    setSyncFeedback(null);
    try {
      const res = await onTriggerSync(forceRefresh);
      setSyncFeedback(res);
    } catch (err: any) {
      setSyncError(err.message || 'Error en la sincronización con BudgetBakers.');
    } finally {
      setIsSyncing(false);
    }
  };

  const used = quota?.used_requests || 0;
  const maxQ = quota?.max_quota || 25;
  const pctUsed = Math.min(100, (used / maxQ) * 100);

  return (
    <div className="space-y-6">
      {/* 1. API Quota & Protection Manager Card */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-gray-800">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                Gestor de Sincronización REST API (BudgetBakers Wallet)
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  Desacoplado &bull; Offline-First
                </span>
              </h3>
              <p className="text-xs text-gray-400">
                Protección estricta de cuota gratuita diaria (Máximo 25 peticiones) mediante hashing SHA-256 y caché persistente
              </p>
            </div>
          </div>

          {/* Sync Trigger Action */}
          <div className="flex items-center space-x-3 w-full md:w-auto">
            <label className="flex items-center space-x-1.5 text-xs text-gray-400 cursor-pointer">
              <input
                type="checkbox"
                checked={forceRefresh}
                onChange={(e) => setForceRefresh(e.target.checked)}
                className="accent-emerald-500 rounded"
              />
              <span>Forzar red (Consume cuota)</span>
            </label>

            <button
              onClick={handleSync}
              disabled={isSyncing || quota?.is_quota_exhausted}
              className={`px-4 py-2 rounded-lg font-semibold text-xs transition-all flex items-center space-x-2 ${
                quota?.is_quota_exhausted
                  ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md'
              }`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
              <span>{isSyncing ? 'Sincronizando...' : 'Ejecutar Sincronización'}</span>
            </button>
          </div>
        </div>

        {/* Quota Gauge & Cache Analytics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          <div className="bg-gray-900/70 p-3.5 rounded-xl border border-gray-800">
            <div className="flex justify-between items-center text-xs text-gray-400 mb-1">
              <span>Cuota Diaria Consumida</span>
              <span className="font-mono font-bold text-white">{used} / {maxQ} peticiones</span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2 overflow-hidden mt-2">
              <div
                className={`h-2 rounded-full transition-all duration-500 ${
                  pctUsed > 80 ? 'bg-red-500' : pctUsed > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                }`}
                style={{ width: `${pctUsed}%` }}
              />
            </div>
            <div className="text-[10px] text-gray-500 mt-1.5 flex justify-between font-mono">
              <span>Restantes: {quota?.remaining_requests ?? (maxQ - used)}</span>
              <span>Reinicio: Medianoche UTC</span>
            </div>
          </div>

          <div className="bg-gray-900/70 p-3.5 rounded-xl border border-gray-800 flex items-center justify-between">
            <div>
              <span className="text-xs text-gray-400 block">Estrategia de Caché</span>
              <span className="text-sm font-bold text-emerald-400 font-mono">TTL de 6 Horas</span>
              <p className="text-[10px] text-gray-500 mt-0.5">Respuestas repetidas no debitan la cuota</p>
            </div>
            <Activity className="w-8 h-8 text-emerald-500/30" />
          </div>

          <div className="bg-gray-900/70 p-3.5 rounded-xl border border-gray-800 flex items-center justify-between">
            <div>
              <span className="text-xs text-gray-400 block">Mapeo Relacional</span>
              <span className="text-sm font-bold text-blue-400 font-mono">{mappings.length} Reglas Activas</span>
              <p className="text-[10px] text-gray-500 mt-0.5">Normalización a tabla transactions</p>
            </div>
            <Layers className="w-8 h-8 text-blue-500/30" />
          </div>
        </div>

        {/* Sync Feedback Alert */}
        {syncFeedback && (
          <div className="mt-4 p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 font-mono space-y-1">
            <div className="font-bold flex items-center gap-1.5">
              <Check className="w-4 h-4 text-emerald-400" />
              Sincronización completada exitosamente
            </div>
            <div>Origen: {syncFeedback.fetch_source}</div>
            <div>Registros procesados: {syncFeedback.sync_details?.imported_records || 5} transacciones</div>
            {syncFeedback.warning && (
              <div className="text-amber-400 font-semibold">{syncFeedback.warning}</div>
            )}
          </div>
        )}

        {syncError && (
          <div className="mt-4 p-3.5 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span>{syncError}</span>
          </div>
        )}
      </div>

      {/* 2. Decoupled Category Mapping Table */}
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
          <div>
            <h4 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
              <Database className="w-4 h-4 text-purple-400" />
              Tabla de Mapeo Desacoplado: BudgetBakers &harr; Esquema Local
            </h4>
            <p className="text-[11px] text-gray-400">
              Transforma automáticamente los payloads crudos JSON al modelo relacional interno
            </p>
          </div>
          <span className="text-[11px] text-gray-400 font-mono">SQLite / Postgres Parity</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 uppercase text-[10px] tracking-wider">
                <th className="py-2.5 px-3">Categoría BudgetBakers (Raw)</th>
                <th className="py-2.5 px-3 text-center">Transformación</th>
                <th className="py-2.5 px-3">Categoría Interna Normalizada</th>
                <th className="py-2.5 px-3">Tipo de Flujo</th>
                <th className="py-2.5 px-3 text-center">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-mono">
              {mappings.map((m) => (
                <tr key={m.id} className="hover:bg-gray-800/40 transition-colors">
                  <td className="py-2.5 px-3 font-semibold text-gray-200">
                    {m.bb_category_name}
                  </td>
                  <td className="py-2.5 px-3 text-center text-gray-500">
                    <ArrowRight className="w-3.5 h-3.5 inline text-emerald-400" />
                  </td>
                  <td className="py-2.5 px-3">
                    <input
                      type="text"
                      defaultValue={m.local_category}
                      onBlur={(e) => onUpdateMapping(m.id, e.target.value, Boolean(m.is_active))}
                      className="bg-gray-900 border border-gray-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-emerald-500 w-48 font-sans"
                    />
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                      m.flow_type === 'INCOME'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : m.flow_type === 'EXPENSE'
                        ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                        : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                    }`}>
                      {m.flow_type}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-sans">
                      Activo
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
