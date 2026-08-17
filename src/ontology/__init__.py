## Statutory & Domain Ontology Interface (`src/ontology/__init__.py`)

The `src/ontology/__init__.py` module formalizes the domain semantic ontology, classification hierarchies, and statutory rule definitions underpinning the **EDGE-TF-disclosure-agent-engine**. It maps statutory obligations (1940 Act, IRC Subchapter M, SEC disclosure mandates) and portfolio taxonomies into strongly-typed Python enumerations and data models.

---

### Core Ontology Entities

* **`RegulatoryFramework`**: Formal statutory authorities (`SEC_1940_ACT`, `IRC_SUBCHAPTER_M`, `SEC_RULE_6C11`, `SEC_RULE_18F4`, `SEC_RULE_22E4`, `SEC_RULE_35D1`).
* **`AssetClassification`**: Multi-tiered taxonomy categorizing spot equities, options overlays, cash equivalents, and illiquid instruments.
* **`ThematicMandateCluster`**: Semantic buckets enforcing portfolio concentration limits and 80% Names Rule alignment.
* **`FiduciaryRole`**: Designated signatory roles required for dual-authorization gates and cryptographic WORM audit trails (`CCO`, `LEAD_PM`, `CFO`, `RISK_OFFICER`).# ontology package

# src/ontology/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Regulatory, Tax, & Domain Semantic Ontology.

Provides standardized enumerations, taxonomy hierarchies, and statutory mapping
models for portfolio classification, compliance gates, and audit trails.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class RegulatoryFramework(str, Enum):
    """Statutory authorities governing the ETF lifecycle."""
    SEC_1940_ACT = "INVESTMENT_COMPANY_ACT_1940"
    IRC_SUBCHAPTER_M = "IRC_SUBCHAPTER_M_REGULATED_INVESTMENT_COMPANY"
    SEC_RULE_6C11 = "SEC_RULE_6C_11_ETF_TRANSPARENCY"
    SEC_RULE_18F4 = "SEC_RULE_18F_4_DERIVATIVES_RISK_MANAGEMENT"
    SEC_RULE_22E4 = "SEC_RULE_22E_4_LIQUIDITY_RISK_MANAGEMENT"
    SEC_RULE_35D1 = "SEC_RULE_35D_1_NAMES_RULE"


class AssetClassification(str, Enum):
    """Asset tier mapping for liquidity, margin, and collateral allocation."""
    EQUITY_COMMON_STOCK = "EQUITY_COMMON_STOCK"
    EQUITY_ADR = "EQUITY_ADR"
    DERIVATIVE_COVERED_CALL = "DERIVATIVE_COVERED_CALL"
    DERIVATIVE_SHORT_LEAP_PUT = "DERIVATIVE_SHORT_LEAP_PUT"
    CASH_SETTLED_USD = "CASH_SETTLED_USD"
    CASH_EQUIVALENT_TREASURY_BILL = "CASH_EQUIVALENT_TREASURY_BILL"
    ILLIQUID_RESTRICTED_SECURITY = "ILLIQUID_RESTRICTED_SECURITY"


class LiquidityBucket(str, Enum):
    """SEC Rule 22e-4 Liquidity Classification Tiers."""
    HIGHLY_LIQUID = "HIGHLY_LIQUID"              # Convertible <= 3 business days
    MODERATELY_LIQUID = "MODERATELY_LIQUID"      # Convertible > 3 and <= 7 calendar days
    LESS_LIQUID = "LESS_LIQUID"                  # Convertible > 7 calendar days to sold, settled > 7
    ILLIQUID = "ILLIQUID"                        # Cannot be sold within 7 calendar days


