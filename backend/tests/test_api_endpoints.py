"""
API Integration & Route Verification Tests
Verifies that all FastAPI endpoints return 200 OK and conform to expected schemas.
"""

import pytest
import uuid
import json
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)


def _collect_keys(value):
    keys = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key).lower().replace("-", "_"))
            keys.extend(_collect_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_collect_keys(child))
    return keys

def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_api_dashboard():
    response = client.get("/api/dashboard?exchange_rate=4050")
    assert response.status_code == 200
    data = response.json()
    assert "kpis" in data
    assert "net_worth" in data["kpis"]
    assert data["kpis"]["net_worth"]["net_worth_usd"] > 0
    assert data["kpis"]["net_worth"]["net_worth_cop"] > 0
    assert "allocation_treemap" in data
    assert len(data["allocation_treemap"]) > 0
    assert "temporal_evolution" in data
    assert "daily_api_quota" in data

def test_api_panorama():
    response = client.get("/api/panorama")
    assert response.status_code == 200
    data = response.json()
    assert "projections_summary" in data
    assert "checklist" in data
    assert len(data["checklist"]) == 4

def test_api_assets():
    response = client.get("/api/assets")
    assert response.status_code == 200
    assets = response.json()
    assert len(assets) > 0
    nvda = next((a for a in assets if a["ticker"] == "NVDA"), None)
    assert nvda is not None
    assert nvda["unrealized_pnl_usd"] > 0

def test_api_theses_and_guardrail():
    # 1. Fetch theses
    resp = client.get("/api/theses")
    assert resp.status_code == 200
    theses = resp.json()
    assert len(theses) > 0

    # 2. Test simulation on authorized ticker (NVDA has checklist_passed = true in seed)
    sim_ok = client.post("/api/simulate-purchase", json={"ticker": "NVDA", "target_amount_usd": 1500.0})
    assert sim_ok.status_code == 200
    assert sim_ok.json()["status"] == "AUTHORIZED"

    # 3. Test simulation on blocked ticker (AAPL has checklist_passed = false in seed)
    sim_blocked = client.post("/api/simulate-purchase", json={"ticker": "AAPL", "target_amount_usd": 1500.0})
    assert sim_blocked.status_code == 403
    assert "OPERACIÓN BLOQUEADA" in sim_blocked.json()["detail"]

