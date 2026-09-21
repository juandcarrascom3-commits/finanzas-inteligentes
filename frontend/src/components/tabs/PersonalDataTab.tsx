import React, { useEffect, useState } from 'react';
import { Account, Asset, BackupResult, BackupValidation, BudgetBakersPreview, BudgetBakersStatus, Category, CsvImportResult, DataSourceInfo, EtoroPreview, EtoroStatus, ReconciliationSummary, SourceMapping, Transaction } from '../../types';

interface PersonalDataTabProps {
  accounts: Account[];
  assets: Asset[];
  transactions: Transaction[];
  categories: Category[];
  dataSource?: DataSourceInfo;
  onSaveAccount: (account: Partial<Account>) => Promise<void>;
  onDeleteAccount: (id: string) => Promise<void>;
  onSaveAsset: (asset: Partial<Asset>) => Promise<void>;
  onDeleteAsset: (ticker: string) => Promise<void>;
  onSaveTransaction: (transaction: Partial<Transaction>) => Promise<void>;
  onDeleteTransaction: (id: string) => Promise<void>;
  onPreviewCsv: (content: string) => Promise<CsvImportResult>;
  onImportCsv: (content: string) => Promise<CsvImportResult>;
  onBackup: () => Promise<BackupResult>;
  onValidateBackup: (path: string) => Promise<BackupValidation>;
  onRestoreBackup: (path: string) => Promise<BackupResult>;
  onFetchWalletStatus: () => Promise<BudgetBakersStatus>;
  onTestWallet: () => Promise<unknown>;
  onPreviewWallet: () => Promise<BudgetBakersPreview>;
  onImportWallet: (preview: BudgetBakersPreview) => Promise<BudgetBakersPreview>;
  onFetchEtoroStatus: () => Promise<EtoroStatus>;
  onTestEtoro: () => Promise<unknown>;
  onPreviewEtoro: () => Promise<EtoroPreview>;
  onImportEtoro: (preview: EtoroPreview) => Promise<EtoroPreview>;
  onFetchReconciliation: () => Promise<ReconciliationSummary>;
  onSaveSourceMapping: (mapping: SourceMapping) => Promise<SourceMapping>;
  privacyMode: boolean;
}

const inputClass = "bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500";

