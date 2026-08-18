"""Legacy compatibility shim; use normalization.normalizer."""

from normalization.normalizer import *

__all__ = ["DisclosureNormalizer", "IngestionMetadata", "normalize_disclosures_pipeline", "resolve_identifier"]
