"""risk_governor.py
Hard sizing constraints placeholder.
"""

def check_single_stock_limit(position_pct: float, max_pct: float = 0.15) -> bool:
    return position_pct <= max_pct
