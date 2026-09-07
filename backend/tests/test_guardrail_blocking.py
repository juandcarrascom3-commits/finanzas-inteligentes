"""
Unit Tests for Human Safety Guardrail Service (Filtro Humano)
Verifies:
- Evaluation of the 5 qualitative checklist criteria
- Strict blocking of purchase simulations when checklist is not passed
- Successful authorization and share calculation when criteria pass
"""

import pytest
from backend.services.guardrail_service import GuardrailService, TradeGuardrailBlockedError

def test_checklist_evaluation_success():
    criteria = {
        "knows_business_model": True,
        "debt_ebitda_healthy": True,
        "margin_safety_above_20": True,
        "timing_not_overbought": True,
        "emotional_bias_checked": True
    }
    is_passed, msg = GuardrailService.evaluate_checklist(
        valuation_grade=4,
        safety_margin_pct=25.0,
        timing_context="Consolidación técnica en soporte clave con volumen creciente.",
        criteria=criteria
    )
    assert is_passed is True
    assert "exitosamente" in msg

def test_checklist_evaluation_failures():
    # 1. Low valuation grade (<3)
    passed, msg = GuardrailService.evaluate_checklist(
        valuation_grade=2,
        safety_margin_pct=25.0,
        timing_context="Fase de rebote.",
        criteria={"knows_business_model": True, "debt_ebitda_healthy": True, "margin_safety_above_20": True, "timing_not_overbought": True, "emotional_bias_checked": True}
    )
    assert passed is False
    assert "insuficiente" in msg

    # 2. Insufficient safety margin (<20%)
    passed, msg = GuardrailService.evaluate_checklist(
        valuation_grade=4,
        safety_margin_pct=15.0,
        timing_context="Fase de rebote.",
        criteria={"knows_business_model": True, "debt_ebitda_healthy": True, "margin_safety_above_20": True, "timing_not_overbought": True, "emotional_bias_checked": True}
    )
    assert passed is False
    assert "Margen de seguridad insuficiente" in msg

    # 3. Missing one qualitative checkbox
    passed, msg = GuardrailService.evaluate_checklist(
        valuation_grade=4,
        safety_margin_pct=25.0,
        timing_context="Fase de rebote.",
        criteria={"knows_business_model": True, "debt_ebitda_healthy": False, "margin_safety_above_20": True, "timing_not_overbought": True, "emotional_bias_checked": True}
    )
    assert passed is False
    assert "Deuda Neta / EBITDA" in msg

def test_guardrail_blocks_unauthorized_simulation():
    unvalidated_thesis = {
        "ticker": "AAPL",
        "checklist_passed": False,
        "valuation_grade": 4,
        "safety_margin": 18.0
    }
    with pytest.raises(TradeGuardrailBlockedError) as excinfo:
        GuardrailService.simulate_purchase(
            ticker="AAPL",
            target_amount_usd=2500.0,
            current_price=220.0,
            thesis=unvalidated_thesis
        )
    assert "OPERACIÓN BLOQUEADA" in str(excinfo.value)

def test_guardrail_allows_validated_simulation():
    validated_thesis = {
        "ticker": "NVDA",
        "checklist_passed": True,
        "valuation_grade": 5,
        "safety_margin": 26.5
    }
    result = GuardrailService.simulate_purchase(
        ticker="NVDA",
        target_amount_usd=3000.0,
        current_price=120.0,
        thesis=validated_thesis
    )
    assert result["status"] == "AUTHORIZED"
    assert result["estimated_shares"] == 25.0
    assert result["guardrail_certified"] is True
