"""
EDGE-TF Disclosure Agent Engine - Console UI & Telemetry Components.

This module exposes terminal-based UI elements, status tables,
and telemetry widgets for real-time fund monitoring.

Improvements:
- Defined dataclasses/TypedDicts for input contracts (Order)
- Lazy-import pandas to reduce import overhead
- RebalanceOrderTable accepts dicts, objects, or dataclass instances
- Added `to_dataframe` helper and optional `return_df` flag
- Added lightweight Streamlit adapter functions (lazy-import st)
- Added formatting helpers for percent and currency
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Union


# -----------------------------
# Input contracts / dataclasses
# -----------------------------

@dataclass
class Order:
    ticker: str
    action: str = "HOLD"
    target_weight: float = 0.0  # fractional (e.g., 0.05 -> 5%)
    weight_delta: float = 0.0
    target_shares: int = 0
    estimated_notional_usd: float = 0.0
    suppressed_by_buffer: bool = False
    reason: str = ""


# -----------------------------
# Formatting helpers
# -----------------------------

def _percent_format(value: Optional[float], is_fraction: bool = True) -> str:
    try:
        if value is None:
            return "0.00%"
        v = float(value)
        if is_fraction:
            return f"{v:.2%}"
        # already a percent like 5.0
        return f"{v:.2f}%"
    except Exception:
        return "N/A"


def _currency_format(value: Optional[float]) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


# -----------------------------
# Console components
# -----------------------------

class ComplianceTelemetryWidget:
    """Renders formatted console readouts for pre-trade statutory and regulatory risk checks."""

    @staticmethod
    def render_summary(compliance_audit: Dict[str, Any]) -> str:
        passed = compliance_audit.get("passed_all_checks", False)
        status_banner = "[PASS] ALL RISK CHECKS CLEARED" if passed else "[CRITICAL ALERT] COMPLIANCE BREACH DETECTED"

        lines = [
            "=" * 60,
            f"  {status_banner}",
            "=" * 60,
            f"Total Violations: {compliance_audit.get('total_violations', 0)}",
        ]

        violations = compliance_audit.get("violations_log", [])
        if violations:
            lines.append("-" * 60)
            lines.append("Active Breaches:")
            for v in violations:
                lines.append(f"  • {v}")

        lines.append("=" * 60)
        return "\n".join(lines)


class RebalanceOrderTable:
    """Formats generated rebalance trade instructions into a scannable console table.

    Usage:
        RebalanceOrderTable.render_table(orders)
        RebalanceOrderTable.to_dataframe(orders)

    Accepts orders as Order dataclass instances, plain dicts, or objects with attributes.
    target_weight and weight_delta are expected to be fractional (e.g., 0.05 => 5%).
    """

    @staticmethod
    def _normalize_order(o: Union[Order, Dict[str, Any], object]) -> Dict[str, Any]:
        if isinstance(o, Order):
            return asdict(o)
        if isinstance(o, dict):
            return o
        # handle generic objects via getattr
        fields = [
            "ticker",
            "action",
            "target_weight",
            "weight_delta",
            "target_shares",
            "estimated_notional_usd",
            "suppressed_by_buffer",
            "reason",
        ]
        out = {}
        for f in fields:
            out[f] = getattr(o, f, None)
        return out

    @staticmethod
    def to_dataframe(orders: List[Union[Order, Dict[str, Any], object]]):
        # Lazy-import pandas to keep module lightweight for callers who don't need tabular output
        try:
            import pandas as pd
        except Exception as e:
            raise RuntimeError("pandas is required to produce DataFrame output") from e

        records = []
        for o in orders:
            norm = RebalanceOrderTable._normalize_order(o)
            records.append(
                {
                    "Ticker": norm.get("ticker", "N/A"),
                    "Action": norm.get("action", "HOLD"),
                    "Target %": _percent_format(norm.get("target_weight", 0.0), is_fraction=True),
                    "Delta %": _percent_format(norm.get("weight_delta", 0.0), is_fraction=True),
                    "Shares": int(norm.get("target_shares") or 0),
                    "Est. USD": _currency_format(norm.get("estimated_notional_usd", 0.0)),
                    "Status": "SUPPRESSED" if norm.get("suppressed_by_buffer") else "ACTIVE",
                    "Reason": norm.get("reason") or "",
                }
            )

        df = pd.DataFrame(records)
        # order columns for readability
        cols = [
            "Ticker",
            "Action",
            "Target %",
            "Delta %",
            "Shares",
            "Est. USD",
            "Status",
            "Reason",
        ]
        return df[cols]

    @staticmethod
    def render_table(orders: List[Union[Order, Dict[str, Any], object]], return_df: bool = False):
        if not orders:
            return "No orders generated for current rebalance cycle."

        df = RebalanceOrderTable.to_dataframe(orders)
        if return_df:
            return df
        # default: return printable string
        return df.to_string(index=False)


class ExecutionAuditPanel:
    """Displays OMS/EMS connection status and real-time execution TCA metrics."""

    @staticmethod
    def render_audit_status(
        environment: str,
        active_gateway: str,
        routed_count: int,
        slippage_breaches: int,
    ) -> str:
        return (
            f"\n--- [EMS / BROKER ROUTING PIPELINE] ---\n"
            f"Environment    : {environment.upper()}\n"
            f"Gateway Dest   : {active_gateway}\n"
            f"Orders Routed  : {routed_count}\n"
            f"Slippage Alerts: {slippage_breaches}\n"
            f"----------------------------------------"
        )


class DisclosurePreviewCard:
    """Formats Portfolio Composition File (PCF) summary metadata for AP publication."""

    @staticmethod
    def render_pcf_card(pcf_payload: Dict[str, Any]) -> str:
        header = pcf_payload.get("header", {})
        basket = pcf_payload.get("basket_composition", [])

        return (
            f"\n*** [ETF PORTFOLIO COMPOSITION FILE (PCF) SUMMARY] ***\n"
            f"Timestamp (UTC)   : {header.get('generated_timestamp_utc')}\n"
            f"Creation Unit Size: {header.get('creation_unit_shares', 50000):,} shares\n"
            f"Estimated Cash/CU : {_currency_format(header.get('cash_component_per_unit_usd', 0.0))}\n"
            f"Total Basket Lines: {len(basket)}\n"
            f"Target Endpoint   : {header.get('target_ap_endpoint')}\n"
            f"*******************************************************"
        )


class GovernanceKillSwitchBanner:
    """Renders emergency governance lockdown alerts."""

    @staticmethod
    def render_state(is_locked: bool, rejection_count: int) -> str:
        if is_locked:
            return (
                "\n" + "!" * 65 + "\n"
                "! [EMERGENCY KILL SWITCH ENGAGED - OUTBOUND TRADING HALTED]    !\n"
                f"! Consecutive Rejected Orders: {rejection_count}                                  !\n"
                "! Requires CCO or Lead PM dual authorization to reset.          !\n"
                + "!" * 65
                + "\n"
            )
        return "[GOVERNANCE STATE]: System Nominal. Automated kill switch active and armed."


# -----------------------------
# Streamlit adapters (lazy-import streamlit)
# -----------------------------


def streamlit_render_string(text: str) -> None:
    try:
        import streamlit as st
    except Exception:
        # If Streamlit is not available, fall back to printing
        print(text)
        return
    st.text(text)


def streamlit_render_table(orders: List[Union[Order, Dict[str, Any], object]]) -> None:
    try:
        import streamlit as st
    except Exception:
        print(RebalanceOrderTable.render_table(orders))
        return
    df = RebalanceOrderTable.to_dataframe(orders)
    st.table(df)


__all__ = [
    "Order",
    "ComplianceTelemetryWidget",
    "RebalanceOrderTable",
    "ExecutionAuditPanel",
    "DisclosurePreviewCard",
    "GovernanceKillSwitchBanner",
    "streamlit_render_string",
    "streamlit_render_table",
]
