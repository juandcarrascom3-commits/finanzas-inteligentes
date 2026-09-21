"""Small market data provider abstraction for delayed daily Finance data."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class MarketQuote:
    symbol: str
    price: float
    currency: str
    as_of: str
    provider: str
    retrieved_at: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MarketPrice:
    symbol: str
    price: float
    currency: str
    price_date: str
    provider: str
    retrieved_at: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MarketDataProvider(Protocol):
    name: str

    def get_quote(self, symbol: str) -> MarketQuote:
        ...

    def get_price_history(self, symbol: str, start: str, end: str) -> List[MarketPrice]:
        ...

    def get_fx_history(self, pair: str, start: str, end: str) -> List[MarketPrice]:
        ...

    def get_benchmark_history(self, symbol: str, start: str, end: str) -> List[MarketPrice]:
        ...

    def get_etf_holdings(self, symbol: str) -> Dict[str, Any]:
        ...


class ProviderUnavailableError(RuntimeError):
    pass


def _today() -> str:
    return date.today().isoformat()


def _normalize_currency(value: Optional[str]) -> str:
    return (value or "USD").upper()


def _row_price(row: Any) -> float:
    for key in ["Adj Close", "Close", "close", "regularMarketPrice"]:
        try:
            value = row[key]
            if value and float(value) > 0:
                return float(value)
        except Exception:
            continue
    return 0.0


class YFinanceProvider:
    name = "YFINANCE"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def _yf(self):
        try:
            import yfinance as yf  # type: ignore
        except Exception as exc:
            raise ProviderUnavailableError("yfinance is not installed. Run pip install -r backend/requirements.txt.") from exc
        return yf

    def get_quote(self, symbol: str) -> MarketQuote:
        yf = self._yf()
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info or {}
        price = float(info.get("last_price") or info.get("regular_market_price") or 0)
        currency = _normalize_currency(info.get("currency"))
        if price <= 0:
            history = ticker.history(period="5d", interval="1d", auto_adjust=True, timeout=self.timeout)
            if history is None or history.empty:
                raise ProviderUnavailableError(f"No quote available for {symbol}.")
            last = history.dropna().iloc[-1]
            price = _row_price(last)
            currency = _normalize_currency(getattr(ticker, "fast_info", {}).get("currency") if getattr(ticker, "fast_info", None) else None)
        if price <= 0:
            raise ProviderUnavailableError(f"No positive quote available for {symbol}.")
        retrieved_at = datetime.now().isoformat()
        return MarketQuote(symbol=symbol.upper(), price=round(price, 6), currency=currency, as_of=_today(), provider=self.name, retrieved_at=retrieved_at, metadata={"adjusted": True})

    def get_price_history(self, symbol: str, start: str, end: str) -> List[MarketPrice]:
        yf = self._yf()
        end_plus = (datetime.fromisoformat(end[:10]).date() + timedelta(days=1)).isoformat()
        frame = yf.download(symbol, start=start[:10], end=end_plus, progress=False, auto_adjust=True, timeout=self.timeout)
        if frame is None or frame.empty:
            return []
        retrieved_at = datetime.now().isoformat()
        rows: List[MarketPrice] = []
        for index, row in frame.iterrows():
            price = _row_price(row)
            if price <= 0:
                continue
            day = getattr(index, "date", lambda: index)().isoformat()
            rows.append(MarketPrice(symbol=symbol.upper(), price=round(price, 6), currency="USD", price_date=day, provider=self.name, retrieved_at=retrieved_at, metadata={"adjusted": True, "policy": "auto_adjust=True"}))
        return rows

    def get_fx_history(self, pair: str, start: str, end: str) -> List[MarketPrice]:
        symbol = pair.upper().replace("/", "") + "=X"
        if pair.upper().endswith("=X"):
            symbol = pair.upper()
        return self.get_price_history(symbol, start, end)

    def get_benchmark_history(self, symbol: str, start: str, end: str) -> List[MarketPrice]:
        return self.get_price_history(symbol, start, end)

    def get_etf_holdings(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol.upper(), "status": "UNAVAILABLE", "coverage": "PARTIAL_HOLDINGS", "holdings": [], "provider": self.name}


def get_market_provider(name: str = "YFINANCE") -> MarketDataProvider:
    provider = (name or "YFINANCE").upper()
    if provider == "YFINANCE":
        return YFinanceProvider()
    raise ProviderUnavailableError(f"Unsupported market provider: {name}")
