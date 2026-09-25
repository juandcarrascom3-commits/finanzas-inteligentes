import React, { useEffect, useRef, useState } from 'react';
import { Account, Asset, BackupResult, BackupValidation, BudgetBakersPreview, BudgetBakersStatus, Category, CsvImportResult, DataSourceInfo, EtoroMappingSuggestion, EtoroPreview, EtoroStatus, MappingConfig, ReconciliationSummary, SourceMapping, Transaction } from '../../types';
import { Button, Field, MetricInput, MoneyField } from '../../aetheris/controls';
import { DataState, InlineMetric } from '../../aetheris/primitives';
import { ToolSurfaceDock } from '../../aetheris/ToolSurfaceDock';

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

// Select y date nativos estilizados con tokens (mismo contrato que controlClass).
const dataControlClass =
  'min-h-10 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] placeholder:text-[var(--a-muted)] transition-colors focus:border-[var(--a-brand)] focus:outline-none';

// Textarea estilizado con tokens (dock CSV / JSON).
const dataAreaClass =
  'min-h-24 w-full rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] placeholder:text-[var(--a-muted)] transition-colors focus:border-[var(--a-brand)] focus:outline-none';

// Select inline estilizado con tokens (reconciliación): mismo contrato sin ancho forzado.
const dataSelectClass =
  'min-h-10 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] px-3 py-2 text-sm text-[var(--a-text)] transition-colors focus:border-[var(--a-brand)] focus:outline-none';

// Celda de evidencia tokenizada (grupos compactos dentro del dock eToro).
const dataEvidenceClass =
  'rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2 text-xs';

// Banner de advertencia tokenizado (evidencia eToro: gates/history/warnings).
const dataWarningClass =
  'rounded-[var(--a-radius-sm)] border border-[var(--a-warning)] bg-[var(--a-canvas)] p-2 text-xs text-[var(--a-warning)]';

