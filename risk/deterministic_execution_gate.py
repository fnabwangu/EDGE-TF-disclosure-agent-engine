"""
Edge-TF Disclosure Agent Engine - Deterministic Execution Gate
Path: risk/deterministic_execution_gate.py

Implements programmatic compliance rules under the Investment Company Act of 1940,
IRC Subchapter M, SEC Rule 18f-4, Rule 22e-4, and Rule 35d-1.
Enforces hard liquidity & spread limits for trade execution.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class GateVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


@dataclass
class RuleEvaluationResult:
    """Container for individual regulatory rule evaluation results."""
    rule_id: str
    rule_name: str
    verdict: GateVerdict
    metric_value: float
    threshold_limit: float
    details: str


@dataclass
class GateAuditReport:
    """Comprehensive audit report from deterministic execution gate evaluation."""
    passed_all_gates: bool
    total_violations: int
    evaluations: List[RuleEvaluationResult]
    audit_timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DeterministicExecutionGate:
    """
    Executes programmatic pre-trade checks and structural regulatory gates.
    Enforces hard liquidity & spread limits for trade execution.
    
    Implements:
    - IRC Subchapter M diversification (5/50 rule)
    - SEC Rule 18f-4 VaR limits
    - SEC Rule 22e-4 Liquidity constraints
    - SEC Rule 35d-1 Names Rule compliance
    """

    def __init__(
        self,
        subchapter_m_single_cap: float = 0.25,
        subchapter_m_aggregate_cap: float = 0.50,
        subchapter_m_concentrated_threshold: float = 0.05,
        sec_18f4_relative_var_limit: float = 2.00,
        sec_22e4_illiquid_cap: float = 0.15,
        sec_35d1_names_rule_floor: float = 0.80,
        max_bid_ask_spread_bps: float = 50.0,
        min_daily_volume_usd: float = 1_000_000.0,
        min_zscore: float = 1.96,
        min_diffusion: float = 0.01,
        max_spread_pct: float = 0.02,
    ):
        """
        Args:
            subchapter_m_single_cap: Maximum single issuer weight (default 25%).
            subchapter_m_aggregate_cap: Maximum aggregate concentrated weight (default 50%).
            subchapter_m_concentrated_threshold: Threshold for concentration (default 5%).
            sec_18f4_relative_var_limit: Maximum relative VaR multiplier (default 2.0x).
            sec_22e4_illiquid_cap: Maximum illiquid holdings weight (default 15%).
            sec_35d1_names_rule_floor: Minimum mandate-aligned weight (default 80%).
            max_bid_ask_spread_bps: Maximum bid-ask spread in basis points.
            min_daily_volume_usd: Minimum required daily trading volume in USD.
        """
        self.sub_m_single_cap = subchapter_m_single_cap
        self.sub_m_agg_cap = subchapter_m_aggregate_cap
        self.sub_m_conc_thresh = subchapter_m_concentrated_threshold
        self.var_limit = sec_18f4_relative_var_limit
        self.illiquid_cap = sec_22e4_illiquid_cap
        self.names_rule_floor = sec_35d1_names_rule_floor
        self.max_spread_bps = max_bid_ask_spread_bps
        self.min_volume_usd = min_daily_volume_usd
        self.min_zscore = min_zscore
        self.min_diffusion = min_diffusion
        self.max_spread_pct = max_spread_pct

    def verify_order(
        self,
        z_score: float,
        diffusion_score: float,
        bid_price: float,
        ask_price: float,
    ) -> tuple[bool, str]:
        """Apply immutable signal and market-quality gates before routing an order."""
        if z_score < self.min_zscore:
            return False, f"REJECTED: Signal Z-score ({z_score:.2f}) below threshold ({self.min_zscore:.2f})"
        if diffusion_score < self.min_diffusion:
            return False, f"REJECTED: Network diffusion ({diffusion_score:.4f}) below minimum ({self.min_diffusion:.4f})"
        if bid_price <= 0 or ask_price <= 0 or ask_price < bid_price:
            return False, "REJECTED: Invalid bid/ask market data"
        spread = (ask_price - bid_price) / ask_price
        if spread > self.max_spread_pct:
            return False, f"REJECTED: Bid-ask spread ({spread:.2%}) exceeds liquidity limit ({self.max_spread_pct:.2%})"
        return True, "ACCEPTED"

    def evaluate_subchapter_m(self, weights: Dict[str, float]) -> List[RuleEvaluationResult]:
        """
        Evaluates IRC Subchapter M (5/50 diversification test):
        1. No single issuer > 25%
        2. Sum of all issuers > 5% must be <= 50%
        """
        results = []
        if not weights:
            results.append(
                RuleEvaluationResult(
                    rule_id="IRC-SUB-M-EMPTY",
                    rule_name="IRC Subchapter M (Empty Portfolio)",
                    verdict=GateVerdict.FAIL,
                    metric_value=0.0,
                    threshold_limit=self.sub_m_single_cap,
                    details="Portfolio weights dictionary is empty."
                )
            )
            return results

        max_weight = max(weights.values())
        single_issuer_passed = max_weight <= self.sub_m_single_cap
        results.append(
            RuleEvaluationResult(
                rule_id="IRC-SUB-M-SINGLE",
                rule_name="IRC Subchapter M (Single Issuer 25% Cap)",
                verdict=GateVerdict.PASS if single_issuer_passed else GateVerdict.FAIL,
                metric_value=max_weight,
                threshold_limit=self.sub_m_single_cap,
                details=f"Max single issuer weight: {max_weight:.2%}"
            )
        )

        concentrated_sum = sum(w for w in weights.values() if w > self.sub_m_conc_thresh)
        agg_passed = concentrated_sum <= self.sub_m_agg_cap
        results.append(
            RuleEvaluationResult(
                rule_id="IRC-SUB-M-AGGREGATE",
                rule_name="IRC Subchapter M (Concentrated Aggregate 50% Cap)",
                verdict=GateVerdict.PASS if agg_passed else GateVerdict.FAIL,
                metric_value=concentrated_sum,
                threshold_limit=self.sub_m_agg_cap,
                details=f"Aggregate weight of positions > 5%: {concentrated_sum:.2%}"
            )
        )

        return results

    def evaluate_rule_18f_4(self, relative_var: float) -> RuleEvaluationResult:
        """Evaluates SEC Rule 18f-4 Relative VaR limit (<= 200% of benchmark)."""
        passed = relative_var <= self.var_limit
        return RuleEvaluationResult(
            rule_id="SEC-18F4-VAR",
            rule_name="SEC Rule 18f-4 (Relative VaR <= 2.0x)",
            verdict=GateVerdict.PASS if passed else GateVerdict.FAIL,
            metric_value=relative_var,
            threshold_limit=self.var_limit,
            details=f"Portfolio relative VaR: {relative_var:.2f}x"
        )

    def evaluate_rule_22e_4(self, illiquid_weight: float) -> RuleEvaluationResult:
        """Evaluates SEC Rule 22e-4 Liquidity Rule (Illiquid assets <= 15%)."""
        passed = illiquid_weight <= self.illiquid_cap
        return RuleEvaluationResult(
            rule_id="SEC-22E4-LIQ",
            rule_name="SEC Rule 22e-4 (Illiquid Asset Cap <= 15%)",
            verdict=GateVerdict.PASS if passed else GateVerdict.FAIL,
            metric_value=illiquid_weight,
            threshold_limit=self.illiquid_cap,
            details=f"Illiquid holdings percentage: {illiquid_weight:.2%}"
        )

    def evaluate_rule_35d_1(self, mandate_aligned_weight: float) -> RuleEvaluationResult:
        """Evaluates SEC Rule 35d-1 Names Rule (>= 80% investment in mandate)."""
        passed = mandate_aligned_weight >= self.names_rule_floor
        return RuleEvaluationResult(
            rule_id="SEC-35D1-NAMES",
            rule_name="SEC Rule 35d-1 (Mandate Policy Floor >= 80%)",
            verdict=GateVerdict.PASS if passed else GateVerdict.FAIL,
            metric_value=mandate_aligned_weight,
            threshold_limit=self.names_rule_floor,
            details=f"Mandate-aligned investment percentage: {mandate_aligned_weight:.2%}"
        )

    def evaluate_liquidity_spread(
        self,
        bid_ask_spread_bps: float,
        daily_volume_usd: float,
    ) -> List[RuleEvaluationResult]:
        """
        Evaluates hard liquidity & spread limits for execution feasibility.
        """
        results = []

        spread_passed = bid_ask_spread_bps <= self.max_spread_bps
        results.append(
            RuleEvaluationResult(
                rule_id="EXEC-SPREAD",
                rule_name="Execution Bid-Ask Spread Limit",
                verdict=GateVerdict.PASS if spread_passed else GateVerdict.FAIL,
                metric_value=bid_ask_spread_bps,
                threshold_limit=self.max_spread_bps,
                details=f"Bid-ask spread: {bid_ask_spread_bps:.1f} bps"
            )
        )

        volume_passed = daily_volume_usd >= self.min_volume_usd
        results.append(
            RuleEvaluationResult(
                rule_id="EXEC-VOLUME",
                rule_name="Execution Minimum Daily Volume",
                verdict=GateVerdict.PASS if volume_passed else GateVerdict.FAIL,
                metric_value=daily_volume_usd,
                threshold_limit=self.min_volume_usd,
                details=f"Daily trading volume: ${daily_volume_usd:,.0f}"
            )
        )

        return results

    def execute_all_gates(
        self,
        target_weights: Dict[str, float],
        relative_var: float,
        illiquid_weight: float,
        mandate_aligned_weight: float,
        bid_ask_spread_bps: Optional[float] = None,
        daily_volume_usd: Optional[float] = None,
    ) -> GateAuditReport:
        """
        Runs comprehensive deterministic compliance evaluation across all statutory gates
        and execution constraints.
        
        Returns:
            GateAuditReport with verdict on all regulatory checks and liquidity constraints.
        """
        evaluations: List[RuleEvaluationResult] = []

        evaluations.extend(self.evaluate_subchapter_m(target_weights))
        evaluations.append(self.evaluate_rule_18f_4(relative_var))
        evaluations.append(self.evaluate_rule_22e_4(illiquid_weight))
        evaluations.append(self.evaluate_rule_35d_1(mandate_aligned_weight))

        if bid_ask_spread_bps is not None and daily_volume_usd is not None:
            evaluations.extend(
                self.evaluate_liquidity_spread(bid_ask_spread_bps, daily_volume_usd)
            )

        violations = [e for e in evaluations if e.verdict == GateVerdict.FAIL]
        passed_all = len(violations) == 0

        report = GateAuditReport(
            passed_all_gates=passed_all,
            total_violations=len(violations),
            evaluations=evaluations
        )

        if not passed_all:
            logger.error(f"Deterministic Execution Gates Failed: {len(violations)} rule breaches detected.")
        else:
            logger.info("All deterministic execution gates successfully passed.")

        return report


__all__ = [
    "GateVerdict",
    "RuleEvaluationResult",
    "GateAuditReport",
    "DeterministicExecutionGate",
    "evaluate_deterministic_gates",
]


def evaluate_deterministic_gates(
    data_quality_ok: bool,
    falsification_passed: bool,
    governor_approved: bool,
) -> Dict[str, Any]:
    """
    Wrapper function for deterministic gate evaluation.
    Returns execution permission decision based on all gate checks.
    
    Args:
        data_quality_ok: Data freshness and quality validation result.
        falsification_passed: Adversarial disconfirmation gate result.
        governor_approved: Risk governor audit result.
    
    Returns:
        Dict with execution_permitted and system_state fields.
    """
    all_gates_pass = data_quality_ok and falsification_passed and governor_approved
    
    return {
        "execution_permitted": all_gates_pass,
        "system_state": "TRADE_DISPATCH_PERMISSIBLE" if all_gates_pass else "NO_TRADE_PERMISSIBLE",
        "data_quality_ok": data_quality_ok,
        "falsification_passed": falsification_passed,
        "governor_approved": governor_approved,
    }
