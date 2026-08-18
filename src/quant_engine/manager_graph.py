"""Legacy compatibility shim; use analytics.manager_independence."""

from analytics.manager_independence import *

__all__ = ["ManagerMetadata", "SecurityManagerMetrics", "ManagerGraphEngine", "compute_manager_graph_pipeline"]
