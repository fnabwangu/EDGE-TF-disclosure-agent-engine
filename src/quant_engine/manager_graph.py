"""manager_graph.py
Deduplicated manager clusters and a simple HHI calculation.
"""

def compute_hhi(shares):
    """Compute concentration Herfindahl-Hirschman Index (percent shares list)."""
    return sum((s * 100) ** 2 for s in shares)
