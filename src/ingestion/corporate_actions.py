"""corporate_actions.py
Placeholder corporate actions adjustments (splits, mergers)
"""

def apply_split(holdings: dict, ticker: str, ratio: float) -> dict:
    """Apply split ratio to holdings for ticker."""
    if ticker in holdings:
        holdings[ticker] = holdings[ticker] * ratio
    return holdings
