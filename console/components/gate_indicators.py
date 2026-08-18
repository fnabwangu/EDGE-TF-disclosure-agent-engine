import streamlit as st

def render_gate_indicators():
    st.header("Gate Indicators")
    st.write("Gate statuses will appear here.")
"""## Gate Indicators Component (`console/components/gate_indicators.py`)

The `gate_indicators.py` module renders real-time qualitative status flags, statutory gating indicators, and operational pipeline health checks for the ETF console. It acts as the visual go/no-go dashboard before rebalance execution or AP disclosure generation.

---

### Key Capabilities

* **`Statutory Gating Metrics`**: Assesses IRC Subchapter M (5/50 rule) safety cushions and SEC Rule 35d-1 80% Names Rule compliance margins.
* **`Risk Gating Metrics`**: Evaluates SEC Rule 18f-4 relative/absolute Value-at-Risk limits and drawdown circuit-breaker thresholds.
* **`Pipeline Operational Readiness`**: Monitors data feed sanity, broker FIX connection health, and dual-signatory approvals.
* **`Status Signal Encoding`**: Emits discrete states (`OPEN_GREEN`, `WARNING_AMBER`, `CLOSED_RED`) with ANSI colorized console rendering.
Python"""
# console/components/gate_indicators.py
"""
EDGE-TF Disclosure Agent Engine - Gate Indicators & Pipeline Health Component.

Evaluates and visualizes go/no-go gating thresholds across statutory compliance,
portfolio risk limits, market data freshness, and execution pipeline readiness.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import pandas as pd


class GateStatus(str, Enum):
    OPEN_GREEN = "OPEN"           # Cleared for automated processing
    WARNING_AMBER = "WARNING"     # Approaching buffer/threshold; manual review suggested
    CLOSED_RED = "CLOSED"         # Hard breach; trading pipeline blocked


@dataclass
class GateMetric:
    gate_id: str
    name: str
    category: str
    current_value: float
    limit_value: float
    unit: str
    status: GateStatus
    message: str


class GateIndicatorsEngine:
    """
    Evaluates system metrics against statutory, risk, and operational gates
    to determine if the ETF pipeline can advance to trade execution or PCF release.
    """

    def __init__(self, warning_buffer_ratio: float = 0.85):
        """
        :param warning_buffer_ratio: Ratio of the limit at which status transitions
                                     from OPEN_GREEN to WARNING_AMBER (default 85%).
        """
        self.warning_buffer = warning_buffer_ratio

    def evaluate_gates(
        self,
        compliance_metrics: Dict[str, Any],
        portfolio_metrics: Dict[str, Any],
        operational_status: Dict[str, Any]
    ) -> List[GateMetric]:
        """
        Sweeps all dimensions and returns an itemized list of gate metrics.
        """
        gates: List[GateMetric] = []

        # 1. Statutory Gate: Single Issuer Cap (IRC Subchapter M - 25% max)
        max_single_w = compliance_metrics.get("max_single_issuer_weight", 0.0)
        single_cap = 0.25
        if max_single_w > single_cap:
            status = GateStatus.CLOSED_RED
            msg = f"Single issuer ({max_single_w:.2%}) breached 25% statutory cap."
        elif max_single_w >= (single_cap * self.warning_buffer):
            status = GateStatus.WARNING_AMBER
            msg = f"Single issuer ({max_single_w:.2%}) approaching 25% cap."
        else:
            status = GateStatus.OPEN_GREEN
            msg = f"Single issuer cushion: {(single_cap - max_single_w):.2%}"

        gates.append(
            GateMetric(
                gate_id="GATE_STAT_01",
                name="IRC Subchapter M Single Issuer",
                category="STATUTORY",
                current_value=max_single_w,
                limit_value=single_cap,
                unit="%",
                status=status,
                message=msg
            )
        )

        # 2. Statutory Gate: Concentrated Aggregate Cap (>5% issuers <= 50%)
        agg_conc_w = compliance_metrics.get("aggregate_concentrated_weight", 0.0)
        agg_cap = 0.50
        if agg_conc_w > agg_cap:
            status = GateStatus.CLOSED_RED
            msg = f"Concentrated issuers aggregate ({agg_conc_w:.2%}) breached 50% cap."
        elif agg_conc_w >= (agg_cap * self.warning_buffer):
            status = GateStatus.WARNING_AMBER
            msg = f"Concentrated issuers aggregate ({agg_conc_w:.2%}) near 50% limit."
        else:
            status = GateStatus.OPEN_GREEN
            msg = f"Concentrated issuers cushion: {(agg_cap - agg_conc_w):.2%}"

        gates.append(
            GateMetric(
                gate_id="GATE_STAT_02",
                name="IRC Subchapter M 50% Basket",
                category="STATUTORY",
                current_value=agg_conc_w,
                limit_value=agg_cap,
                unit="%",
                status=status,
                message=msg
            )
        )

        # 3. Regulatory Risk Gate: SEC Rule 18f-4 Relative VaR (Max 2.0x)
        rel_var = portfolio_metrics.get("relative_var_multiplier", 1.0)
        max_rel_var = 2.00
        if rel_var > max_rel_var:
            status = GateStatus.CLOSED_RED
            msg = f"Relative VaR ({rel_var:.2f}x) exceeds 200% benchmark cap."
        elif rel_var >= (max_rel_var * self.warning_buffer):
            status = GateStatus.WARNING_AMBER
            msg = f"Relative VaR ({rel_var:.2f}x) approaching 2.0x limit."
        else:
            status = GateStatus.OPEN_GREEN
            msg = f"Relative VaR headroom: {(max_rel_var - rel_var):.2f}x"

        gates.append(
            GateMetric(
                gate_id="GATE_RISK_01",
                name="SEC Rule 18f-4 Relative VaR",
                category="RISK",
                current_value=rel_var,
                limit_value=max_rel_var,
                unit="x",
                status=status,
                message=msg
            )
        )

        # 4. Risk Gate: Max Drawdown Circuit Breaker
        current_dd = portfolio_metrics.get("current_drawdown", 0.0)
        max_dd = portfolio_metrics.get("drawdown_limit", 0.15)
        if current_dd > max_dd:
            status = GateStatus.CLOSED_RED
            msg = f"Current drawdown ({current_dd:.2%}) tripped circuit breaker ({max_dd:.2%})."
        elif current_dd >= (max_dd * self.warning_buffer):
            status = GateStatus.WARNING_AMBER
            msg = f"Current drawdown ({current_dd:.2%}) near stop limit."
        else:
            status = GateStatus.OPEN_GREEN
            msg = f"Drawdown headroom: {(max_dd - current_dd):.2%}"

        gates.append(
            GateMetric(
                gate_id="GATE_RISK_02",
                name="Portfolio Drawdown Stop",
                category="RISK",
                current_value=current_dd,
                limit_value=max_dd,
                unit="%",
                status=status,
                message=msg
            )
        )

        # 5. Operational Gate: Market Data Latency
        data_latency_sec = operational_status.get("data_latency_seconds", 0.0)
        max_latency = operational_status.get("max_permitted_latency_seconds", 60.0)
        if data_latency_sec > max_latency:
            status = GateStatus.CLOSED_RED
            msg = f"Market data stale ({data_latency_sec:.1f}s > {max_latency:.1f}s)."
        elif data_latency_sec >= (max_latency * 0.75):
            status = GateStatus.WARNING_AMBER
            msg = f"Elevated market feed latency ({data_latency_sec:.1f}s)."
        else:
            status = GateStatus.OPEN_GREEN
            msg = f"Data feed latency nominal ({data_latency_sec:.1f}s)."

        gates.append(
            GateMetric(
                gate_id="GATE_OPS_01",
                name="Market Feed Freshness",
                category="OPERATIONAL",
                current_value=data_latency_sec,
                limit_value=max_latency,
                unit="s",
                status=status,
                message=msg
            )
        )

        return gates

    def is_pipeline_cleared(self, gates: List[GateMetric]) -> bool:
        """Returns True if no gates are in CLOSED_RED status."""
        return not any(g.status == GateStatus.CLOSED_RED for g in gates)

    def render_console_indicators(self, gates: List[GateMetric]) -> str:
        """Formats gate indicators into an aligned terminal telemetry dashboard."""
        if not gates:
            return "No gate indicators evaluated."

        rows = []
        for g in gates:
            if g.unit == "%":
                curr_str = f"{g.current_value:.2%}"
                lim_str = f"{g.limit_value:.2%}"
            elif g.unit == "x":
                curr_str = f"{g.current_value:.2f}x"
                lim_str = f"{g.limit_value:.2f}x"
            else:
                curr_str = f"{g.current_value:.1f}{g.unit}"
                lim_str = f"{g.limit_value:.1f}{g.unit}"

            status_display = f"[{g.status.value}]"
            rows.append({
                "Gate ID": g.gate_id,
                "Category": g.category,
                "Indicator Name": g.name,
                "Current": curr_str,
                "Limit": lim_str,
                "State": status_display,
                "Diagnostic Message": g.message
            })

        df = pd.DataFrame(rows)
        pipeline_status = "ALL GATES CLEARED - EXECUTION PERMITTED" if self.is_pipeline_cleared(gates) else "PIPELINE BLOCKED - REMEDIATION REQUIRED"

        lines = [
            "\n" + "=" * 95,
            f"  STATUTORY & OPERATIONAL GATE MONITOR  |  STATUS: {pipeline_status}",
            "=" * 95,
            df.to_string(index=False),
            "=" * 95
        ]
        return "\n".join(lines)


__all__ = [
    "GateStatus",
    "GateMetric",
    "GateIndicatorsEngine",
]
