"""Investment ledger analytics: FIFO lots, realized P&L, cashflows and reconciliation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.analytics.metrics import calculate_mwr_irr

EXTERNAL_CASHFLOW_TYPES = {"CONTRIBUTION", "WITHDRAWAL"}
PORTFOLIO_OPERATION_TYPES = {"BUY", "SELL", "DIVIDEND", "INTEREST", "FEE"}
INTERNAL_MOVEMENT_TYPES = {"TRANSFER_IN", "TRANSFER_OUT"}


def _date(value: str):
    return datetime.fromisoformat(str(value)[:19].replace("Z", "+00:00")).date()


def _signed_cashflow(op: Dict[str, Any]) -> float:
    amount = abs(float(op.get("amount") or 0))
    if op["operation_type"] == "CONTRIBUTION":
        return amount
    if op["operation_type"] == "WITHDRAWAL":
        return -amount
    return 0.0


def _trade_gross_amount(op: Dict[str, Any]) -> float:
    amount = abs(float(op.get("amount") or 0))
    if amount > 0:
        return amount
    return abs(float(op.get("quantity") or 0) * float(op.get("price") or 0))


def match_lots_fifo(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    lots_by_ticker: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    realized = []
    issues = []

    for op in sorted(operations, key=lambda item: (item["occurred_at"], item["id"])):
        op_type = op["operation_type"]
        ticker = (op.get("ticker") or "").upper()
        currency = (op.get("currency") or "USD").upper()
        qty = float(op.get("quantity") or 0)
        fee = abs(float(op.get("fee") or 0))

        if op_type == "BUY":
            gross = _trade_gross_amount(op)
            total_cost = gross + fee
            unit_cost = total_cost / qty if qty else 0.0
            lots_by_ticker[ticker].append({
                "ticker": ticker,
                "buy_transaction_id": op["id"],
                "acquired_at": op["occurred_at"],
                "original_quantity": qty,
                "remaining_quantity": qty,
                "unit_cost": unit_cost,
                "total_cost": total_cost,
                "currency": currency,
            })

        elif op_type == "SELL":
            remaining_to_sell = qty
            sale_gross = _trade_gross_amount(op)
            proceeds_after_fee = sale_gross - fee
            cost_basis = 0.0
            matches = []
            for lot in lots_by_ticker[ticker]:
                if remaining_to_sell <= 1e-9:
                    break
                available = float(lot["remaining_quantity"])
                if available <= 1e-9:
                    continue
                used = min(available, remaining_to_sell)
                matched_cost = used * float(lot["unit_cost"])
                lot["remaining_quantity"] = round(available - used, 10)
                remaining_to_sell -= used
                cost_basis += matched_cost
                matches.append({"buy_transaction_id": lot["buy_transaction_id"], "quantity": used, "cost_basis": round(matched_cost, 2)})

            if remaining_to_sell > 1e-9:
                issues.append({
                    "type": "INSUFFICIENT_LOTS",
                    "ticker": ticker,
                    "operation_id": op["id"],
                    "message": f"SELL {ticker} exceeds available FIFO lots by {round(remaining_to_sell, 8)}.",
                    "action": "Import missing BUY operations before trusting realized P&L.",
                })
                continue

            realized.append({
                "sell_transaction_id": op["id"],
                "ticker": ticker,
                "occurred_at": op["occurred_at"],
                "quantity": qty,
                "proceeds": round(proceeds_after_fee, 2),
                "cost_basis": round(cost_basis, 2),
                "fee": round(fee, 2),
                "realized_pnl": round(proceeds_after_fee - cost_basis, 2),
                "currency": currency,
                "matches": matches,
            })

    lots = [lot for ticker_lots in lots_by_ticker.values() for lot in ticker_lots]
    open_lots = [lot for lot in lots if float(lot["remaining_quantity"]) > 1e-9]
    return {"lots": lots, "open_lots": open_lots, "realized_trades": realized, "issues": issues}


def derive_positions(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    matched = match_lots_fifo(operations)
    positions: Dict[str, Dict[str, Any]] = {}
    for lot in matched["open_lots"]:
        ticker = lot["ticker"]
        pos = positions.setdefault(ticker, {"ticker": ticker, "quantity": 0.0, "remaining_cost_basis": 0.0, "currency": lot["currency"]})
        qty = float(lot["remaining_quantity"])
        pos["quantity"] += qty
        pos["remaining_cost_basis"] += qty * float(lot["unit_cost"])
    for pos in positions.values():
        pos["quantity"] = round(pos["quantity"], 8)
        pos["remaining_cost_basis"] = round(pos["remaining_cost_basis"], 2)
        pos["avg_cost"] = round(pos["remaining_cost_basis"] / pos["quantity"], 6) if pos["quantity"] else 0.0
    return {"positions": list(positions.values()), **matched}


def get_realized_pnl(operations: List[Dict[str, Any]], ticker: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    realized = match_lots_fifo(operations)
    rows = realized["realized_trades"]
    if ticker:
        rows = [row for row in rows if row["ticker"] == ticker.upper()]
    if start:
        rows = [row for row in rows if row["occurred_at"][:10] >= start[:10]]
    if end:
        rows = [row for row in rows if row["occurred_at"][:10] <= end[:10]]
    by_ticker: Dict[str, float] = defaultdict(float)
    for row in rows:
        by_ticker[row["ticker"]] += float(row["realized_pnl"])
    return {
        "status": "AVAILABLE" if not realized["issues"] else "PARTIAL",
        "total_realized_pnl": round(sum(float(row["realized_pnl"]) for row in rows), 2),
        "by_ticker": [{"ticker": key, "realized_pnl": round(value, 2)} for key, value in sorted(by_ticker.items())],
        "trades": rows,
        "issues": realized["issues"],
    }


def get_investment_income(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    dividends: Dict[str, float] = defaultdict(float)
    interest = 0.0
    fees = 0.0
    for op in operations:
        amount = abs(float(op.get("amount") or 0))
        fee = abs(float(op.get("fee") or 0))
        if op["operation_type"] == "DIVIDEND":
            dividends[(op.get("ticker") or "UNKNOWN").upper()] += amount
        elif op["operation_type"] == "INTEREST":
            interest += amount
        elif op["operation_type"] == "FEE":
            fees += amount
        if op["operation_type"] in {"BUY", "SELL"}:
            fees += fee
    return {
        "dividends_total": round(sum(dividends.values()), 2),
        "dividends_by_ticker": [{"ticker": ticker, "amount": round(value, 2)} for ticker, value in sorted(dividends.items())],
        "interest_total": round(interest, 2),
        "fees_total": round(fees, 2),
    }


def get_investment_cashflows(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    for op in operations:
        if op["operation_type"] in EXTERNAL_CASHFLOW_TYPES:
            rows.append({"date": op["occurred_at"][:10], "amount": _signed_cashflow(op), "operation_id": op["id"], "type": op["operation_type"]})
    return {"cashflows": rows, "total_external_cashflow": round(sum(row["amount"] for row in rows), 2)}


def calculate_mwr(operations: List[Dict[str, Any]], final_value: float, final_date: Optional[str] = None) -> Dict[str, Any]:
    cashflows = get_investment_cashflows(operations)["cashflows"]
    if not cashflows:
        return {"status": "INSUFFICIENT_DATA", "value_pct": None, "reason": "No contribution/withdrawal operations exist."}
    end_date = _date(final_date or max([row["date"] for row in cashflows]))
    first_date = min(_date(row["date"]) for row in cashflows)
    flows: List[Tuple[float, float]] = []
    for row in cashflows:
        # Investor cashflows: contributions are cash outflows into portfolio; withdrawals are inflows back to investor.
        flows.append(((_date(row["date"]) - first_date).days / 365.25, -float(row["amount"])))
    flows.append(((end_date - first_date).days / 365.25, float(final_value)))
    try:
        value = calculate_mwr_irr(flows)
    except Exception as exc:
        return {"status": "INSUFFICIENT_DATA", "value_pct": None, "reason": f"XIRR did not converge: {exc}"}
    return {"status": "AVAILABLE", "value_pct": value, "reason": None}


def get_unrealized_pnl_from_lots(assets: List[Dict[str, Any]], operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    positions = {row["ticker"]: row for row in derive_positions(operations)["positions"]}
    rows = []
    total = 0.0
    issues = []
    for asset in assets:
        ticker = asset["ticker"].upper()
        position = positions.get(ticker)
        if not position:
            continue
        if (asset.get("currency") or "USD").upper() != position["currency"]:
            issues.append({"type": "INSUFFICIENT_FX_DATA", "ticker": ticker, "message": "Asset currency differs from ledger lot currency.", "action": "Add historical FX before aggregating."})
            continue
        market_value = float(asset.get("quantity") or 0) * float(asset.get("current_price") or 0)
        pnl = market_value - float(position["remaining_cost_basis"])
        total += pnl
        rows.append({"ticker": ticker, "market_value": round(market_value, 2), "cost_basis": position["remaining_cost_basis"], "unrealized_pnl": round(pnl, 2), "currency": position["currency"]})
    return {"status": "AVAILABLE" if rows and not issues else ("PARTIAL" if rows else "INSUFFICIENT_DATA"), "total_unrealized_pnl": round(total, 2), "by_ticker": rows, "issues": issues}


def get_ledger_reconciliation(assets: List[Dict[str, Any]], operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    positions = {row["ticker"]: row for row in derive_positions(operations)["positions"]}
    rows = []
    issues = []
    for asset in assets:
        if asset.get("is_watchlist"):
            continue
        ticker = asset["ticker"].upper()
        registered_qty = round(float(asset.get("quantity") or 0), 8)
        derived = positions.get(ticker)
        if not derived:
            status = "INSUFFICIENT_HISTORY"
            derived_qty = 0.0
            derived_avg = 0.0
        else:
            derived_qty = round(float(derived["quantity"]), 8)
            derived_avg = round(float(derived["avg_cost"]), 6)
            status = "MATCH" if abs(registered_qty - derived_qty) < 1e-8 else "MISMATCH"
        avg_price = round(float(asset.get("avg_price") or 0), 6)
        avg_diff = round(avg_price - derived_avg, 6)
        row = {
            "ticker": ticker,
            "registered_quantity": registered_qty,
            "derived_quantity": derived_qty,
            "quantity_diff": round(registered_qty - derived_qty, 8),
            "registered_avg_price": avg_price,
            "derived_avg_price": derived_avg,
            "avg_price_diff": avg_diff,
            "status": status,
        }
        rows.append(row)
        if status != "MATCH":
            issues.append({"type": "LEDGER_HOLDINGS_MISMATCH", "ticker": ticker, "message": f"{ticker}: holdings {registered_qty} vs ledger {derived_qty}.", "action": "Import missing operations or correct holdings."})
        elif abs(avg_diff) > 0.01:
            issues.append({"type": "COST_BASIS_MISMATCH", "ticker": ticker, "message": f"{ticker}: avg price {avg_price} vs ledger {derived_avg}.", "action": "Review cost basis."})
    return {"rows": rows, "issues": issues}
