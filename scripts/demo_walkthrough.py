"""
Headless walkthrough of the interaction layer.

Path: scripts/demo_walkthrough.py

Run with:  python -m scripts.demo_walkthrough

Drives the whole flow in the terminal: cross-project overview, session
continuity, the approval inbox, quorum rules, hash-bound approvals, a tampered
order, a watch-condition breach, and the model's tool surface.
"""

from __future__ import annotations

import sys

from approvals.schemas import ApprovalState
from approvals.service import ApprovalError
from console.demo.wiring import build_stack, option_intent_missing_fields, seed
from orchestration.tool_registry import build_tools
from transactions.validator import validate_intent
from ui.registry import action_approval_panel, approval_inbox, approval_panel


def rule(title: str) -> None:
    print(f"\n\033[1m{'=' * 78}\n{title}\n{'=' * 78}\033[0m")


def line(label: str, value: object = "") -> None:
    print(f"  {label:<34}{value}")


def main() -> int:
    stack = seed(build_stack())
    nuclear = "proj-nuclear"

    rule("1. Cross-project overview - what is waiting on a human")
    brief = stack.workbench.workspace_brief()
    for digest in brief.projects:
        flag = "NEEDS ATTENTION" if digest.needs_attention else "quiet"
        line(
            f"{digest.name} [{flag}]",
            f"theses={digest.active_thesis_count} contested={digest.contested_thesis_count} "
            f"pending_approvals={digest.pending_approval_count} breached={digest.breached_condition_count}",
        )
    line("total pending approvals", brief.total_pending_approvals)

    rule("2. New chat session in 'Nuclear power' - rehydrated from the log")
    session = stack.workbench.open_session(project_id=nuclear, actor="op-1")
    line("session_id", session.session_id)
    line("previous session", session.previous_session_id)
    line("project mandate", session.project.mandate)
    for thesis in session.active_theses:
        line(f"thesis {thesis.thesis_id}", f"{thesis.state.value} - {thesis.title}")
    line("open transactions", session.open_transactions)
    line("pending actions", [a["request_id"] for a in session.pending_actions])
    line("unresolved questions", session.unresolved_questions)
    print("  changed since last session:")
    for entry in session.changed_since_last_session[-5:]:
        line(f"  {entry['kind']}", entry["summary"])

    rule("3. Approval inbox - trades and workflow actions in one queue")
    pending = stack.approvals.pending(project_id=nuclear)
    previews = [r.preview for r in stack.transactions.records() if r.preview is not None]
    inbox = approval_inbox(previews=previews, actions=pending)
    for item in inbox.data["items"]:
        line(f"[{item['item_type']}] {item['title']}", f"tier={item['risk_tier']} blocked={item['blocked']}")

    rule("4. Approving a MEDIUM action - one approver, then it executes")
    record = stack.approvals.get("req-promote-nuclear")
    panel = action_approval_panel(record, policy=stack.approvals.policy)
    line("required approvals", panel.data["required_approvals"])
    line("buttons offered", [a.type.value for a in panel.actions])
    stack.approvals.approve("req-promote-nuclear", action_hash=record.action_hash, approver_id="op-2")
    result = stack.approvals.execute("req-promote-nuclear")
    line("state", result.state.value)
    line("executor result", result.result)
    line(
        "thesis state now",
        stack.workbench.projection(project_id=nuclear).theses["th-nuclear"].state.value,
    )

    rule("5. An irreversible change is auto-escalated and cannot be self-approved")
    record = stack.approvals.get("req-illiquid-cap")
    line("declared tier", record.request.risk_tier.value)
    line("effective tier", stack.approvals.policy.effective_tier(record.request).value)
    line("required approvals", record.required_approvals)
    denied = stack.approvals.approve("req-illiquid-cap", action_hash=record.action_hash, approver_id="EDGE_TF")
    line("requester self-approves", f"{denied.state.value} <- refused")
    line("config applied?", stack.applied_config or "{} (nothing changed)")

    rule("6. A trade preview - what the human actually reviews")
    txn = stack.transactions.get("intent-nlr-1")
    preview = txn.preview
    line("symbol / side", f"{preview.symbol} {preview.side}")
    line("quantity", f"{preview.quantity:g} @ {preview.estimated_price:,.2f}")
    line("estimated notional", f"${preview.estimated_notional:,.0f}")
    line(
        "portfolio weight",
        f"{preview.estimated_portfolio_weight_before:.2%} -> {preview.estimated_portfolio_weight_after:.2%}",
    )
    line("liquidity", f"{preview.liquidity_status} (spread {preview.spread_pct:.3%})")
    line("risk gate", "PASS" if preview.risk_gate_passed else f"FAIL {preview.risk_reasons}")
    line("strategy state", preview.strategy_state)
    line("invalidation", preview.invalidation_condition)
    line("intent_hash", preview.intent_hash[:32] + "...")
    line("buttons offered", [a.type.value for a in approval_panel(preview).actions])

    rule("7. Approve, then silently change the size - the approval dies")
    stack.transactions.approve("intent-nlr-1", intent_hash=preview.intent_hash, approver_id="op-2")
    line("after approval", stack.transactions.get("intent-nlr-1").state.value)
    txn.intent.requested_notional = 1_200_000.0
    after = stack.transactions.execute("intent-nlr-1", user_id="op-1")
    line("execute with mutated size", after.state.value)
    line("orders sent to broker", len(stack.broker.submitted))

    rule("8. Re-preview the corrected order and let it through")
    txn.intent.requested_notional = 120_000.0
    record = stack.transactions.create_preview("intent-nlr-1", user_id="op-1", strategy_state="CONFIRMED_ADOPTION")
    stack.transactions.approve("intent-nlr-1", intent_hash=record.preview.intent_hash, approver_id="op-2")
    final = stack.transactions.execute("intent-nlr-1", user_id="op-1")
    line("state", final.state.value)
    line("broker response", final.broker_response)

    rule("9. An incomplete option intent - the UI knows exactly what is missing")
    from transactions.schemas import TradeIntent

    draft = TradeIntent.model_validate(option_intent_missing_fields("th-nuclear"))
    result = validate_intent(draft)
    line("passes?", result.passed)
    for finding in result.findings:
        line(f"  [{finding.severity}] {finding.code}", finding.message)

    rule("10. A watch condition fires while nobody is watching")
    breaches = stack.workbench.evaluate_watch_conditions({"iav": 0.31}, project_id=nuclear)
    line("breaches", breaches)
    line(
        "thesis demoted to",
        stack.workbench.projection(project_id=nuclear).theses["th-nuclear"].state.value,
    )

    rule("11. What the model is allowed to do")
    tools = build_tools(
        transactions=stack.transactions,
        approvals=stack.approvals,
        workbench=stack.workbench,
        project_id=nuclear,
        session_id=session.session_id,
        user_id="op-1",
    )
    for tool in tools:
        line(f"{tool.capability.value:<8} {tool.name}", tool.description.splitlines()[0])
    line("approve / execute exposed?", bool({"approve", "execute"} & {t.name for t in tools}))

    rule("12. The audit chain")
    line("events written", len(stack.workbench.events()))
    line("chain verified", stack.workbench.verify_chain())
    try:
        stack.approvals.approve("req-promote-nuclear", action_hash="x", approver_id="op-2")
    except ApprovalError as exc:
        line("re-approving executed action", f"refused: {exc}")
    assert stack.approvals.get("req-promote-nuclear").state is ApprovalState.EXECUTED
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