export const PersonalDataTab: React.FC<PersonalDataTabProps> = ({
  accounts,
  assets,
  transactions,
  categories,
  dataSource,
  onSaveAccount,
  onDeleteAccount,
  onSaveAsset,
  onDeleteAsset,
  onSaveTransaction,
  onDeleteTransaction,
  onPreviewCsv,
  onImportCsv,
  onBackup,
  onValidateBackup,
  onRestoreBackup,
  onFetchWalletStatus,
  onTestWallet,
  onPreviewWallet,
  onImportWallet,
  onFetchEtoroStatus,
  onTestEtoro,
  onPreviewEtoro,
  onImportEtoro,
  onFetchReconciliation,
  onSaveSourceMapping,
  privacyMode
}) => {
  const [accountForm, setAccountForm] = useState<Partial<Account>>({ name: '', account_type: 'cash', currency: 'USD', opening_balance: 0, current_balance: 0 });
  const [assetForm, setAssetForm] = useState<Partial<Asset>>({ ticker: '', name: '', asset_type: 'Renta Variable', sector: 'General', country: 'Global', quantity: 0, avg_price: 0, current_price: 0, currency: 'USD' });
  const [txForm, setTxForm] = useState<Partial<Transaction>>({ date: new Date().toISOString().slice(0, 10), amount: 0, category: 'General', currency: 'USD', description: '' });
  const [csvText, setCsvText] = useState('');
  const [csvResult, setCsvResult] = useState<CsvImportResult | null>(null);
  const [walletStatus, setWalletStatus] = useState<BudgetBakersStatus | null>(null);
  const [walletPreview, setWalletPreview] = useState<BudgetBakersPreview | null>(null);
  const [etoroStatus, setEtoroStatus] = useState<EtoroStatus | null>(null);
  const [etoroPreview, setEtoroPreview] = useState<EtoroPreview | null>(null);
  const [reconciliation, setReconciliation] = useState<ReconciliationSummary | null>(null);
  const [backupPath, setBackupPath] = useState('');
  const [walletBusy, setWalletBusy] = useState(false);
  const [etoroBusy, setEtoroBusy] = useState(false);
  const [feedback, setFeedback] = useState<string>('');

  useEffect(() => {
    onFetchWalletStatus().then(setWalletStatus).catch((err) => setFeedback(err.message));
    onFetchEtoroStatus().then(setEtoroStatus).catch(() => undefined);
    onFetchReconciliation().then(setReconciliation).catch(() => undefined);
  }, [onFetchWalletStatus, onFetchEtoroStatus]);

  const money = (value: number) => privacyMode ? '••••' : value.toLocaleString();

  const submitAccount = async () => {
    await onSaveAccount(accountForm);
    setAccountForm({ name: '', account_type: 'cash', currency: 'USD', opening_balance: 0, current_balance: 0 });
  };

  const submitAsset = async () => {
    await onSaveAsset(assetForm);
    setAssetForm({ ticker: '', name: '', asset_type: 'Renta Variable', sector: 'General', country: 'Global', quantity: 0, avg_price: 0, current_price: 0, currency: 'USD' });
  };

  const submitTransaction = async () => {
    await onSaveTransaction(txForm);
    setTxForm({ date: new Date().toISOString().slice(0, 10), amount: 0, category: 'General', currency: 'USD', description: '' });
  };

  const handleFile = async (file?: File) => {
    if (!file) return;
    const text = await file.text();
    setCsvText(text);
    setCsvResult(await onPreviewCsv(text));
  };

  const backup = async () => {
    const result = await onBackup();
    if (result?.db_backup_path) setBackupPath(result.db_backup_path);
    setFeedback(`Backup generado: ${result?.db_backup_path || 'export listo'}`);
  };

  const validateBackup = async () => {
    const result = await onValidateBackup(backupPath);
    setFeedback(`Backup valido: version ${result.latest_version || 'sin version'} · ${result.tables.length} tablas.`);
  };

  const restoreBackup = async () => {
    if (!backupPath) return;
    if (!window.confirm('Restaurar reemplazara la base local actual. Se creara una copia antes de restaurar.')) return;
    const result = await onRestoreBackup(backupPath);
    setFeedback(`Backup restaurado. Copia previa: ${result.pre_restore_backup_path || 'no creada'}`);
  };

  const runWalletTest = async () => {
    setWalletBusy(true);
    try {
      await onTestWallet();
      setWalletStatus(await onFetchWalletStatus());
      setFeedback('Wallet conectado correctamente.');
    } catch (err: any) {
      setFeedback(err.message);
      setWalletStatus(await onFetchWalletStatus().catch(() => null));
    } finally {
      setWalletBusy(false);
    }
  };

  const previewWallet = async () => {
    setWalletBusy(true);
    try {
      const preview = await onPreviewWallet();
      setWalletPreview(preview);
      setFeedback('Preview de Wallet listo. Revise los conteos antes de importar.');
    } catch (err: any) {
      setFeedback(err.message);
    } finally {
      setWalletBusy(false);
    }
  };

  const importWallet = async () => {
    if (!walletPreview) return;
    setWalletBusy(true);
    try {
      const result = await onImportWallet(walletPreview);
      setWalletPreview(result);
      setWalletStatus(await onFetchWalletStatus());
      setReconciliation(await onFetchReconciliation());
      setFeedback(`Wallet importado: ${result.imported_count ?? 0} transacciones nuevas.`);
    } catch (err: any) {
      setFeedback(err.message);
    } finally {
      setWalletBusy(false);
    }
  };

  const runEtoroTest = async () => {
    setEtoroBusy(true);
    try {
      await onTestEtoro();
      setEtoroStatus(await onFetchEtoroStatus());
      setFeedback('eToro conectado en modo solo lectura.');
    } catch (err: any) {
      setFeedback(err.message);
      setEtoroStatus(await onFetchEtoroStatus().catch(() => null));
    } finally {
      setEtoroBusy(false);
    }
  };

  const previewEtoro = async () => {
    setEtoroBusy(true);
    try {
      const preview = await onPreviewEtoro();
      setEtoroPreview(preview);
      setFeedback('Preview de eToro listo. Revise mappings, CFDs y diferencias antes de importar.');
    } catch (err: any) {
      setFeedback(err.message);
    } finally {
      setEtoroBusy(false);
    }
  };

  const importEtoro = async () => {
    if (!etoroPreview) return;
    setEtoroBusy(true);
    try {
      const result = await onImportEtoro(etoroPreview);
      setEtoroPreview({ ...etoroPreview, ...result });
      setEtoroStatus(await onFetchEtoroStatus());
      setFeedback(`eToro importado: ${result.imported_count ?? 0} operaciones nuevas; ${result.updated_count ?? 0} actualizadas.`);
    } catch (err: any) {
      setFeedback(err.message);
    } finally {
      setEtoroBusy(false);
    }
  };

  const saveAccountMapping = async (externalId: string, externalName: string, localId: string) => {
    await onSaveSourceMapping({ source: 'BUDGETBAKERS', external_type: 'account', external_id: externalId, external_name: externalName, local_id: localId, local_type: 'account', is_active: true });
    setReconciliation(await onFetchReconciliation());
  };

  const saveCategoryMapping = async (externalName: string, localName: string) => {
    await onSaveSourceMapping({ source: 'BUDGETBAKERS', external_type: 'category', external_id: externalName, external_name: externalName, local_id: localName, local_type: 'category', is_active: true });
    setReconciliation(await onFetchReconciliation());
  };

  return (
    <div className="space-y-5">
      <div className="bg-[#111827] border border-gray-800 rounded-xl p-4 text-xs text-gray-300 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
        <span>Fuente activa: <strong className={dataSource?.mode === 'REAL' ? 'text-emerald-400' : 'text-amber-300'}>{dataSource?.mode || 'DEMO'}</strong></span>
        <span className="font-mono text-gray-500 truncate">{dataSource?.db_path}</span>
        <div className="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
          <input className={`${inputClass} min-w-0 sm:min-w-80`} placeholder="Ruta de backup .db para validar/restaurar" value={backupPath} onChange={(e) => setBackupPath(e.target.value)} />
          <button onClick={backup} className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 whitespace-nowrap">Exportar backup</button>
          <button disabled={!backupPath} onClick={validateBackup} className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 border border-gray-700 whitespace-nowrap">Validar</button>
          <button disabled={!backupPath} onClick={restoreBackup} className="px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 disabled:opacity-50 text-red-200 border border-red-500/30 whitespace-nowrap">Restaurar</button>
        </div>
      </div>

      {feedback && <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 rounded-xl p-3 text-xs">{feedback}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-bold text-white">Cuentas</h3>
          <input className={inputClass} placeholder="Nombre" value={accountForm.name || ''} onChange={(e) => setAccountForm({ ...accountForm, name: e.target.value })} />
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} placeholder="Tipo" value={accountForm.account_type || ''} onChange={(e) => setAccountForm({ ...accountForm, account_type: e.target.value })} />
            <input className={inputClass} placeholder="Moneda" value={accountForm.currency || ''} onChange={(e) => setAccountForm({ ...accountForm, currency: e.target.value.toUpperCase() })} />
            <input className={inputClass} type="number" placeholder="Balance inicial" value={accountForm.opening_balance ?? 0} onChange={(e) => setAccountForm({ ...accountForm, opening_balance: Number(e.target.value) })} />
            <input className={inputClass} type="number" placeholder="Balance actual" value={accountForm.current_balance ?? 0} onChange={(e) => setAccountForm({ ...accountForm, current_balance: Number(e.target.value) })} />
          </div>
          <button onClick={submitAccount} className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Guardar cuenta</button>
          <div className="space-y-2 max-h-56 overflow-auto">
            {accounts.map((a) => (
              <div key={a.id} className="flex items-center justify-between bg-gray-900/60 rounded-lg p-2 text-xs">
                <button className="text-left" onClick={() => setAccountForm(a)}>{a.name}<span className="text-gray-500"> · {a.currency} · {a.source}</span></button>
                <button onClick={() => onDeleteAccount(a.id)} className="text-red-300">Eliminar</button>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-bold text-white">Activos</h3>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} placeholder="Ticker" value={assetForm.ticker || ''} onChange={(e) => setAssetForm({ ...assetForm, ticker: e.target.value.toUpperCase() })} />
            <input className={inputClass} placeholder="Nombre" value={assetForm.name || ''} onChange={(e) => setAssetForm({ ...assetForm, name: e.target.value })} />
            <input className={inputClass} placeholder="Tipo" value={assetForm.asset_type || ''} onChange={(e) => setAssetForm({ ...assetForm, asset_type: e.target.value })} />
            <input className={inputClass} placeholder="Sector" value={assetForm.sector || ''} onChange={(e) => setAssetForm({ ...assetForm, sector: e.target.value })} />
            <input className={inputClass} type="number" placeholder="Cantidad" value={assetForm.quantity ?? 0} onChange={(e) => setAssetForm({ ...assetForm, quantity: Number(e.target.value) })} />
            <input className={inputClass} type="number" placeholder="Precio actual" value={assetForm.current_price ?? 0} onChange={(e) => setAssetForm({ ...assetForm, current_price: Number(e.target.value) })} />
            <input className={inputClass} type="number" placeholder="Costo promedio" value={assetForm.avg_price ?? 0} onChange={(e) => setAssetForm({ ...assetForm, avg_price: Number(e.target.value) })} />
            <input className={inputClass} placeholder="Moneda" value={assetForm.currency || ''} onChange={(e) => setAssetForm({ ...assetForm, currency: e.target.value.toUpperCase() })} />
          </div>
          <button onClick={submitAsset} className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Guardar activo</button>
          <div className="space-y-2 max-h-56 overflow-auto">
            {assets.map((a) => (
              <div key={a.ticker} className="flex items-center justify-between bg-gray-900/60 rounded-lg p-2 text-xs">
                <button className="text-left" onClick={() => setAssetForm(a)}>{a.ticker}<span className="text-gray-500"> · {a.name} · {a.source}</span></button>
                <button onClick={() => onDeleteAsset(a.ticker)} className="text-red-300">Eliminar</button>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-bold text-white">Transacción</h3>
          <select className={inputClass} value={txForm.account_id || ''} onChange={(e) => setTxForm({ ...txForm, account_id: e.target.value || undefined })}>
            <option value="">Sin cuenta</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} type="date" value={txForm.date || ''} onChange={(e) => setTxForm({ ...txForm, date: e.target.value })} />
            <input className={inputClass} type="number" value={txForm.amount ?? 0} onChange={(e) => setTxForm({ ...txForm, amount: Number(e.target.value) })} />
            <input className={inputClass} placeholder="Categoria" list="categories" value={txForm.category || ''} onChange={(e) => setTxForm({ ...txForm, category: e.target.value })} />
            <input className={inputClass} placeholder="Moneda" value={txForm.currency || ''} onChange={(e) => setTxForm({ ...txForm, currency: e.target.value.toUpperCase() })} />
          </div>
          <datalist id="categories">{categories.map((c) => <option key={c.id} value={c.name} />)}</datalist>
          <input className={inputClass} placeholder="Descripción" value={txForm.description || ''} onChange={(e) => setTxForm({ ...txForm, description: e.target.value })} />
          <button onClick={submitTransaction} className="w-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Guardar transacción</button>
        </section>
      </div>

      <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-bold text-white">Importar CSV</h3>
        <p className="text-xs text-gray-400">Columnas soportadas: date, amount, category, description, currency, account_id, external_id.</p>
        <input type="file" accept=".csv,text/csv" onChange={(e) => handleFile(e.target.files?.[0])} className="text-xs text-gray-300" />
        <textarea className={`${inputClass} w-full min-h-24`} placeholder="O pegue CSV aquí" value={csvText} onChange={(e) => setCsvText(e.target.value)} />
        <div className="flex gap-2">
          <button onClick={async () => setCsvResult(await onPreviewCsv(csvText))} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs">Preview</button>
          <button onClick={async () => setCsvResult(await onImportCsv(csvText))} className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Importar aceptadas</button>
        </div>
        {csvResult && (
          <div className="text-xs text-gray-300">
            Aceptadas: {csvResult.accepted_count} · Rechazadas: {csvResult.rejected_count} · Importadas: {csvResult.imported_count ?? '-'} · Duplicadas: {csvResult.duplicate_count ?? '-'}
          </div>
        )}
      </section>

      <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-white">Wallet by BudgetBakers</h3>
            <p className="text-xs text-gray-400">
              Fuente REAL solo lectura. Token en backend: <span className={walletStatus?.configured ? 'text-emerald-300' : 'text-amber-300'}>{walletStatus?.configured ? 'configurado' : 'no configurado'}</span>
              {walletStatus?.last_success_at ? ` · ultimo import: ${walletStatus.last_success_at}` : ''}
            </p>
          </div>
          <div className="flex gap-2">
            <button disabled={walletBusy} onClick={runWalletTest} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 text-xs">Probar</button>
            <button disabled={walletBusy || !walletStatus?.configured} onClick={previewWallet} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 text-xs">Preview</button>
            <button disabled={walletBusy || !walletPreview} onClick={importWallet} className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold">Confirmar importación</button>
          </div>
        </div>
        <div className="text-xs text-gray-400">
          Estado: <span className="text-gray-200">{walletStatus?.status || 'sin leer'}</span>
          {walletStatus?.last_error ? <span className="text-red-300"> · {walletStatus.last_error}</span> : null}
        </div>
        {walletPreview && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
            <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Cuentas</div><div className="text-white font-bold">{walletPreview.accounts_detected}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Registros</div><div className="text-white font-bold">{walletPreview.records_found}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Nuevos</div><div className="text-emerald-300 font-bold">{walletPreview.new_transaction_count}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Duplicados</div><div className="text-amber-300 font-bold">{walletPreview.duplicate_count}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Rechazados</div><div className="text-red-300 font-bold">{walletPreview.rejected_count}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Rango</div><div className="text-white">{walletPreview.date_range?.from || '-'} / {walletPreview.date_range?.to || '-'}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Cuentas nuevas</div><div className="text-white font-bold">{walletPreview.new_accounts}</div></div>
            <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Fuente</div><div className="text-white font-bold">BUDGETBAKERS</div></div>
          </div>
        )}
      </section>

      <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-white">eToro read-only</h3>
            <p className="text-xs text-gray-400">
              Fuente REAL solo lectura para inversión. Keys en backend: <span className={etoroStatus?.configured ? 'text-emerald-300' : 'text-amber-300'}>{etoroStatus?.configured ? 'configuradas' : 'no configuradas'}</span>
              {etoroStatus?.environment ? ` · ${etoroStatus.environment}` : ''}
              {etoroStatus?.last_success_at ? ` · ultimo import: ${etoroStatus.last_success_at}` : ''}
            </p>
          </div>
          <div className="flex gap-2">
            <button disabled={etoroBusy} onClick={runEtoroTest} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 text-xs">Probar</button>
            <button disabled={etoroBusy || !etoroStatus?.configured} onClick={previewEtoro} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 text-xs">Preview</button>
            <button disabled={etoroBusy || !etoroPreview || etoroPreview.new_count === 0} onClick={importEtoro} className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold">Confirmar importación</button>
          </div>
        </div>
        <div className="text-xs text-gray-400">
          Estado: <span className="text-gray-200">{etoroStatus?.status || 'sin leer'}</span>
          {etoroStatus?.last_error ? <span className="text-red-300"> · {etoroStatus.last_error}</span> : null}
        </div>
        {etoroPreview && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Posiciones</div><div className="text-white font-bold">{etoroPreview.positions_found}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Operaciones</div><div className="text-white font-bold">{etoroPreview.operations_found}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Nuevas</div><div className="text-emerald-300 font-bold">{etoroPreview.new_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Duplicadas</div><div className="text-amber-300 font-bold">{etoroPreview.duplicate_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Rechazadas</div><div className="text-red-300 font-bold">{etoroPreview.rejected_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Sin mapping</div><div className="text-amber-300 font-bold">{etoroPreview.unmapped_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Unsupported</div><div className="text-red-300 font-bold">{etoroPreview.unsupported_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Reconciliación</div><div className="text-white font-bold">{etoroPreview.reconciliation?.summary.issues ?? 0} alertas</div></div>
            </div>
            {etoroPreview.optional_warnings?.length ? (
              <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2">
                {etoroPreview.optional_warnings.slice(0, 3).map((warning) => <div key={warning}>{warning}</div>)}
              </div>
            ) : null}
            {(etoroPreview.unmapped_instruments.length > 0 || etoroPreview.unsupported_instruments.length > 0 || (etoroPreview.reconciliation?.issues.length || 0) > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                <div className="bg-gray-900/60 rounded-lg p-2">
                  <div className="text-gray-400 font-bold mb-1">Instrumentos sin mapping</div>
                  {etoroPreview.unmapped_instruments.slice(0, 4).map((item) => <div key={`${item.external_instrument_id}-${item.external_name}`} className="text-amber-200 truncate">{item.external_name || item.external_instrument_id}</div>)}
                  {etoroPreview.unmapped_instruments.length === 0 && <div className="text-gray-500">Sin pendientes.</div>}
                </div>
                <div className="bg-gray-900/60 rounded-lg p-2">
                  <div className="text-gray-400 font-bold mb-1">CFD/leverage/short</div>
                  {etoroPreview.unsupported_instruments.slice(0, 4).map((item) => <div key={`${item.external_id}-${item.external_name}`} className="text-red-200 truncate">{item.external_name || item.external_id}</div>)}
                  {etoroPreview.unsupported_instruments.length === 0 && <div className="text-gray-500">Sin bloqueos.</div>}
                </div>
                <div className="bg-gray-900/60 rounded-lg p-2">
                  <div className="text-gray-400 font-bold mb-1">Ledger vs eToro</div>
                  {etoroPreview.reconciliation?.issues.slice(0, 4).map((item) => <div key={`${item.type}-${item.ticker}`} className="text-amber-200 truncate">{item.ticker || item.type}: {item.type}</div>)}
                  {(!etoroPreview.reconciliation || etoroPreview.reconciliation.issues.length === 0) && <div className="text-gray-500">Sin diferencias.</div>}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="bg-[#111827] border border-gray-800 rounded-xl p-4">
        <h3 className="text-sm font-bold text-white mb-3">Transacciones recientes</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-gray-400 uppercase text-[10px]">
              <tr><th className="py-2">Fecha</th><th>Monto</th><th>Categoría</th><th>Cuenta</th><th>Fuente</th><th></th></tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {transactions.map((t) => (
                <tr key={t.id}>
                  <td className="py-2">{t.date}</td>
                  <td className={t.amount >= 0 ? 'text-emerald-400' : 'text-red-300'}>{money(t.amount)} {t.currency}</td>
                  <td>{t.category}<div className="text-gray-500">{t.description}</div></td>
                  <td>{t.account_name || '-'}</td>
                  <td>{t.source}</td>
                  <td className="text-right"><button onClick={() => onDeleteTransaction(t.id)} className="text-red-300">Eliminar</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="bg-[#111827] border border-gray-800 rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-bold text-white">Reconciliación Wallet</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-bold text-gray-300 mb-2">Cuentas sin mapping</div>
            {reconciliation?.unmapped_accounts.slice(0, 6).map((account) => (
              <div key={account.external_id} className="flex flex-col sm:flex-row sm:items-center gap-2 bg-gray-900/60 rounded-lg p-2 mb-2 text-xs">
                <span className="flex-1 text-gray-200">{account.external_name || account.external_id}</span>
                <select className={inputClass} onChange={(e) => e.target.value && saveAccountMapping(account.external_id, account.external_name, e.target.value)} defaultValue="">
                  <option value="">Asignar...</option>
                  {accounts.filter((a) => a.source !== 'BUDGETBAKERS').map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  <option value={account.local_id || ''}>Usar cuenta importada</option>
                </select>
              </div>
            ))}
            {(!reconciliation || reconciliation.unmapped_accounts.length === 0) && <div className="text-xs text-gray-400">Sin cuentas pendientes.</div>}
          </div>
          <div>
            <div className="text-xs font-bold text-gray-300 mb-2">Categorías frecuentes sin mapping</div>
            {reconciliation?.unmapped_categories.slice(0, 8).map((category) => (
              <div key={category.external_name} className="flex flex-col sm:flex-row sm:items-center gap-2 bg-gray-900/60 rounded-lg p-2 mb-2 text-xs">
                <span className="flex-1 text-gray-200">{category.external_name}<span className="text-gray-500"> · {category.count}</span></span>
                <select className={inputClass} onChange={(e) => e.target.value && saveCategoryMapping(category.external_name, e.target.value)} defaultValue="">
                  <option value="">Asignar...</option>
                  {categories.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                </select>
              </div>
            ))}
            {(!reconciliation || reconciliation.unmapped_categories.length === 0) && <div className="text-xs text-gray-400">Sin categorías pendientes.</div>}
          </div>
        </div>
      </section>
    </div>
  );
};