// Herramienta activa en ToolSurfaceDock (una a la vez; estado local del tab).
type DataTool = 'csv' | 'wallet' | 'etoro' | null;

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
  const [openTool, setOpenTool] = useState<DataTool>(null);
  const csvLauncherRef = useRef<HTMLButtonElement>(null);
  const walletLauncherRef = useRef<HTMLButtonElement>(null);
  const etoroLauncherRef = useRef<HTMLButtonElement>(null);

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
    <div className={openTool ? 'grid gap-[var(--a-stack)] min-[1041px]:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]' : ''}>
    <section className="a-canvas a-enter space-y-5">
      <header>
        <div className="a-page-kicker">Datos</div>
        <h1 className="a-page-title">Centro de información</h1>
        <p className="a-page-subtitle">Fuentes, estado, integridad y gestión de los datos financieros.</p>
      </header>

      <section className="a-surface p-5" aria-labelledby="data-source-status-title">
        <h2 id="data-source-status-title" className="a-page-kicker">Estado de la fuente</h2>
        <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 space-y-1">
            <p className="a-meta">
              Fuente activa:{' '}
              <strong className="font-semibold text-[var(--a-text)]">{dataSource?.mode || 'DEMO'}</strong>
            </p>
            <p className="a-meta break-all">{dataSource?.db_path}</p>
          </div>
          <div className="flex flex-col gap-3 sm:min-w-80 md:items-end">
            <Field
              id="data-backup-path"
              label="Ruta de backup .db para validar/restaurar"
              value={backupPath}
              onChange={setBackupPath}
            />
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button variant="operational" onClick={backup} className="whitespace-nowrap">Exportar backup</Button>
              <Button variant="quiet" disabled={!backupPath} onClick={validateBackup} className="whitespace-nowrap">Validar</Button>
              <Button variant="negative" disabled={!backupPath} onClick={restoreBackup} className="whitespace-nowrap">Restaurar</Button>
            </div>
          </div>
        </div>
      </section>

      {feedback && (
        <div role="status" className="a-surface p-3 text-xs text-[var(--a-secondary)]">{feedback}</div>
      )}

      <section className="a-surface p-5" aria-labelledby="data-manual-title">
        <h2 id="data-manual-title" className="a-page-kicker">Alta manual</h2>
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wide text-[var(--a-secondary)]">Cuenta</h3>
            <Field id="data-account-name" label="Nombre" value={accountForm.name || ''} onChange={(raw) => setAccountForm({ ...accountForm, name: raw })} />
            <div className="grid grid-cols-2 gap-3">
              <Field id="data-account-type" label="Tipo" value={accountForm.account_type || ''} onChange={(raw) => setAccountForm({ ...accountForm, account_type: raw })} />
              <Field id="data-account-currency" label="Moneda" value={accountForm.currency || ''} onChange={(raw) => setAccountForm({ ...accountForm, currency: raw.toUpperCase() })} />
              <MoneyField id="data-account-opening" label="Balance inicial" value={accountForm.opening_balance ?? 0} onChange={(v) => setAccountForm({ ...accountForm, opening_balance: v })} currency={accountForm.currency || 'USD'} allowNegative />
              <MoneyField id="data-account-current" label="Balance actual" value={accountForm.current_balance ?? 0} onChange={(v) => setAccountForm({ ...accountForm, current_balance: v })} currency={accountForm.currency || 'USD'} allowNegative />
            </div>
            <Button variant="primary" onClick={submitAccount} className="w-full">Guardar cuenta</Button>
            {accounts.length === 0 ? (
              <DataState state="EMPTY" title="Sin cuentas" detail="Las cuentas que registres aparecerán aquí." />
            ) : (
              <div className="max-h-56 space-y-2 overflow-auto">
                {accounts.map((a) => (
                  <div key={a.id} className="flex items-center justify-between gap-2 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2 text-xs">
                    <button className="min-w-0 flex-1 text-left text-[var(--a-secondary)] transition-colors hover:text-[var(--a-text)]" onClick={() => setAccountForm(a)}>
                      {a.name}<span className="text-[var(--a-muted)]"> · {a.currency} · {a.source}</span>
                    </button>
                    <Button variant="negative" onClick={() => onDeleteAccount(a.id)} className="shrink-0">Eliminar</Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-3 border-t border-[var(--a-line)] pt-6 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
            <h3 className="text-xs font-bold uppercase tracking-wide text-[var(--a-secondary)]">Activos</h3>
            <div className="grid grid-cols-2 gap-3">
              <Field id="data-asset-ticker" label="Ticker" value={assetForm.ticker || ''} onChange={(raw) => setAssetForm({ ...assetForm, ticker: raw.toUpperCase() })} />
              <Field id="data-asset-name" label="Nombre" value={assetForm.name || ''} onChange={(raw) => setAssetForm({ ...assetForm, name: raw })} />
              <Field id="data-asset-type" label="Tipo" value={assetForm.asset_type || ''} onChange={(raw) => setAssetForm({ ...assetForm, asset_type: raw })} />
              <Field id="data-asset-sector" label="Sector" value={assetForm.sector || ''} onChange={(raw) => setAssetForm({ ...assetForm, sector: raw })} />
              <MetricInput id="data-asset-quantity" label="Cantidad" value={assetForm.quantity ?? 0} onChange={(raw) => setAssetForm({ ...assetForm, quantity: Number(raw || 0) })} unit="uds" allowNegative />
              <MetricInput id="data-asset-current-price" label="Precio actual" value={assetForm.current_price ?? 0} onChange={(raw) => setAssetForm({ ...assetForm, current_price: Number(raw || 0) })} unit={assetForm.currency || 'USD'} allowNegative />
              <MetricInput id="data-asset-avg-price" label="Costo promedio" value={assetForm.avg_price ?? 0} onChange={(raw) => setAssetForm({ ...assetForm, avg_price: Number(raw || 0) })} unit={assetForm.currency || 'USD'} allowNegative />
              <Field id="data-asset-currency" label="Moneda" value={assetForm.currency || ''} onChange={(raw) => setAssetForm({ ...assetForm, currency: raw.toUpperCase() })} />
            </div>
            <Button variant="primary" onClick={submitAsset} className="w-full">Guardar activo</Button>
            {assets.length === 0 ? (
              <DataState state="EMPTY" title="Sin activos" detail="Los activos que registres aparecerán aquí." />
            ) : (
              <div className="max-h-56 space-y-2 overflow-auto">
                {assets.map((a) => (
                  <div key={a.ticker} className="flex items-center justify-between gap-2 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2 text-xs">
                    <button className="min-w-0 flex-1 text-left text-[var(--a-secondary)] transition-colors hover:text-[var(--a-text)]" onClick={() => setAssetForm(a)}>
                      {a.ticker}<span className="text-[var(--a-muted)]"> · {a.name} · {a.source}</span>
                    </button>
                    <Button variant="negative" onClick={() => onDeleteAsset(a.ticker)} className="shrink-0">Eliminar</Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-3 border-t border-[var(--a-line)] pt-6 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
            <h3 className="text-xs font-bold uppercase tracking-wide text-[var(--a-secondary)]">Transacción</h3>
            <div>
              <label htmlFor="data-tx-account" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Cuenta</label>
              <select id="data-tx-account" className={dataControlClass} value={txForm.account_id || ''} onChange={(e) => setTxForm({ ...txForm, account_id: e.target.value || undefined })}>
                <option value="">Sin cuenta</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="data-tx-date" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Fecha</label>
                <input id="data-tx-date" type="date" className={dataControlClass} value={txForm.date || ''} onChange={(e) => setTxForm({ ...txForm, date: e.target.value })} />
              </div>
              <MoneyField id="data-tx-amount" label="Monto" value={txForm.amount ?? 0} onChange={(v) => setTxForm({ ...txForm, amount: v })} currency={txForm.currency || 'USD'} allowNegative />
              <Field id="data-tx-category" label="Categoria" list="categories" value={txForm.category || ''} onChange={(raw) => setTxForm({ ...txForm, category: raw })} />
              <Field id="data-tx-currency" label="Moneda" value={txForm.currency || ''} onChange={(raw) => setTxForm({ ...txForm, currency: raw.toUpperCase() })} />
            </div>
            <datalist id="categories">{categories.map((c) => <option key={c.id} value={c.name} />)}</datalist>
            <Field id="data-tx-description" label="Descripción" value={txForm.description || ''} onChange={(raw) => setTxForm({ ...txForm, description: raw })} />
            <Button variant="primary" onClick={submitTransaction} className="w-full">Guardar transacción</Button>
          </div>
        </div>
      </section>

      <section className="a-surface p-5" aria-labelledby="data-tool-launcher-title">
        <h2 id="data-tool-launcher-title" className="a-page-kicker">Herramientas bajo demanda</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Button
            ref={csvLauncherRef}
            variant={openTool === 'csv' ? 'operational' : 'quiet'}
            aria-pressed={openTool === 'csv'}
            aria-controls="data-csv-dock"
            onClick={() => setOpenTool((current) => current === 'csv' ? null : 'csv')}
            className="h-auto min-h-11 justify-start text-left"
          >
            Importar CSV
          </Button>
          <Button
            ref={walletLauncherRef}
            variant={openTool === 'wallet' ? 'operational' : 'quiet'}
            aria-pressed={openTool === 'wallet'}
            aria-controls="data-wallet-dock"
            onClick={() => setOpenTool((current) => current === 'wallet' ? null : 'wallet')}
            className="h-auto min-h-11 justify-start text-left"
          >
            Wallet
          </Button>
          <Button
            ref={etoroLauncherRef}
            variant={openTool === 'etoro' ? 'operational' : 'quiet'}
            aria-pressed={openTool === 'etoro'}
            aria-controls="data-etoro-dock"
            onClick={() => setOpenTool((current) => current === 'etoro' ? null : 'etoro')}
            className="h-auto min-h-11 justify-start text-left"
          >
            eToro
          </Button>
        </div>
      </section>

      <section className="a-surface p-5" aria-labelledby="data-recent-title">
        <h2 id="data-recent-title" className="a-page-kicker">Transacciones recientes</h2>
        <div className="mt-4 max-h-[28rem] overflow-auto">
          {transactions.length === 0 ? (
            <DataState state="EMPTY" title="Sin transacciones" detail="Las transacciones registradas aparecerán aquí." />
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="text-[var(--a-muted)] uppercase text-[10px]">
                <tr><th className="py-2">Fecha</th><th>Monto</th><th>Categoría</th><th>Cuenta</th><th>Fuente</th><th></th></tr>
              </thead>
              <tbody className="divide-y divide-[var(--a-line)]">
                {transactions.map((t) => (
                  <tr key={t.id}>
                    <td className="py-2">{t.date}</td>
                    <td className={t.amount >= 0 ? 'text-[var(--a-positive)]' : 'text-[var(--a-negative)]'}>{money(t.amount)} {t.currency}</td>
                    <td>{t.category}<div className="text-[var(--a-muted)]">{t.description}</div></td>
                    <td>{t.account_name || '-'}</td>
                    <td>{t.source}</td>
                    <td className="text-right"><Button variant="negative" onClick={() => onDeleteTransaction(t.id)}>Eliminar</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="a-surface p-4" aria-labelledby="data-reconciliation-title">
        <h2 id="data-reconciliation-title" className="a-page-kicker">Reconciliación Wallet</h2>
        <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <div className="mb-2 text-xs font-bold text-[var(--a-secondary)]">Cuentas sin mapping</div>
            {reconciliation?.unmapped_accounts.slice(0, 6).map((account) => (
              <div key={account.external_id} className="mb-2 flex flex-col gap-2 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2 text-xs sm:flex-row sm:items-center">
                <span className="flex-1 text-[var(--a-text)]">{account.external_name || account.external_id}</span>
                <select className={dataSelectClass} aria-label={`Asignar cuenta ${account.external_name || account.external_id}`} onChange={(e) => e.target.value && saveAccountMapping(account.external_id, account.external_name, e.target.value)} defaultValue="">
                  <option value="">Asignar...</option>
                  {accounts.filter((a) => a.source !== 'BUDGETBAKERS').map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                  <option value={account.local_id || ''}>Usar cuenta importada</option>
                </select>
              </div>
            ))}
            {(!reconciliation || reconciliation.unmapped_accounts.length === 0) && <div className="a-meta">Sin cuentas pendientes.</div>}
          </div>
          <div>
            <div className="mb-2 text-xs font-bold text-[var(--a-secondary)]">Categorías frecuentes sin mapping</div>
            {reconciliation?.unmapped_categories.slice(0, 8).map((category) => (
              <div key={category.external_name} className="mb-2 flex flex-col gap-2 rounded-[var(--a-radius-sm)] border border-[var(--a-line)] bg-[var(--a-canvas)] p-2 text-xs sm:flex-row sm:items-center">
                <span className="flex-1 text-[var(--a-text)]">{category.external_name}<span className="text-[var(--a-muted)]"> · {category.count}</span></span>
                <select className={dataSelectClass} aria-label={`Asignar categoría ${category.external_name}`} onChange={(e) => e.target.value && saveCategoryMapping(category.external_name, e.target.value)} defaultValue="">
                  <option value="">Asignar...</option>
                  {categories.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                </select>
              </div>
            ))}
            {(!reconciliation || reconciliation.unmapped_categories.length === 0) && <div className="a-meta">Sin categorías pendientes.</div>}
          </div>
        </div>
      </section>
    </section>
      {openTool === 'csv' && (
        <ToolSurfaceDock
          id="data-csv-dock"
          title="Importar CSV"
          description="Columnas soportadas: date, amount, category, description, currency, account_id, external_id."
          triggerRef={csvLauncherRef}
          onClose={() => setOpenTool(null)}
        >
          <div className="space-y-4">
            <div>
              <label htmlFor="data-csv-file" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Archivo CSV</label>
              <input id="data-csv-file" type="file" accept=".csv,text/csv" onChange={(e) => handleFile(e.target.files?.[0])} className="text-xs text-[var(--a-secondary)]" />
            </div>
            <div>
              <label htmlFor="data-csv-text" className="mb-1.5 block text-xs font-bold text-[var(--a-secondary)]">Contenido CSV</label>
              <textarea id="data-csv-text" className={dataAreaClass} placeholder="O pegue CSV aquí" value={csvText} onChange={(e) => setCsvText(e.target.value)} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="quiet" onClick={async () => setCsvResult(await onPreviewCsv(csvText))}>Preview</Button>
              <Button variant="primary" onClick={async () => setCsvResult(await onImportCsv(csvText))}>Importar aceptadas</Button>
            </div>
            {csvResult && (
              <div className="grid grid-cols-2 gap-3">
                <InlineMetric label="Aceptadas" value={String(csvResult.accepted_count)} />
                <InlineMetric label="Rechazadas" value={String(csvResult.rejected_count)} />
                <InlineMetric label="Importadas" value={String(csvResult.imported_count ?? '-')} />
                <InlineMetric label="Duplicadas" value={String(csvResult.duplicate_count ?? '-')} />
              </div>
            )}
          </div>
        </ToolSurfaceDock>
      )}
      {openTool === 'wallet' && (
        <ToolSurfaceDock
          id="data-wallet-dock"
          title="Wallet by BudgetBakers"
          description="Estado, preview e importación de la fuente BudgetBakers."
          triggerRef={walletLauncherRef}
          onClose={() => setOpenTool(null)}
        >
          <div className="space-y-4">
            <p className="a-meta">
              Fuente REAL solo lectura. Token en backend:{' '}
              <span className={walletStatus?.configured ? 'text-[var(--a-positive)]' : 'text-[var(--a-warning)]'}>{walletStatus?.configured ? 'configurado' : 'no configurado'}</span>
              {walletStatus?.last_success_at ? ` · ultimo import: ${walletStatus.last_success_at}` : ''}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="operational" disabled={walletBusy} onClick={runWalletTest}>Probar</Button>
              <Button variant="quiet" disabled={walletBusy || !walletStatus?.configured} onClick={previewWallet}>Preview</Button>
              <Button variant="primary" disabled={walletBusy || !walletPreview} onClick={importWallet}>Confirmar importación</Button>
            </div>
            <div className="a-meta">
              Estado: <span className="text-[var(--a-text)]">{walletStatus?.status || 'sin leer'}</span>
              {walletStatus?.last_error ? <span className="text-[var(--a-negative)]"> · {walletStatus.last_error}</span> : null}
            </div>
            {walletPreview && (
              <div className="grid grid-cols-2 gap-3">
                <InlineMetric label="Cuentas" value={String(walletPreview.accounts_detected)} />
                <InlineMetric label="Registros" value={String(walletPreview.records_found)} />
                <InlineMetric label="Nuevos" value={String(walletPreview.new_transaction_count)} />
                <InlineMetric label="Duplicados" value={String(walletPreview.duplicate_count)} />
                <InlineMetric label="Rechazados" value={String(walletPreview.rejected_count)} />
                <InlineMetric label="Rango" value={`${walletPreview.date_range?.from || '-'} / ${walletPreview.date_range?.to || '-'}`} />
                <InlineMetric label="Cuentas nuevas" value={String(walletPreview.new_accounts)} />
                <InlineMetric label="Fuente" value="BUDGETBAKERS" />
              </div>
            )}
          </div>
        </ToolSurfaceDock>
      )}
      {openTool === 'etoro' && (
        <ToolSurfaceDock
          id="data-etoro-dock"
          title="eToro read-only"
          description="Estado, preview e importación de la fuente eToro."
          triggerRef={etoroLauncherRef}
          onClose={() => setOpenTool(null)}
        >
          <div className="space-y-4">
            <p className="a-meta">
              Fuente REAL solo lectura para inversión. Keys en backend:{' '}
              <span className={etoroStatus?.configured ? 'text-[var(--a-positive)]' : 'text-[var(--a-warning)]'}>{etoroStatus?.configured ? 'configuradas' : 'no configuradas'}</span>
              {etoroStatus?.environment ? ` · ${etoroStatus.environment}` : ''}
              {etoroStatus?.last_success_at ? ` · ultimo import: ${etoroStatus.last_success_at}` : ''}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="operational" disabled={etoroBusy} onClick={runEtoroTest}>Probar</Button>
              <Button variant="quiet" disabled={etoroBusy || !etoroStatus?.configured} onClick={previewEtoro}>Preview</Button>
              <Button variant="primary" disabled={etoroBusy || !etoroPreview || !etoroPreview.import_enabled || etoroPreview.history_status !== 'READY' || (etoroPreview.local_conflict_count ?? 0) > 0} onClick={importEtoro}>Confirmar importación</Button>
            </div>
            <div className="a-meta">
              Estado: <span className="text-[var(--a-text)]">{etoroStatus?.status || 'sin leer'}</span>
              {etoroStatus?.last_error ? <span className="text-[var(--a-negative)]"> · {etoroStatus.last_error}</span> : null}
            </div>
            {etoroPreview && (
              <div className="max-h-[70vh] space-y-3 overflow-y-auto pr-1">
                <div className="grid grid-cols-2 gap-2">
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Posiciones</div><div className="text-[var(--a-text)] font-bold">{etoroPreview.positions_found}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Operaciones</div><div className="text-[var(--a-text)] font-bold">{etoroPreview.operations_found ?? 'No evaluado'}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Importables</div><div className="text-[var(--a-positive)] font-bold">{etoroPreview.ready_to_import_count ?? etoroPreview.new_count}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Duplicadas</div><div className="text-[var(--a-warning)] font-bold">{etoroPreview.duplicate_count}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Rechazadas</div><div className="text-[var(--a-negative)] font-bold">{etoroPreview.rejected_count}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Sin mapping</div><div className="text-[var(--a-warning)] font-bold">{etoroPreview.unmapped_count}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Unsupported</div><div className="text-[var(--a-negative)] font-bold">{etoroPreview.unsupported_count}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Conflictos</div><div className="text-[var(--a-negative)] font-bold">{etoroPreview.local_conflict_count ?? 0}</div></div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Updates</div><div className="text-[var(--a-text)] font-bold">{etoroPreview.update_candidate_count ?? 0}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Periodo</div><div className="text-[var(--a-text)]">{etoroPreview.period?.from || '-'} / {etoroPreview.period?.to || '-'}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">FX faltante</div><div className="text-[var(--a-warning)] font-bold">{etoroPreview.missing_fx?.join(', ') || '-'}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Ambiente</div><div className="text-[var(--a-text)] font-bold">{etoroPreview.environment_label || `ETORO ${etoroPreview.environment.toUpperCase()}`}</div></div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Snapshot</div><div className="text-[var(--a-text)] font-bold">{etoroPreview.snapshot_status || '-'}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Historial</div><div className="text-[var(--a-warning)] font-bold">{etoroPreview.history_status || 'NOT_AVAILABLE'}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">PnL cuenta</div><div className="text-[var(--a-text)] font-bold">{etoroPreview.snapshot?.account_pnl_reconciliation?.status || '-'}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Preview</div><div className={etoroPreview.preview_valid ? 'text-[var(--a-positive)] font-bold' : 'text-[var(--a-negative)] font-bold'}>{etoroPreview.preview_valid ? 'VALIDO' : 'STALE'}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Gates</div><div className={etoroPreview.import_gates?.status === 'PASS' ? 'text-[var(--a-positive)] font-bold' : 'text-[var(--a-warning)] font-bold'}>{etoroPreview.import_gates?.status || '-'}</div></div>
                  <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Backup/import</div><div className="text-[var(--a-text)] font-bold">{etoroPreview.backup?.created ? 'BACKUP OK' : etoroPreview.import_status || '-'}</div></div>
                </div>
                {etoroPreview.import_gates?.failures?.length ? (
                  <div className={dataWarningClass}>
                    {etoroPreview.import_gates.failures.join(' · ')}
                  </div>
                ) : null}
                {etoroPreview.history_summary && (
                  <div className="grid grid-cols-2 gap-2">
                    <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Rows history</div><div className="text-[var(--a-text)] font-bold">{etoroPreview.history_summary.rows_downloaded ?? etoroPreview.history_summary.rows ?? 0}</div></div>
                    <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Compatibles</div><div className="text-[var(--a-positive)] font-bold">{etoroPreview.history_summary.compatible ?? 0}</div></div>
                    <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Parciales</div><div className="text-[var(--a-warning)] font-bold">{etoroPreview.history_summary.partial ?? 0}</div></div>
                    <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Conflictos ID</div><div className="text-[var(--a-negative)] font-bold">{etoroPreview.history_summary.identity_conflicts ?? 0}</div></div>
                    <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Stop</div><div className="text-[var(--a-secondary)] font-bold">{etoroPreview.history_summary.stop_reason || '-'}</div></div>
                  </div>
                )}
                {etoroPreview.history_status !== 'READY' && (
                  <div className={dataWarningClass}>
                    Historial eToro no disponible/no validado todavía. La importación permanece deshabilitada y no se muestran falsos 0 históricos.
                  </div>
                )}
                {etoroPreview.history_status === 'READY' && !etoroPreview.import_enabled && (
                  <div className={dataWarningClass}>
                    Historial eToro disponible en modo dry-run. La importación real permanece deshabilitada en esta fase.
                  </div>
                )}
                {etoroPreview.snapshot && (
                  <div className="grid grid-cols-2 gap-2">
                    <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Direct</div><div className="text-[var(--a-text)]">{etoroPreview.snapshot.direct_summary?.positions ?? 0} posiciones · PnL {money(etoroPreview.snapshot.direct_summary?.unrealized_pnl ?? 0)}</div></div>
                    <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">Mirrors</div><div className="text-[var(--a-text)]">{etoroPreview.snapshot.mirror_summary?.mirrors ?? 0} mirrors · {etoroPreview.snapshot.mirror_summary?.internal_positions ?? 0} internas</div></div>
                    <div className={dataEvidenceClass}><div className="text-[var(--a-muted)]">PnL reconstruido</div><div className="text-[var(--a-text)]">{money(etoroPreview.snapshot.account_pnl_reconciliation?.reconstructed_total_pnl ?? 0)}</div></div>
                  </div>
                )}
                {etoroPreview.optional_warnings?.length ? (
                  <div className={dataWarningClass}>
                    {etoroPreview.optional_warnings.slice(0, 3).map((warning) => <div key={warning}>{warning}</div>)}
                  </div>
                ) : null}
                {etoroPreview.mapping_suggestions?.length ? (
                  <div className="space-y-2 border-t border-[var(--a-line)] pt-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-xs font-bold text-[var(--a-text)]">Instrument mapping eToro → Finance</div>
                      <Button variant="operational" onClick={confirmSelectedEtoroMappings}>Confirmar seleccionados</Button>
                    </div>
                    <div className="space-y-2">
                      {etoroPreview.mapping_suggestions.map((item) => {
                        const key = etoroKey(item);
                        const current = etoroMappings.find((mapping) => mapping.external_id === item.external_id);
                        return (
                          <div key={key} className={`${dataEvidenceClass} space-y-2`}>
                            <div className="flex items-center justify-between gap-2">
                              <label className="flex min-w-0 items-center gap-2">
                                <input type="checkbox" checked={selectedEtoroIds.includes(key)} onChange={() => toggleEtoroSelection(key)} />
                                <span className="truncate font-medium">{item.external_name}</span>
                              </label>
                              <span className={`shrink-0 font-bold ${item.status === 'READY' ? 'text-[var(--a-positive)]' : 'text-[var(--a-warning)]'}`}>{current?.is_active === 0 ? 'UNSUPPORTED' : item.status}</span>
                            </div>
                            <div className="flex flex-wrap gap-x-3 text-[10px] text-[var(--a-muted)]">
                              <span className="font-mono">{item.external_id || '-'}</span>
                              <span>{item.symbol || ''}</span>
                            </div>
                            <div className="flex flex-wrap gap-x-3 text-[10px] text-[var(--a-muted)]">
                              <span>Tipo: {item.instrument_type || '-'}</span>
                              <span>Moneda: {item.currency || '-'}</span>
                            </div>
                            <label className="block space-y-1">
                              <span className="a-meta block">Mapping</span>
                              <select className={`${dataSelectClass} w-full`} value={etoroTargets[key] || current?.local_id || ''} onChange={(e) => setEtoroTargets({ ...etoroTargets, [key]: e.target.value })}>
                                <option value="">Seleccionar...</option>
                                {item.suggested.map((candidate) => <option key={`${key}-${candidate.ticker}`} value={candidate.ticker}>{candidate.ticker} · {candidate.confidence}</option>)}
                                {assets.map((asset) => <option key={`${key}-${asset.ticker}`} value={asset.ticker}>{asset.ticker} · {asset.name}</option>)}
                              </select>
                            </label>
                            {item.suggested.length > 0 && <div className="text-[10px] text-[var(--a-muted)]">suggested ≠ confirmed</div>}
                            <div className="flex flex-wrap gap-2">
                              <Button variant="positive" onClick={() => saveSingleEtoroMapping(item)}>Guardar</Button>
                              <Button variant="quiet" onClick={() => createAssetFromEtoro(item)}>Crear asset</Button>
                              <Button variant="negative" onClick={() => markUnsupported(item)}>Unsupported</Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
                {etoroPreview.dry_run && (
                  <div className="grid grid-cols-1 gap-2 border-t border-[var(--a-line)] pt-3">
                    <div className={dataEvidenceClass}>
                      <div className="mb-1 font-bold text-[var(--a-muted)]">Dry-run ledger</div>
                      <div>Nuevas: <span className="text-[var(--a-positive)]">{etoroPreview.dry_run.new_operations}</span></div>
                      <div>Updates: <span className="text-[var(--a-warning)]">{etoroPreview.dry_run.update_candidates}</span></div>
                      <div>Conflictos: <span className="text-[var(--a-negative)]">{etoroPreview.dry_run.local_conflicts}</span></div>
                    </div>
                    <div className={dataEvidenceClass}>
                      <div className="mb-1 font-bold text-[var(--a-muted)]">Coverage</div>
                      {etoroPreview.dry_run.history_coverage.slice(0, 5).map((row) => <div key={`${row.ticker}-${row.external_id}`} className="flex justify-between gap-2"><span>{row.ticker || row.external_name}</span><span className="text-[var(--a-text)]">{row.coverage}</span></div>)}
                    </div>
                    <div className={dataEvidenceClass}>
                      <div className="mb-1 font-bold text-[var(--a-muted)]">Opening position assist</div>
                      {etoroPreview.dry_run.opening_position_suggestions.slice(0, 4).map((item) => (
                        <div key={item.ticker} className="flex items-center justify-between gap-2">
                          <span>{item.ticker} · {item.quantity}</span>
                          <Button variant="positive" disabled={item.requires_user_cost_basis || item.requires_user_opened_at} onClick={() => saveOpeningFromSuggestion(item)}>Requiere datos</Button>
                        </div>
                      ))}
                      {etoroPreview.dry_run.opening_position_suggestions.length === 0 && <div className="text-[var(--a-muted)]">Sin sugerencias.</div>}
                    </div>
                  </div>
                )}
                {(etoroPreview.unmapped_instruments.length > 0 || etoroPreview.unsupported_instruments.length > 0 || (etoroPreview.reconciliation?.issues.length || 0) > 0) && (
                  <div className="grid grid-cols-1 gap-2 border-t border-[var(--a-line)] pt-3">
                    <div className={dataEvidenceClass}>
                      <div className="mb-1 font-bold text-[var(--a-muted)]">Instrumentos sin mapping</div>
                      {etoroPreview.unmapped_instruments.slice(0, 4).map((item) => <div key={`${item.external_instrument_id}-${item.external_name}`} className="truncate text-[var(--a-warning)]">{item.external_name || item.external_instrument_id}</div>)}
                      {etoroPreview.unmapped_instruments.length === 0 && <div className="text-[var(--a-muted)]">Sin pendientes.</div>}
                    </div>
                    <div className={dataEvidenceClass}>
                      <div className="mb-1 font-bold text-[var(--a-muted)]">CFD/leverage/short</div>
                      {etoroPreview.unsupported_instruments.slice(0, 4).map((item) => <div key={`${item.external_id}-${item.external_name}`} className="truncate text-[var(--a-negative)]">{item.external_name || item.external_id}</div>)}
                      {etoroPreview.unsupported_instruments.length === 0 && <div className="text-[var(--a-muted)]">Sin bloqueos.</div>}
                    </div>
                    <div className={dataEvidenceClass}>
                      <div className="mb-1 font-bold text-[var(--a-muted)]">Ledger vs eToro</div>
                      {etoroPreview.reconciliation?.issues.slice(0, 4).map((item) => <div key={`${item.type}-${item.ticker}`} className="truncate text-[var(--a-warning)]">{item.ticker || item.type}: {item.type}</div>)}
                      {(!etoroPreview.reconciliation || etoroPreview.reconciliation.issues.length === 0) && <div className="text-[var(--a-muted)]">Sin diferencias.</div>}
                    </div>
                  </div>
                )}
              </div>
            )}
            <div className="space-y-2 border-t border-[var(--a-line)] pt-3">
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="quiet" onClick={exportConfig}>Exportar config mappings</Button>
                <Button variant="quiet" disabled={!mappingConfigText} onClick={validateConfig}>Validar JSON</Button>
                <Button variant="operational" disabled={!mappingConfigText} onClick={importConfig}>Importar config</Button>
              </div>
              <label htmlFor="data-etoro-config" className="a-meta block">JSON de config eToro/Market Data/Price Authority</label>
              <textarea id="data-etoro-config" className={dataAreaClass} placeholder="JSON de config eToro/Market Data/Price Authority" value={mappingConfigText} onChange={(e) => setMappingConfigText(e.target.value)} />
            </div>
          </div>
        </ToolSurfaceDock>
      )}
    </div>
  );
};
