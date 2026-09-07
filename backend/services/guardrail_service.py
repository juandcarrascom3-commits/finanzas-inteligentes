"""
Investment Thesis & Human Safety Guardrail Service (Filtro Humano)
Enforces Investing Pro qualitative parameters:
- Valuation Grade (1-5)
- Timing Context
- Margin of Safety (minimum 20% threshold)
- 5-point Human Validation Checklist
STRICT ENFORCEMENT: Trade and purchase simulations are strictly BLOCKED until checklist_passed == True.
"""

from typing import Dict, Any, Tuple

class TradeGuardrailBlockedError(Exception):
    """Raised when an order or purchase simulation is attempted on an unvalidated thesis."""
    pass

class GuardrailService:
    @staticmethod
    def evaluate_checklist(
        valuation_grade: int,
        safety_margin_pct: float,
        timing_context: str,
        criteria: Dict[str, bool]
    ) -> Tuple[bool, str]:
        """
        Evaluates whether an investment thesis meets all mandatory risk and human safety criteria.
        Returns (is_passed: bool, message: str).
        """
        required_criteria = [
            ("knows_business_model", "Comprensión integral del modelo de negocio y ventajas competitivas (Moat)."),
            ("debt_ebitda_healthy", "Solvencia financiera: Deuda Neta / EBITDA menor a 3.0x."),
            ("margin_safety_above_20", "Margen de seguridad cuantitativo superior o igual al 20%."),
            ("timing_not_overbought", "Contexto técnico y macroeconómico fuera de sobrecompra extrema."),
            ("emotional_bias_checked", "Validación psicológica: Tesis contrastada contra FOMO y sesgos de confirmación.")
        ]

        # 1. Valuation Grade verification
        if valuation_grade < 3:
            return False, f"Calificación de valuación insuficiente ({valuation_grade}/5). Mínimo requerido: 3."

        # 2. Safety margin threshold
        if safety_margin_pct < 20.0:
            return False, f"Margen de seguridad insuficiente ({safety_margin_pct}%). El umbral de protección mínimo es 20.0%."

        # 3. Timing context present
        if not timing_context or len(timing_context.strip()) < 10:
            return False, "Contexto de timing insuficiente. Ingrese una justificación técnica o de ciclo de mercado."

        # 4. Mandatory checklist criteria
        for key, description in required_criteria:
            if not criteria.get(key, False):
                return False, f"Criterio de seguridad no superado: '{description}'"

        return True, "Todos los filtros cualitativos y cuantitativos han sido validados exitosamente."

    @staticmethod
    def simulate_purchase(
        ticker: str,
        target_amount_usd: float,
        current_price: float,
        thesis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulates capital deployment only if the thesis has passed the human safety checklist.
        Blocks the operation if safety criteria are not satisfied.
        """
        is_passed = bool(thesis.get("checklist_passed", False))
        if not is_passed:
            raise TradeGuardrailBlockedError(
                f"OPERACIÓN BLOQUEADA para {ticker}: El Filtro Humano de seguridad no ha sido validado. "
                f"Complete y certifique los 5 criterios de Investing Pro antes de simular o ejecutar compras."
            )

        shares_to_buy = target_amount_usd / current_price if current_price > 0 else 0
        return {
            "status": "AUTHORIZED",
            "ticker": ticker,
            "simulated_capital_usd": target_amount_usd,
            "unit_price_usd": current_price,
            "estimated_shares": round(shares_to_buy, 4),
            "safety_margin_validated": thesis.get("safety_margin", 0),
            "valuation_grade": thesis.get("valuation_grade", 0),
            "guardrail_certified": True
        }
