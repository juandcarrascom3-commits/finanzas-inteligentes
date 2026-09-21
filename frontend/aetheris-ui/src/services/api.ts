import type { DashboardSummary, PanoramaData, Asset, InvestmentThesis, BudgetBakersMapping } from '../types';

const API_BASE = 'http://127.0.0.1:8000/api';

export async function fetchDashboardData(): Promise<DashboardSummary | null> {
  try {
    const response = await fetch(`${API_BASE}/dashboard`);
    if (!response.ok) throw new Error('Error al conectar con el backend');
    return await response.json();
  } catch (error) {
    console.error('API Error (Dashboard):', error);
    return null;
  }
}

export async function fetchDashboard(exchangeRate: number = 4050): Promise<DashboardSummary> {
  const res = await fetch(`${API_BASE}/dashboard?exchange_rate=${exchangeRate}`);
  if (!res.ok) throw new Error(`HTTP error ${res.status}`);
  return res.json();
}

export async function fetchPanorama(): Promise<PanoramaData> {
  const res = await fetch(`${API_BASE}/panorama`);
  if (!res.ok) throw new Error(`HTTP error ${res.status}`);
  return res.json();
}

export async function fetchAssets(): Promise<Asset[]> {
  const res = await fetch(`${API_BASE}/assets`);
  if (!res.ok) throw new Error(`HTTP error ${res.status}`);
  return res.json();
}

export async function fetchTheses(): Promise<InvestmentThesis[]> {
  const res = await fetch(`${API_BASE}/theses`);
  if (!res.ok) throw new Error(`HTTP error ${res.status}`);
  return res.json();
}

export async function saveThesis(thesis: Partial<InvestmentThesis>): Promise<any> {
  const res = await fetch(`${API_BASE}/theses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(thesis)
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Error al guardar la tesis.');
  }
  return res.json();
}

export async function simulatePurchase(ticker: string, targetAmountUsd: number): Promise<any> {
  const res = await fetch(`${API_BASE}/simulate-purchase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, target_amount_usd: targetAmountUsd })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Operación bloqueada por el Filtro Humano.');
  }
  return res.json();
}

export async function fetchBudgetBakersMappings(): Promise<BudgetBakersMapping[]> {
  const res = await fetch(`${API_BASE}/budgetbakers/mappings`);
  if (!res.ok) throw new Error(`HTTP error ${res.status}`);
  return res.json();
}

export async function updateBudgetBakersMapping(mappingId: string, localCategory: string, isActive: boolean): Promise<any> {
  const res = await fetch(`${API_BASE}/budgetbakers/mappings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mapping_id: mappingId, local_category: localCategory, is_active: isActive })
  });
  if (!res.ok) throw new Error(`HTTP error ${res.status}`);
  return res.json();
}

export async function triggerBudgetBakersSync(forceRefresh: boolean = false): Promise<any> {
  const res = await fetch(`${API_BASE}/budgetbakers/sync?force_refresh=${forceRefresh}`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al sincronizar con BudgetBakers.');
  }
  return res.json();
}