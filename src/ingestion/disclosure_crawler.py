"""Legacy compatibility shim; use core.disclosure_crawler."""

from core.disclosure_crawler import DisclosureCrawler, ExtractedDisclosure, FilingType

__all__ = ["DisclosureCrawler", "ExtractedDisclosure", "FilingType"]
