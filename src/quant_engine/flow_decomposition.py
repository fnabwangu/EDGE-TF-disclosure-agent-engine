"""flow_decomposition.py
Computes simple decomposition placeholder values for unit tests.
"""

def compute_u_f_i_t(flows):
    """Return a simple normalized decomposition of flows (placeholder)."""
    total = sum(flows) or 1
    return [f / total for f in flows]
