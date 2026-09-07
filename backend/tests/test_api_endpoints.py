"""
API Integration & Route Verification Tests
Verifies that all FastAPI endpoints return 200 OK and conform to expected schemas.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

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
    assert len(data["temporal_evolution"]) == 12
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

def test_api_budgetbakers_sync():
    resp = client.post("/api/budgetbakers/sync")
    assert resp.status_code == 200
    data = resp.json()
    assert "fetch_source" in data
    assert "sync_details" in data
    assert data["daily_quota"]["max_quota"] == 25
