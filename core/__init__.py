"""
EDGE-TF Core Module

Layer 1: Data Contracts & Schema Definitions
Contains canonical schemas for disclosure payloads, manager actions, and data models.
"""

from .schemas import (
    DataSourceType,
    MarketDataSnapshot,
    IngestionBatchReport,
    DisclosurePayload,
    ManagerAction,
)
from .disclosure_crawler import (
    DisclosureCrawler,
    ExtractedDisclosure,
    FilingType,
)

__all__ = [
    "DataSourceType",
    "MarketDataSnapshot",
    "IngestionBatchReport",
    "DisclosurePayload",
    "ManagerAction",
    "DisclosureCrawler",
    "ExtractedDisclosure",
    "FilingType",
]