class FiduciaryRole(str, Enum):
    """Authorized regulatory and governance actors."""
    CHIEF_COMPLIANCE_OFFICER = "CHIEF_COMPLIANCE_OFFICER"
    LEAD_PORTFOLIO_MANAGER = "LEAD_PORTFOLIO_MANAGER"
    CHIEF_FINANCIAL_OFFICER = "CHIEF_FINANCIAL_OFFICER"
    SYSTEM_RISK_GOVERNOR = "SYSTEM_RISK_GOVERNOR"
    COMPLIANCE_WATCHDOG = "COMPLIANCE_WATCHDOG"
    EXTERNAL_AUDITOR = "EXTERNAL_AUDITOR"


class ThematicMandateCluster(str, Enum):
    """Thematic taxonomy for Rule 35d-1 Names Rule asset verification."""
    AUTONOMOUS_SYSTEMS_AI = "AUTONOMOUS_SYSTEMS_AI"
    CLEAN_ENERGY_GRID = "CLEAN_ENERGY_GRID"
    NEXT_GEN_COMPUTE = "NEXT_GEN_COMPUTE"
    BIOPHARMA_INNOVATION = "BIOPHARMA_INNOVATION"
    DIGITAL_INFRASTRUCTURE = "DIGITAL_INFRASTRUCTURE"
    UNCLASSIFIED_NON_MANDATE = "UNCLASSIFIED_NON_MANDATE"


@dataclass
class ConstituentMetadata:
    """Ontological metadata descriptor for every asset in the portfolio universe."""
    ticker: str
    cusip: str
    company_name: str
    asset_class: AssetClassification
    thematic_cluster: ThematicMandateCluster
    liquidity_bucket: LiquidityBucket
    is_mandate_eligible: bool
    is_subchapter_m_qualifying: bool = True
    last_verified_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "cusip": self.cusip,
            "company_name": self.company_name,
            "asset_class": self.asset_class.value,
            "thematic_cluster": self.thematic_cluster.value,
            "liquidity_bucket": self.liquidity_bucket.value,
            "is_mandate_eligible": self.is_mandate_eligible,
            "is_subchapter_m_qualifying": self.is_subchapter_m_qualifying,
            "last_verified_utc": self.last_verified_utc,
        }


class StatutoryOntologyRegistry:
    """
    In-memory knowledge registry mapping tickers to statutory classifications,
    enabling deterministic lookups for compliance verification.
    """

    def __init__(self):
        self._registry: Dict[str, ConstituentMetadata] = {}

    def register_constituent(self, meta: ConstituentMetadata):
        """Adds or updates constituent metadata in the ontology registry."""
        self._registry[meta.ticker.upper()] = meta
        logging.debug(f"Registered ontology definition for {meta.ticker} ({meta.asset_class.value}).")

    def get_metadata(self, ticker: str) -> Optional[ConstituentMetadata]:
        return self._registry.get(ticker.upper())

    def is_mandate_aligned(self, ticker: str) -> bool:
        meta = self.get_metadata(ticker)
        return meta.is_mandate_eligible if meta else False

    def is_illiquid(self, ticker: str) -> bool:
        meta = self.get_metadata(ticker)
        if not meta:
            return False
        return meta.liquidity_bucket == LiquidityBucket.ILLIQUID

    def get_universe_summary(self) -> Dict[str, Any]:
        """Provides statistical breakdown across thematic clusters and liquidity buckets."""
        total = len(self._registry)
        if total == 0:
            return {"total_registered": 0}

        cluster_counts: Dict[str, int] = {}
        liquidity_counts: Dict[str, int] = {}

        for meta in self._registry.values():
            c = meta.thematic_cluster.value
            l = meta.liquidity_bucket.value
            cluster_counts[c] = cluster_counts.get(c, 0) + 1
            liquidity_counts[l] = liquidity_counts.get(l, 0) + 1

        return {
            "total_registered": total,
            "by_cluster": cluster_counts,
            "by_liquidity": liquidity_counts,
        }


__all__ = [
    "RegulatoryFramework",
    "AssetClassification",
    "LiquidityBucket",
    "FiduciaryRole",
    "ThematicMandateCluster",
    "ConstituentMetadata",
    "StatutoryOntologyRegistry",
]
