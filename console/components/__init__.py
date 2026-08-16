"""
EDGE-TF Disclosure Agent Engine - Console UI & Telemetry Components.

This module exposes terminal-based UI elements, status tables,
and telemetry widgets for real-time fund monitoring.
"""

from typing import List, Dict, Any
import pandas as pd


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
            f"Total Violations: {compliance_audit.get('total_violations', 0)}"
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
    """Formats generated rebalance trade instructions into a scannable console table."""

    @staticmethod
    def render_table(orders: List[Any]) -> str:
        if not orders:
            return "No orders generated for current rebalance cycle."

        records = []
        for o in orders:
            records.append({
                "Ticker": getattr(o, "ticker", "N/A"),
                "Action": getattr(o, "action", "HOLD"),
                "Target %": f"{getattr(o, 'target_weight', 0.0):.2%}",
                "Delta %": f"{getattr(o, 'weight_delta', 0.0):.2%}",
                "Shares": getattr(o, "target_shares", 0),
                "Est. USD": f"${getattr(o, 'estimated_notional_usd', 0.0):,.2f}",
                "Status": "SUPPRESSED" if getattr(o, "suppressed_by_buffer", False) else "ACTIVE",
                "Reason": getattr(o, "reason", "N/A")
            })

        df = pd.DataFrame(records)
        return df.to_string(index=False)


class ExecutionAuditPanel:
    """Displays OMS/EMS connection status and real-time execution TCA metrics."""

    @staticmethod
    def render_audit_status(
        environment: str,
        active_gateway: str,
        routed_count: int,
        slippage_breaches: int
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
            f"Estimated Cash/CU : ${header.get('cash_component_per_unit_usd', 0.0):,.2f}\n"
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
                + "!" * 65 + "\n"
            )
        return "[GOVERNANCE STATE]: System Nominal. Automated kill switch active and armed."


__all__ = [
    "ComplianceTelemetryWidget",
    "RebalanceOrderTable",
    "ExecutionAuditPanel",
    "DisclosurePreviewCard",
    "GovernanceKillSwitchBanner",
]
