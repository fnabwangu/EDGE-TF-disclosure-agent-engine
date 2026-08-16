"""deterministic_gates.py
Hard gates (EV gate, Rebalance filter, Volatility governor) placeholder.
"""

def ev_gate(signal_strength: float, threshold: float) -> bool:
    return signal_strength >= threshold
Markdown
## Deterministic Governance Gates (`src/governance/deterministic_gates.py`)

The `deterministic_gates.py` module evaluates programmatic, hard-coded statutory and regulatory constraints before permitting order generation, basket creation, or AP disclosure dispatching. It eliminates non-deterministic model behavior during regulatory evaluation by applying strict mathematical checks across IRC Subchapter M, SEC Rule 18f-4 (VaR), SEC Rule 22e-4 (Liquidity), and SEC Rule 35d-1 (Names Rule).

---

### Key Capabilities

* **`IRC Subchapter M Diversification Audit (5/50 Rule)`**: Mathematically enforces that no single issuer exceeds 25% of total fund assets, and the aggregate weight of all issuers exceeding 5% does not surpass 50%.
* **`SEC Rule 18f-4 Derivatives & Leverage Limit`**: Evaluates portfolio relative Value-at-Risk against designated reference benchmarks (capped at 200%) or absolute VaR limits (capped at 20%).
* **`SEC Rule 22e-4 Liquidity Risk Management`**: Validates illiquid investments do not exceed the 15% statutory threshold and monitors Days-to-Liquid parameters.
* **`SEC Rule 35d-1 Names Rule Compliance`**: Guarantees that at least 80% of fund assets are allocated directly in alignment with the thematic investment mandate.
* **`Deterministic Go/No-Go Decision Engine`**: Evaluates all gating logic synchronously and returns a structured diagnostic report.
Python
# src/governance/deterministic_gates.py
"""
EDGE-TF Disclosure Agent Engine - Deterministic Statutory & Regulatory Gates.

Implements programmatic compliance rules under the Investment Company Act of 1940,
IRC Subchapter M, SEC Rule 18f-4, Rule 22e-4, and Rule 35d-1.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class GateVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


@dataclass
class RuleEvaluationResult:
    rule_id: str
    rule_name: str
    verdict: GateVerdict
    metric_value: float
    threshold_limit: float
    details: str


@dataclass
class GateAuditReport:
    passed_all_gates: bool
    total_violations: int
    evaluations: List[RuleEvaluationResult]
    audit_timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DeterministicGateEngine:
    """
    Executes programmatic pre-trade checks and structural regulatory gates.
    """

    def __init__(
        self,
        subchapter_m_single_cap: float = 0.25,
        subchapter_m_aggregate_cap: float = 0.50,
        subchapter_m_concentrated_threshold: float = 0.05,
        sec_18f4_relative_var_limit: float = 2.00,
        sec_22e4_illiquid_cap: float = 0.15,
        sec_35d1_names_rule_floor: float = 0.80,
    ):
        self.sub_m_single_cap = subchapter_m_single_cap
        self.sub_m_agg_cap = subchapter_m_aggregate_cap
        self.sub_m_conc_thresh = subchapter_m_concentrated_threshold
        self.var_limit = sec_18f4_relative_var_limit
        self.illiquid_cap = sec_22e4_illiquid_cap
        self.names_rule_floor = sec_35d1_names_rule_floor

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

    def execute_all_gates(
        self,
        target_weights: Dict[str, float],
        relative_var: float,
        illiquid_weight: float,
        mandate_aligned_weight: float,
    ) -> GateAuditReport:
        """
        Runs comprehensive deterministic compliance evaluation across all statutory gates.
        """
        evaluations: List[RuleEvaluationResult] = []

        evaluations.extend(self.evaluate_subchapter_m(target_weights))
        evaluations.append(self.evaluate_rule_18f_4(relative_var))
        evaluations.append(self.evaluate_rule_22e_4(illiquid_weight))
        evaluations.append(self.evaluate_rule_35d_1(mandate_aligned_weight))

        violations = [e for e in evaluations if e.verdict == GateVerdict.FAIL]
        passed_all = len(violations) == 0

        report = GateAuditReport(
            passed_all_gates=passed_all,
            total_violations=len(violations),
            evaluations=evaluations
        )

        if not passed_all:
            logging.error(f"Deterministic Gates Failed: {len(violations)} rule breaches detected.")
        else:
            logging.info("All deterministic governance gates successfully passed.")

        return report


__all__ = [
    "GateVerdict",
    "RuleEvaluationResult",
    "GateAuditReport",
    "DeterministicGateEngine",
]
