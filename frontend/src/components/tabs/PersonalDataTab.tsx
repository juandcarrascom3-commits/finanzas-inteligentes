import React, { useEffect, useState } from 'react';
import { Account, Asset, BackupResult, BackupValidation, BudgetBakersPreview, BudgetBakersStatus, Category, CsvImportResult, DataSourceInfo, EtoroMappingSuggestion, EtoroPreview, EtoroStatus, MappingConfig, ReconciliationSummary, SourceMapping, Transaction } from '../../types';

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
  onFetchEtoroMappings: () => Promise<{ mappings: SourceMapping[]; assets: Asset[]; market_symbol_mappings: Array<Record<string, unknown>> }>;
  onConfirmEtoroMappings: (mappings: SourceMapping[]) => Promise<unknown>;
  onMarkEtoroUnsupported: (mapping: SourceMapping) => Promise<SourceMapping>;
  onExportMappingConfig: () => Promise<MappingConfig>;
  onValidateMappingConfig: (config: MappingConfig) => Promise<{ valid: boolean; errors: string[]; counts: Record<string, number> }>;
  onImportMappingConfig: (config: MappingConfig) => Promise<unknown>;
  onFetchReconciliation: () => Promise<ReconciliationSummary>;
  onSaveSourceMapping: (mapping: SourceMapping) => Promise<SourceMapping>;
  onSaveOpeningPosition: (position: { ticker: string; opened_at: string; quantity: number; unit_cost?: number; total_cost?: number; currency: string; notes?: string }) => Promise<void>;
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
  onFetchEtoroMappings,
  onConfirmEtoroMappings,
  onMarkEtoroUnsupported,
  onExportMappingConfig,
  onValidateMappingConfig,
  onImportMappingConfig,
  onFetchReconciliation,
  onSaveSourceMapping,
  onSaveOpeningPosition,
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
  const [etoroMappings, setEtoroMappings] = useState<SourceMapping[]>([]);
  const [selectedEtoroIds, setSelectedEtoroIds] = useState<string[]>([]);
  const [etoroTargets, setEtoroTargets] = useState<Record<string, string>>({});
  const [mappingConfigText, setMappingConfigText] = useState('');
  const [reconciliation, setReconciliation] = useState<ReconciliationSummary | null>(null);
  const [backupPath, setBackupPath] = useState('');
  const [walletBusy, setWalletBusy] = useState(false);
  const [etoroBusy, setEtoroBusy] = useState(false);
  const [feedback, setFeedback] = useState<string>('');

  useEffect(() => {
    onFetchWalletStatus().then(setWalletStatus).catch((err) => setFeedback(err.message));
    onFetchEtoroStatus().then(setEtoroStatus).catch(() => undefined);
    onFetchEtoroMappings().then((result) => setEtoroMappings(result.mappings)).catch(() => undefined);
    onFetchReconciliation().then(setReconciliation).catch(() => undefined);
  }, [onFetchWalletStatus, onFetchEtoroStatus, onFetchEtoroMappings]);

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
      const exactTargets: Record<string, string> = {};
      const selected: string[] = [];
      (preview.mapping_suggestions || []).forEach((item) => {
        const exact = item.suggested.find((candidate) => candidate.confidence === 'EXACT');
        if (exact) {
          exactTargets[item.external_id || item.external_name] = exact.ticker;
          selected.push(item.external_id || item.external_name);
        }
      });
      setEtoroTargets(exactTargets);
      setSelectedEtoroIds(selected);
      setFeedback('Preview de eToro listo. Revise mappings, CFDs y diferencias antes de importar.');
    } catch (err: any) {
      setFeedback(err.message);
    } finally {
      setEtoroBusy(false);
    }
  };

  const importEtoro = async () => {
    if (!etoroPreview) return;
    if (!window.confirm(`Importar eToro ${etoroPreview.environment.toUpperCase()} localmente con backup previo?`)) return;
    setEtoroBusy(true);
    try {
      const result = await onImportEtoro(etoroPreview);
      setEtoroPreview({ ...etoroPreview, ...result });
      setEtoroStatus(await onFetchEtoroStatus());
      setFeedback(`eToro importado: ${result.imported_count ?? 0} nuevas; backup ${result.backup?.created ? 'valido' : 'no reportado'}.`);
    } catch (err: any) {
      setFeedback(err.message);
    } finally {
      setEtoroBusy(false);
    }
  };

  const etoroKey = (item: EtoroMappingSuggestion) => item.external_id || item.external_name;

  const toggleEtoroSelection = (key: string) => {
    setSelectedEtoroIds((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  };

  const confirmSelectedEtoroMappings = async () => {
    if (!etoroPreview) return;
    const mappings = (etoroPreview.mapping_suggestions || [])
      .filter((item) => selectedEtoroIds.includes(etoroKey(item)) && etoroTargets[etoroKey(item)])
      .map((item) => ({
        source: 'ETORO' as const,
        external_type: 'instrument' as const,
        external_id: item.external_id || item.external_name,
        external_name: item.external_name,
        local_id: etoroTargets[etoroKey(item)].toUpperCase(),
        local_type: 'ticker',
        is_active: true
      }));
    if (mappings.length === 0) return;
    await onConfirmEtoroMappings(mappings);
    setEtoroMappings((await onFetchEtoroMappings()).mappings);
    setFeedback(`${mappings.length} mappings eToro confirmados. Ejecute Preview otra vez para revalidar.`);
  };

  const saveSingleEtoroMapping = async (item: EtoroMappingSuggestion) => {
    const target = etoroTargets[etoroKey(item)];
    if (!target) return;
    await onSaveSourceMapping({
      source: 'ETORO',
      external_type: 'instrument',
      external_id: item.external_id || item.external_name,
      external_name: item.external_name,
      local_id: target.toUpperCase(),
      local_type: 'ticker',
      is_active: true
    });
    setEtoroMappings((await onFetchEtoroMappings()).mappings);
    setFeedback(`Mapping eToro confirmado para ${item.external_name}.`);
  };

  const markUnsupported = async (item: EtoroMappingSuggestion) => {
    await onMarkEtoroUnsupported({
      source: 'ETORO',
      external_type: 'instrument',
      external_id: item.external_id || item.external_name,
      external_name: item.external_name,
      local_type: 'unsupported',
      is_active: false
    });
    setEtoroMappings((await onFetchEtoroMappings()).mappings);
    setFeedback(`${item.external_name} marcado como unsupported.`);
  };

  const createAssetFromEtoro = async (item: EtoroMappingSuggestion) => {
    const ticker = (etoroTargets[etoroKey(item)] || item.symbol || item.external_id || '').toUpperCase();
    if (!ticker) return;
    await onSaveAsset({
      ticker,
      name: item.external_name || ticker,
      asset_type: item.instrument_type || 'Renta Variable',
      sector: 'General',
      country: 'Global',
      quantity: 0,
      avg_price: 0,
      current_price: 0,
      currency: item.currency || 'USD',
      source: 'MANUAL'
    });
    setEtoroTargets({ ...etoroTargets, [etoroKey(item)]: ticker });
    setFeedback(`Activo ${ticker} creado. Confirme el mapping antes de importar.`);
  };

  const saveOpeningFromSuggestion = async (suggestion: NonNullable<EtoroPreview['dry_run']>['opening_position_suggestions'][number]) => {
    const openedAt = window.prompt('Fecha de posición inicial (YYYY-MM-DD)', suggestion.opened_at || '') || '';
    const unitCost = Number(window.prompt('Costo unitario confirmado', '0') || 0);
    if (!openedAt) {
      setFeedback('Opening position no guardada: falta fecha confirmada.');
      return;
    }
    if (unitCost <= 0) {
      setFeedback('Opening position no guardada: falta costo unitario confirmado.');
      return;
    }
    await onSaveOpeningPosition({
      ticker: suggestion.ticker,
      opened_at: openedAt,
      quantity: suggestion.quantity,
      unit_cost: unitCost,
      currency: suggestion.currency,
      notes: suggestion.notes
    });
    setFeedback(`Opening position preparada para ${suggestion.ticker}. Ejecute Preview otra vez.`);
  };

  const exportConfig = async () => {
    const config = await onExportMappingConfig();
    setMappingConfigText(JSON.stringify(config, null, 2));
    setFeedback('Configuración de mappings exportada en JSON.');
  };

  const validateConfig = async () => {
    const parsed = JSON.parse(mappingConfigText);
    const result = await onValidateMappingConfig(parsed);
    setFeedback(result.valid ? `Config válida: ${JSON.stringify(result.counts)}` : `Config inválida: ${result.errors.join(', ')}`);
  };

  const importConfig = async () => {
    const parsed = JSON.parse(mappingConfigText);
    await onImportMappingConfig(parsed);
    setEtoroMappings((await onFetchEtoroMappings()).mappings);
    setFeedback('Configuración de mappings importada.');
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
            <button disabled={etoroBusy || !etoroPreview || !etoroPreview.import_enabled || etoroPreview.history_status !== 'READY' || (etoroPreview.local_conflict_count ?? 0) > 0} onClick={importEtoro} className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold">Confirmar importación</button>
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
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Operaciones</div><div className="text-white font-bold">{etoroPreview.operations_found ?? 'No evaluado'}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Importables</div><div className="text-emerald-300 font-bold">{etoroPreview.ready_to_import_count ?? etoroPreview.new_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Duplicadas</div><div className="text-amber-300 font-bold">{etoroPreview.duplicate_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Rechazadas</div><div className="text-red-300 font-bold">{etoroPreview.rejected_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Sin mapping</div><div className="text-amber-300 font-bold">{etoroPreview.unmapped_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Unsupported</div><div className="text-red-300 font-bold">{etoroPreview.unsupported_count}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Conflictos</div><div className="text-red-300 font-bold">{etoroPreview.local_conflict_count ?? 0}</div></div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Updates</div><div className="text-white font-bold">{etoroPreview.update_candidate_count ?? 0}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Periodo</div><div className="text-white">{etoroPreview.period?.from || '-'} / {etoroPreview.period?.to || '-'}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">FX faltante</div><div className="text-amber-300 font-bold">{etoroPreview.missing_fx?.join(', ') || '-'}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Ambiente</div><div className="text-white font-bold">{etoroPreview.environment_label || `ETORO ${etoroPreview.environment.toUpperCase()}`}</div></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Snapshot</div><div className="text-white font-bold">{etoroPreview.snapshot_status || '-'}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Historial</div><div className="text-amber-300 font-bold">{etoroPreview.history_status || 'NOT_AVAILABLE'}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">PnL cuenta</div><div className="text-white font-bold">{etoroPreview.snapshot?.account_pnl_reconciliation?.status || '-'}</div></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Preview</div><div className={etoroPreview.preview_valid ? 'text-emerald-300 font-bold' : 'text-red-300 font-bold'}>{etoroPreview.preview_valid ? 'VALIDO' : 'STALE'}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Gates</div><div className={etoroPreview.import_gates?.status === 'PASS' ? 'text-emerald-300 font-bold' : 'text-amber-300 font-bold'}>{etoroPreview.import_gates?.status || '-'}</div></div>
              <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Backup/import</div><div className="text-white font-bold">{etoroPreview.backup?.created ? 'BACKUP OK' : etoroPreview.import_status || '-'}</div></div>
            </div>
            {etoroPreview.import_gates?.failures?.length ? (
              <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2">
                {etoroPreview.import_gates.failures.join(' · ')}
              </div>
            ) : null}
            {etoroPreview.history_summary && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Rows history</div><div className="text-white font-bold">{etoroPreview.history_summary.rows_downloaded ?? etoroPreview.history_summary.rows ?? 0}</div></div>
                <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Compatibles</div><div className="text-emerald-300 font-bold">{etoroPreview.history_summary.compatible ?? 0}</div></div>
                <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Parciales</div><div className="text-amber-300 font-bold">{etoroPreview.history_summary.partial ?? 0}</div></div>
                <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Conflictos ID</div><div className="text-red-300 font-bold">{etoroPreview.history_summary.identity_conflicts ?? 0}</div></div>
                <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Stop</div><div className="text-gray-200 font-bold">{etoroPreview.history_summary.stop_reason || '-'}</div></div>
              </div>
            )}
            {etoroPreview.history_status !== 'READY' && (
              <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2">
                Historial eToro no disponible/no validado todavía. La importación permanece deshabilitada y no se muestran falsos 0 históricos.
              </div>
            )}
            {etoroPreview.history_status === 'READY' && !etoroPreview.import_enabled && (
              <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2">
                Historial eToro disponible en modo dry-run. La importación real permanece deshabilitada en esta fase.
              </div>
            )}
            {etoroPreview.snapshot && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Direct</div><div className="text-white">{etoroPreview.snapshot.direct_summary?.positions ?? 0} posiciones · PnL {money(etoroPreview.snapshot.direct_summary?.unrealized_pnl ?? 0)}</div></div>
                <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">Mirrors</div><div className="text-white">{etoroPreview.snapshot.mirror_summary?.mirrors ?? 0} mirrors · {etoroPreview.snapshot.mirror_summary?.internal_positions ?? 0} internas</div></div>
                <div className="bg-gray-900/60 rounded-lg p-2"><div className="text-gray-500">PnL reconstruido</div><div className="text-white">{money(etoroPreview.snapshot.account_pnl_reconciliation?.reconstructed_total_pnl ?? 0)}</div></div>
              </div>
            )}
            {etoroPreview.optional_warnings?.length ? (
              <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2">
                {etoroPreview.optional_warnings.slice(0, 3).map((warning) => <div key={warning}>{warning}</div>)}
              </div>
            ) : null}
            {etoroPreview.mapping_suggestions?.length ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-bold text-gray-300">Instrument mapping eToro → Finance</div>
                  <button onClick={confirmSelectedEtoroMappings} className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">Confirmar seleccionados</button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-gray-400 uppercase text-[10px]">
                      <tr><th></th><th>External</th><th>Nombre</th><th>Tipo</th><th>Moneda</th><th>Estado</th><th>Mapping</th><th>Acciones</th></tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {etoroPreview.mapping_suggestions.map((item) => {
                        const key = etoroKey(item);
                        const current = etoroMappings.find((mapping) => mapping.external_id === item.external_id);
                        return (
                          <tr key={key}>
                            <td className="py-2"><input type="checkbox" checked={selectedEtoroIds.includes(key)} onChange={() => toggleEtoroSelection(key)} /></td>
                            <td className="font-mono text-gray-400">{item.external_id || '-'}</td>
                            <td>{item.external_name}<div className="text-gray-500">{item.symbol || ''}</div></td>
                            <td>{item.instrument_type || '-'}</td>
                            <td>{item.currency || '-'}</td>
                            <td><span className={item.status === 'READY' ? 'text-emerald-300' : 'text-amber-300'}>{current?.is_active === 0 ? 'UNSUPPORTED' : item.status}</span></td>
                            <td>
                              <select className={inputClass} value={etoroTargets[key] || current?.local_id || ''} onChange={(e) => setEtoroTargets({ ...etoroTargets, [key]: e.target.value })}>
                                <option value="">Seleccionar...</option>
                                {item.suggested.map((candidate) => <option key={`${key}-${candidate.ticker}`} value={candidate.ticker}>{candidate.ticker} · {candidate.confidence}</option>)}
                                {assets.map((asset) => <option key={`${key}-${asset.ticker}`} value={asset.ticker}>{asset.ticker} · {asset.name}</option>)}
                              </select>
                              {item.suggested.length > 0 && <div className="text-[10px] text-gray-500">suggested ≠ confirmed</div>}
                            </td>
                            <td className="space-x-2 whitespace-nowrap">
                              <button onClick={() => saveSingleEtoroMapping(item)} className="text-emerald-300">Guardar</button>
                              <button onClick={() => createAssetFromEtoro(item)} className="text-gray-300">Crear asset</button>
                              <button onClick={() => markUnsupported(item)} className="text-red-300">Unsupported</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
            {etoroPreview.dry_run && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                <div className="bg-gray-900/60 rounded-lg p-2">
                  <div className="text-gray-400 font-bold mb-1">Dry-run ledger</div>
                  <div>Nuevas: <span className="text-emerald-300">{etoroPreview.dry_run.new_operations}</span></div>
                  <div>Updates: <span className="text-amber-300">{etoroPreview.dry_run.update_candidates}</span></div>
                  <div>Conflictos: <span className="text-red-300">{etoroPreview.dry_run.local_conflicts}</span></div>
                </div>
                <div className="bg-gray-900/60 rounded-lg p-2">
                  <div className="text-gray-400 font-bold mb-1">Coverage</div>
                  {etoroPreview.dry_run.history_coverage.slice(0, 5).map((row) => <div key={`${row.ticker}-${row.external_id}`} className="flex justify-between gap-2"><span>{row.ticker || row.external_name}</span><span className="text-gray-300">{row.coverage}</span></div>)}
                </div>
                <div className="bg-gray-900/60 rounded-lg p-2">
                  <div className="text-gray-400 font-bold mb-1">Opening position assist</div>
                  {etoroPreview.dry_run.opening_position_suggestions.slice(0, 4).map((item) => (
                    <div key={item.ticker} className="flex items-center justify-between gap-2">
                      <span>{item.ticker} · {item.quantity}</span>
                      <button disabled={item.requires_user_cost_basis || item.requires_user_opened_at} onClick={() => saveOpeningFromSuggestion(item)} className="text-emerald-300 disabled:text-gray-500">Requiere datos</button>
                    </div>
                  ))}
                  {etoroPreview.dry_run.opening_position_suggestions.length === 0 && <div className="text-gray-500">Sin sugerencias.</div>}
                </div>
              </div>
            )}
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
        <div className="space-y-2 pt-2 border-t border-gray-800">
          <div className="flex items-center gap-2">
            <button onClick={exportConfig} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs">Exportar config mappings</button>
            <button disabled={!mappingConfigText} onClick={validateConfig} className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-200 text-xs">Validar JSON</button>
            <button disabled={!mappingConfigText} onClick={importConfig} className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold">Importar config</button>
          </div>
          <textarea className={`${inputClass} w-full min-h-24`} placeholder="JSON de config eToro/Market Data/Price Authority" value={mappingConfigText} onChange={(e) => setMappingConfigText(e.target.value)} />
        </div>
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
