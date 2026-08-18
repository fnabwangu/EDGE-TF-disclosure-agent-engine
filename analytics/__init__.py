"""
EDGE-TF Analytics Module

Centralized quantitative analysis engines for institutional graph modeling,
anomaly detection, convex portfolio optimization, and derivatives pricing.
"""

from .institutional_graph_engine import InstitutionalGraphEngine
from .anomaly_detector import AnomalyDetector
from .convex_position_optimizer import ConvexPositionOptimizer
from .institutional_adoption_velocity import IAVInputs, IAVResult, InstitutionalAdoptionVelocity
from .inav_calculator import INAVCalculator, INAVSnapshot, OptionPositionState
from .options_modeler import (
    BlackScholesEngine,
    OptionContract,
    OptionGreeks,
    select_duration_matched_expiry,
    structure_leap_expression,
    generate_scenario_surface,
)
from .pipeline import process_disclosure_pipeline
from .quant_matrix import QuantMatrixUtils, OptimizationConstraints, OptimizationObjective, QuantEngineDiagnostics, RiskModelType
from .manager_independence import ManagerGraphEngine, ManagerMetadata, SecurityManagerMetrics, compute_manager_graph_pipeline

__all__ = [
    "InstitutionalGraphEngine",
    "AnomalyDetector",
    "ConvexPositionOptimizer",
    "IAVInputs",
    "IAVResult",
    "InstitutionalAdoptionVelocity",
    "INAVCalculator",
    "INAVSnapshot",
    "OptionPositionState",
    "BlackScholesEngine",
    "OptionContract",
    "OptionGreeks",
    "select_duration_matched_expiry",
    "structure_leap_expression",
    "generate_scenario_surface",
    "process_disclosure_pipeline",
    "QuantMatrixUtils",
    "OptimizationConstraints",
    "OptimizationObjective",
    "QuantEngineDiagnostics",
    "RiskModelType",
    "ManagerGraphEngine",
    "ManagerMetadata",
    "SecurityManagerMetrics",
    "compute_manager_graph_pipeline",
]