def test_api_budgetbakers_status_without_token(monkeypatch):
    monkeypatch.delenv("BUDGETBAKERS_API_TOKEN", raising=False)
    resp = client.get("/api/budgetbakers/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["status"] == "NOT_CONFIGURED"


def test_api_budgetbakers_legacy_sync_disabled():
    resp = client.post("/api/budgetbakers/sync")
    assert resp.status_code == 410

def test_personal_data_crud_csv_and_backup():
    account = client.post("/api/accounts", json={
        "name": "Cuenta diaria",
        "account_type": "checking",
        "currency": "USD",
        "opening_balance": 100,
        "current_balance": 100
    })
    assert account.status_code == 200
    account_id = account.json()["id"]

    asset = client.post("/api/assets", json={
        "ticker": "TEST",
        "name": "Test Asset",
        "asset_type": "Renta Variable",
        "sector": "Testing",
        "country": "Global",
        "quantity": 2,
        "avg_price": 10,
        "current_price": 12,
        "currency": "USD"
    })
    assert asset.status_code == 200

    tx = client.post("/api/transactions", json={
        "account_id": account_id,
        "amount": -25.5,
        "category": "General",
        "date": "2026-09-20",
        "description": "Compra prueba",
        "currency": "USD"
    })
    assert tx.status_code == 200

    listed = client.get("/api/transactions")
    assert listed.status_code == 200
    assert any(item["description"] == "Compra prueba" for item in listed.json())

    csv_id = f"csv-{uuid.uuid4()}"
    csv_payload = {"content": f"date,amount,category,description,currency,external_id\n2026-09-21,100,Ingresos,Ingreso CSV,USD,{csv_id}\nbad,,General,Rota,USD,{csv_id}-bad"}
    preview = client.post("/api/import/transactions/preview", json=csv_payload)
    assert preview.status_code == 200
    assert preview.json()["accepted_count"] == 1
    assert preview.json()["rejected_count"] == 1

    imported = client.post("/api/import/transactions", json=csv_payload)
    assert imported.status_code == 200
    assert imported.json()["imported_count"] == 1

    duplicate = client.post("/api/import/transactions", json=csv_payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate_count"] >= 1

    backup = client.get("/api/backup")
    assert backup.status_code == 200
    assert "db_backup_path" in backup.json()

    assert client.delete(f"/api/transactions/{tx.json()['id']}").status_code == 200
    assert client.delete("/api/assets/TEST").status_code == 200
    assert client.delete(f"/api/accounts/{account_id}").status_code == 200


def test_understand_and_reconciliation_endpoints():
    reconciliation = client.get("/api/reconciliation")
    assert reconciliation.status_code == 200
    assert "unmapped_accounts" in reconciliation.json()

    mapping = client.post("/api/source-mappings", json={
        "source": "BUDGETBAKERS",
        "external_type": "category",
        "external_id": "Food",
        "external_name": "Food",
        "local_id": "Alimentacion",
        "local_type": "category",
        "is_active": True
    })
    assert mapping.status_code == 200

    budget = client.post("/api/budgets", json={"category": "Alimentacion", "monthly_limit": 500, "currency": "USD"})
    assert budget.status_code == 200

    understand = client.get("/api/understand?period=current_month")
    assert understand.status_code == 200
    data = understand.json()
    assert "what_changed" in data
    assert "cashflow_forecast" in data
    assert "action_items" in data


def test_analysis_export_endpoint_returns_structured_json_without_sensitive_keys():
    response = client.get("/api/analysis-export?period=current_month")
    assert response.status_code == 200
    data = response.json()
    json.dumps(data)
    assert "period" in data
    assert "what_changed" in data
    assert "cash_flow" in data
    assert "data_confidence" in data
    sensitive = {"token", "api_key", "apikey", "authorization", "password", "secret", "client_secret", "access_token"}
    assert sensitive.isdisjoint(set(_collect_keys(data)))


def test_calculator_endpoints_contracts_and_validation():
    compound = client.post("/api/calculators/compound", json={"principal": 1000000, "periodic_contribution": 100000, "annual_effective_rate_pct": 12, "periods": 12, "contribution_timing": "END", "currency": "COP"})
    assert compound.status_code == 200
    assert compound.json()["future_value"] > 2_300_000
    assert compound.json()["assumptions"]["contribution_timing"] == "END"

    goal = client.post("/api/calculators/savings-goal", json={"target": 12000000, "current_amount": 3000000, "annual_effective_rate_pct": 0, "periods": 9, "currency": "COP"})
    assert goal.status_code == 200
    assert goal.json()["required_contribution"] == 1_000_000

    eta = client.post("/api/calculators/goal-eta", json={"target": 5000000, "current_amount": 2000000, "periodic_contribution": 500000, "annual_effective_rate_pct": 0})
    assert eta.status_code == 200
    assert eta.json()["periods_required"] == 6

    emergency = client.post("/api/calculators/emergency-fund", json={"liquid_resources": 1000, "essential_monthly_expenses": 0})
    assert emergency.status_code == 200
    assert emergency.json()["evaluability"] == "UNEVALUABLE"

    debt = client.post("/api/calculators/debt-payoff", json={"balance": 12000000, "annual_effective_rate_pct": 0, "monthly_payment": 1000000, "extra_payment": 0})
    assert debt.status_code == 200
    assert debt.json()["periods"] == 12

    opportunity = client.post("/api/calculators/opportunity-cost", json={"amount": 1000000, "annual_effective_rate_pct": 12, "periods": 12})
    assert opportunity.status_code == 200
    assert opportunity.json()["opportunity_cost"] > 100000

    invalid = client.post("/api/calculators/compound", json={"principal": 1, "periodic_contribution": 0, "annual_effective_rate_pct": -100, "periods": 1})
    assert invalid.status_code == 422


def test_financial_events_endpoint_returns_expected_recurring_events():
    for idx, day in enumerate(["2026-09-01", "2026-09-08", "2026-09-15", "2026-09-22"]):
        created = client.post("/api/transactions", json={
            "amount": -100,
            "category": "General",
            "date": day,
            "description": "Wave3 Weekly Test",
            "currency": "USD",
            "external_id": f"wave3-weekly-{idx}",
        })
        assert created.status_code == 200
    response = client.get("/api/financial-events?from=2026-09-23&to=2026-10-14")
    assert response.status_code == 200
    data = response.json()
    events = [event for event in data["events"] if event["label"].startswith("wave3 weekly test")]
    assert [event["date"] for event in events] == ["2026-09-29", "2026-10-06", "2026-10-13"]
    assert all(event["certainty"] == "EXPECTED" for event in events)


def test_phase4_budget_recurring_monthly_review_endpoints():
    wallet_plan = client.post("/api/budgetbakers/import-plan", json={
        "budgets": [{"category": "Wallet Food", "monthly_limit": 250, "currency": "USD", "external_id": "bb-budget-1"}],
        "standing_orders": [{"merchant": "Wallet Rent", "typical_amount": -900, "category": "Vivienda", "frequency": "monthly", "external_id": "bb-so-1", "next_expected": "2026-10-01"}]
    })
    assert wallet_plan.status_code == 200
    assert wallet_plan.json()["imported_budgets"] == 1

    budget = client.post("/api/budgets", json={
        "category": "Transporte",
        "monthly_limit": 300,
        "currency": "USD",
        "period": "MONTHLY",
        "is_active": True
    })
    assert budget.status_code == 200
    budget_id = budget.json()["id"]

    budgets = client.get("/api/budgets")
    assert budgets.status_code == 200
    assert any(item["id"] == budget_id for item in budgets.json())

    recurring = client.get("/api/recurring")
    assert recurring.status_code == 200
    if recurring.json():
        rule_id = recurring.json()[0]["id"]
        updated = client.patch(f"/api/recurring/{rule_id}", json={"status": "confirmed"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "confirmed"

    review = client.get("/api/monthly-review?period=2026-09")
    assert review.status_code == 200
    review_data = review.json()
    assert review_data["period"] == "2026-09"
    assert "budget_variances" in review_data
    assert "action_items" in review_data

    snapshot = client.post("/api/monthly-review/snapshot?period=2026-09")
    assert snapshot.status_code == 200
    snapshots = client.get("/api/monthly-review/snapshots")
    assert snapshots.status_code == 200
    assert any(item["period"] == "2026-09" for item in snapshots.json())

    assert client.delete(f"/api/budgets/{budget_id}").status_code == 200
