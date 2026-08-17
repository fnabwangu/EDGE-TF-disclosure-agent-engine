"""EDGE-TF disclosure agent engine - core package.

This module is intentionally lightweight. It provides package metadata and
convenience exports for the inference public API without importing heavy
dependencies at import time.
"""

__version__ = "0.1.0"

# Public API exports (deferred imports to keep `import src` cheap).
# If the full inference stack is not installed yet, we set placeholders to
# allow safe inspection/import of the package without raising heavy ImportErrors.
try:
    from .inference import FactorPipeline, PortfolioOptimizer, VaREngine  # type: ignore
except Exception:
    FactorPipeline = None  # type: ignore
    PortfolioOptimizer = None  # type: ignore
    VaREngine = None  # type: ignore

__all__ = ["__version__", "FactorPipeline", "PortfolioOptimizer", "VaREngine"]
