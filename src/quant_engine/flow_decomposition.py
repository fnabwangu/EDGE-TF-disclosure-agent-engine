"""Legacy compatibility shim; use analytics.anomaly_detector."""

from analytics.anomaly_detector import AnomalyDetector


def compute_u_f_i_t(flows):
    total = sum(flows) or 1
    return [flow / total for flow in flows]

__all__ = ["AnomalyDetector", "compute_u_f_i_t"]
