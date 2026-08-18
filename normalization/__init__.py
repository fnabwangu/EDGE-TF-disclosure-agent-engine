"""Authoritative disclosure normalization package."""

from .normalizer import DisclosureNormalizer, IngestionMetadata, normalize_disclosures_pipeline, resolve_identifier

__all__ = ["DisclosureNormalizer", "IngestionMetadata", "normalize_disclosures_pipeline", "resolve_identifier"]
