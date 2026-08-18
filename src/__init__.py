"""Legacy compatibility namespace for the EDGE-TF engine.

Authoritative implementations live in the root packages: ``core``,
``normalization``, ``ingestion``, ``analytics``, ``agents``, ``risk``,
``execution``, and ``audit``. New product code must not import from ``src``.
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
