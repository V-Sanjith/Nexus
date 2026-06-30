from typing import Dict

class CurrencyService:
    """Manages currency translations and isolates exchange rate logic from the Decision Engine."""

    # Fixed mock exchange rates for development (1 USD = 98 INR)
    EXCHANGE_RATES: Dict[str, float] = {
        "usd": 1.0,
        "inr": 1.0,
        "eur": 1.0,
        "gbp": 1.0
    }

    @classmethod
    def convert_to_usd(cls, amount: float, from_currency: str) -> float:
        """No-op conversion for native INR operation."""
        return float(amount)

    @classmethod
    def convert_from_usd(cls, amount: float, to_currency: str) -> float:
        """No-op conversion for native INR operation."""
        return float(amount)
