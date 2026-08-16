import streamlit as st

def render_approval_queue():
    st.header("Approval Queue")
    st.write("No approvals in scaffold.")
## Approval Queue Component (`console/components/approval_queue.py`)

The `approval_queue.py` module implements human-in-the-loop oversight and dual-authorization workflows for model rebalances, portfolio composition disclosures, and critical override events.

---

### Key Capabilities

* **`Dual-Authorization State Machine`**: Requires designated governance roles (e.g., `CHIEF_COMPLIANCE_OFFICER`, `LEAD_PORTFOLIO_MANAGER`, `CHIEF_FINANCIAL_OFFICER`) to review and cryptographically sign off on queue items.
* **`Risk & Disclosure Context Injection`**: Binds rebalance orders, pre-trade compliance audits, and daily PCF payloads directly to the pending approval ticket.
* **`Console Telemetry & Terminal UI`**: Formats pending approval tickets into scannable console views with visual inspection tables.
* **`Immutable Audit Trail`**: Records sign-off timestamps, signor credentials, decision statuses (`PENDING`, `APPROVED`, `REJECTED`), and justification notes.
Python
# console/components/approval_queue.py
"""
EDGE-TF Disclosure Agent Engine - Human-in-the-Loop Approval Queue.

Manages dual-authorization workflows, pending trade queues, regulatory
disclosure sign-offs, and interactive console rendering.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Set
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ItemCategory(str, Enum):
    REBALANCE_ORDER_BATCH = "REBALANCE_ORDER_BATCH"
    PCF_DISCLOSURE = "PCF_DISCLOSURE"
    KILL_SWITCH_RESET = "KILL_SWITCH_RESET"
    POLICY_OVERRIDE = "POLICY_OVERRIDE"


@dataclass
class SignatureRecord:
    signor_id: str
    role: str
    action: str  # 'APPROVE' or 'REJECT'
    timestamp_utc: str
    justification: str
    signature_hash: str


@dataclass
class QueueItem:
    ticket_id: str
    category: ItemCategory
    description: str
    required_signatory_roles: Set[str]
    payload: Dict[str, Any]
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: ApprovalStatus = ApprovalStatus.PENDING
    signatures: List[SignatureRecord] = field(default_factory=list)
    rejection_reason: Optional[str] = None


class ApprovalQueueManager:
    """
    Coordinates pending compliance sign-offs and dual-approval gates
    before releasing orders to the broker EMS or publishing PCF disclosures.
    """

    def __init__(self, authorized_roles: Optional[List[str]] = None):
        self.authorized_roles = set(authorized_roles or [
            "CHIEF_COMPLIANCE_OFFICER",
            "LEAD_PORTFOLIO_MANAGER",
            "CHIEF_FINANCIAL_OFFICER"
        ])
        self.queue: Dict[str, QueueItem] = {}

    def _generate_signature_hash(self, ticket_id: str, signor_id: str, timestamp: str) -> str:
        raw_msg = f"{ticket_id}:{signor_id}:{timestamp}"
        return hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()[:16]

    def create_rebalance_ticket(
        self,
        orders_data: List[Dict[str, Any]],
        compliance_summary: Dict[str, Any],
        turnover_pct: float,
        nav_usd: float
    ) -> QueueItem:
        """Enqueues a rebalance order batch for compliance and PM sign-off."""
        ticket_id = f"TKT-REBAL-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        description = (
            f"Weekly Rebalance Batch: {len(orders_data)} orders, "
            f"Estimated Turnover: {turnover_pct:.2%}, Total NAV: ${nav_usd:,.2f}"
        )
        required_roles = {"CHIEF_COMPLIANCE_OFFICER", "LEAD_PORTFOLIO_MANAGER"}

        item = QueueItem(
            ticket_id=ticket_id,
            category=ItemCategory.REBALANCE_ORDER_BATCH,
            description=description,
            required_signatory_roles=required_roles,
            payload={
                "orders": orders_data,
                "compliance_summary": compliance_summary,
                "turnover_pct": turnover_pct,
                "nav_usd": nav_usd
            }
        )
        self.queue[ticket_id] = item
        logging.info(f"Enqueued Rebalance Ticket: {ticket_id}")
        return item

    def create_pcf_disclosure_ticket(self, pcf_payload: Dict[str, Any]) -> QueueItem:
        """Enqueues daily Portfolio Composition File (PCF) for pre-market AP transmission sign-off."""
        ticket_id = f"TKT-PCF-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        lines_count = len(pcf_payload.get("basket_composition", []))
        description = f"Daily PCF AP Publication Payload: {lines_count} constituents"
        required_roles = {"CHIEF_COMPLIANCE_OFFICER"}

        item = QueueItem(
            ticket_id=ticket_id,
            category=ItemCategory.PCF_DISCLOSURE,
            description=description,
            required_signatory_roles=required_roles,
            payload=pcf_payload
        )
        self.queue[ticket_id] = item
        logging.info(f"Enqueued PCF Ticket: {ticket_id}")
        return item

    def sign_ticket(
        self,
        ticket_id: str,
        signor_id: str,
        role: str,
        action: str,
        justification: str
    ) -> QueueItem:
        """
        Records a signature on a pending ticket and evaluates whether dual-authorization is fulfilled.
        """
        if ticket_id not in self.queue:
            raise KeyError(f"Ticket ID '{ticket_id}' not found in active approval queue.")

        item = self.queue[ticket_id]
        if item.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot sign ticket '{ticket_id}' in state '{item.status}'.")

        if role not in self.authorized_roles:
            raise PermissionError(f"Role '{role}' is not an authorized signor role.")

        now_ts = datetime.now(timezone.utc).isoformat()
        sig_hash = self._generate_signature_hash(ticket_id, signor_id, now_ts)

        sig_record = SignatureRecord(
            signor_id=signor_id,
            role=role,
            action=action.upper(),
            timestamp_utc=now_ts,
            justification=justification,
            signature_hash=sig_hash
        )
        item.signatures.append(sig_record)

        if action.upper() == "REJECT":
            item.status = ApprovalStatus.REJECTED
            item.rejection_reason = f"Rejected by {signor_id} ({role}): {justification}"
            logging.warning(f"Ticket {ticket_id} REJECTED: {item.rejection_reason}")
            return item

        # Check if all required roles have approved
        approved_roles = {s.role for s in item.signatures if s.action == "APPROVE"}
        if item.required_signatory_roles.issubset(approved_roles):
            item.status = ApprovalStatus.APPROVED
            logging.info(f"Ticket {ticket_id} fully APPROVED across all required roles.")

        return item

    def render_console_dashboard(self) -> str:
        """Generates an aligned console table of active and resolved approval tickets."""
        if not self.queue:
            return "\n[APPROVAL QUEUE]: No active or historical tickets in queue."

        rows = []
        for tkt in self.queue.values():
            signed_roles = {s.role for s in tkt.signatures if s.action == "APPROVE"}
            remaining_roles = tkt.required_signatory_roles - signed_roles
            roles_status = "CLEARED" if not remaining_roles else f"Awaiting: {', '.join(remaining_roles)}"

            rows.append({
                "Ticket ID": tkt.ticket_id,
                "Category": tkt.category.value,
                "Status": tkt.status.value,
                "Sign-off State": roles_status,
                "Created (UTC)": tkt.created_at_utc.split("T")[1][:8],
                "Description": (tkt.description[:45] + "...") if len(tkt.description) > 45 else tkt.description
            })

        df = pd.DataFrame(rows)
        lines = [
            "\n" + "=" * 85,
            "  HUMAN-IN-THE-LOOP (HITL) GOVERNANCE & APPROVAL QUEUE",
            "=" * 85,
            df.to_string(index=False),
            "=" * 85
        ]
        return "\n".join(lines)

    def render_ticket_detail_view(self, ticket_id: str) -> str:
        """Renders an inspection view of a single ticket including compliance and payload details."""
        if ticket_id not in self.queue:
            return f"Error: Ticket '{ticket_id}' not found."

        tkt = self.queue[ticket_id]
        lines = [
            "\n" + "*" * 75,
            f"  TICKET INSPECTION: {tkt.ticket_id}",
            "*" * 75,
            f"Category          : {tkt.category.value}",
            f"Status            : {tkt.status.value}",
            f"Created At (UTC)  : {tkt.created_at_utc}",
            f"Required Roles    : {', '.join(tkt.required_signatory_roles)}",
            f"Description       : {tkt.description}",
            "-" * 75,
            "Signatures Logged :"
        ]

        if not tkt.signatures:
            lines.append("  (No signatures recorded yet)")
        else:
            for s in tkt.signatures:
                lines.append(
                    f"  • [{s.action}] {s.signor_id} ({s.role}) at {s.timestamp_utc} "
                    f"| Hash: {s.signature_hash} | Note: {s.justification}"
                )

        if tkt.category == ItemCategory.REBALANCE_ORDER_BATCH:
            orders = tkt.payload.get("orders", [])
            lines.append("-" * 75)
            lines.append(f"Payload Preview ({len(orders)} Orders):")
            if orders:
                df = pd.DataFrame(orders)
                lines.append(df.head(5).to_string(index=False))
                if len(orders) > 5:
                    lines.append(f"  ... and {len(orders) - 5} more orders.")

        lines.append("*" * 75)
        return "\n".join(lines)


__all__ = [
    "ApprovalStatus",
    "ItemCategory",
    "SignatureRecord",
    "QueueItem",
    "ApprovalQueueManager",
]
