"""
Composes generative views from funnel output.

Path: orchestration/ui_composer.py

Every component built here carries provenance naming the engine that produced
its numbers, so a rendered claim can always be traced back to a computation.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence

from research.funnel import FunnelPosition, FunnelStage, STAGE_ORDER
from research.catalyst import CatalystStrategy
from research.strategy_generation import StrategyCandidate
from research.synthesis import SecuritySynthesis, ThemeSynthesis
from ui.schemas import ActionType, ComponentType, GenerativeView, UIAction, UIComponent
from ui.state import FieldKind, FieldSpec, Persistence


def new_view(title: str, *, summary: Optional[str] = None, **kwargs: Any) -> GenerativeView:
    return GenerativeView(view_id=f"v-{uuid.uuid4().hex[:8]}", title=title, summary=summary, **kwargs)


def funnel_rail(board: Dict[str, List[FunnelPosition]]) -> UIComponent:
    return UIComponent(
        type=ComponentType.FUNNEL_RAIL,
        title="Research pipeline",
        data={
            "stages": [
                {
                    "stage": stage.value,
                    "count": len(board.get(stage.value, [])),
                    "items": [
                        {
                            "strategy_id": p.strategy_id,
                            "thesis_id": p.thesis_id,
                            "intent_id": p.intent_id,
                            "blocked_reason": p.blocked_reason,
                        }
                        for p in board.get(stage.value, [])
                    ],
                }
                for stage in STAGE_ORDER
            ]
        },
    )


def strategy_candidates(candidates: Sequence[StrategyCandidate], *, query: Optional[str] = None) -> UIComponent:
    rows = [
        {
            "strategy": c.strategy_id,
            "theme": c.theme.replace("_", " "),
            "function": c.function.replace("_", " "),
            "clusters": c.cluster_count,
            "signal_funds": ", ".join(c.signal_tickers[:5]),
            "implementation": ", ".join(c.implementation_tickers[:3]) or "-",
            "observability": round(c.observability_score, 3),
            "blocked": "; ".join(c.rejection_reasons) or "",
        }
        for c in candidates
    ]
    return UIComponent(
        type=ComponentType.STRATEGY_CANDIDATES,
        title=f"Strategy candidates{f' for {query}' if query else ''}",
        data={
            "columns": [
                "strategy",
                "theme",
                "function",
                "clusters",
                "signal_funds",
                "implementation",
                "observability",
                "blocked",
            ],
            "rows": rows,
        },
        actions=[
            UIAction(
                type=ActionType.SYNTHESIZE_DISCLOSURES,
                label=f"Synthesize {c.strategy_id}",
                payload={"strategy_id": c.strategy_id},
            )
            for c in candidates
            if c.viable
        ][:5],
        provenance=["config/fund_universe.json", "config/strategy_ontology.json"],
    )


def implementation_candidates(candidates: Sequence[Any], *, strategy_id: str) -> UIComponent:
    """Every eligible expression, side by side. Selecting one is the only way forward."""
    rows = [
        {
            "id": c.id,
            "type": c.type.value,
            "instruments": ", ".join(i.ticker for i in c.instruments) or "-",
            "thesis_fit": c.thesis_fit,
            "expected_return": c.expected_return,
            "downside_risk": c.downside_risk,
            "convexity": c.convexity,
            "carry_cost": c.carry_cost,
            "liquidity": c.liquidity_score,
            "concentration": c.concentration_score,
            "risk_adjusted_score": c.risk_adjusted_score,
            "rationale": c.rationale,
        }
        for c in candidates
    ]
    return UIComponent(
        type=ComponentType.IMPLEMENTATION_CANDIDATES,
        title="Candidate implementations",
        data={
            "columns": [
                "type",
                "instruments",
                "thesis_fit",
                "expected_return",
                "downside_risk",
                "convexity",
                "carry_cost",
                "liquidity",
                "concentration",
                "risk_adjusted_score",
            ],
            "rows": rows,
        },
        actions=[
            UIAction(
                type=ActionType.SELECT_IMPLEMENTATION,
                label=f"Select {c.type.value}",
                payload={"strategy_id": strategy_id, "implementation_id": c.id},
            )
            for c in candidates
        ],
        provenance=["ImplementationGenerator", "BlackScholesEngine", "config/fund_universe.json"],
    )


def iav_gauge(security: SecuritySynthesis) -> UIComponent:
    return UIComponent(
        type=ComponentType.IAV_GAUGE,
        title=f"Institutional adoption velocity - {security.raw_identifier}",
        data={
            "value": round(security.iav.composite_score, 4),
            "state": security.state,
            "core_score": round(security.iav.core_score, 4),
            "quality_multiplier": round(security.iav.quality_multiplier, 4),
            "penalty_total": round(security.iav.penalty_total, 4),
            "accepted": security.iav.accepted,
            "components": {k: round(v, 4) for k, v in security.iav.components.items()},
            "conviction_tier": security.conviction.quality_tier,
            "requested_leverage": round(security.conviction.requested_leverage, 3),
        },
        actions=[
            UIAction(type=ActionType.DRILL_DOWN, label="Show components", payload={"security_id": security.security_id})
        ],
        provenance=["InstitutionalAdoptionVelocity", "ConvictionEngine"],
        confidence=max(0.0, min(1.0, (security.iav.composite_score + 1) / 2)),
    )


def adoption_table(synthesis: ThemeSynthesis) -> UIComponent:
    rows = [
        {
            "security": s.raw_identifier,
            "IAV": round(s.iav.composite_score, 3),
            "tier": s.conviction.quality_tier,
            "clusters": s.manager_breadth,
            "AQD %": f"{s.aqd_pct:+.2%}",
            "flow z": round(s.z_score, 2),
            "persistence": round(s.persistence, 2),
            "diffusion z": round(s.z_diffusion, 2),
            "HHI": round(s.manager_hhi, 3),
            "funds": len(s.holding_funds),
        }
        for s in synthesis.ranked()
    ]
    return UIComponent(
        type=ComponentType.HOLDINGS_DELTA_TABLE,
        title="Active quantity deviation by security",
        data={"columns": list(rows[0].keys()) if rows else [], "rows": rows},
        actions=[UIAction(type=ActionType.DRILL_DOWN, label="Open panel", payload={})],
        provenance=["AnomalyDetector", "ManagerGraphEngine", "InstitutionalGraphEngine"],
    )


def manager_breadth(synthesis: ThemeSynthesis, candidate: StrategyCandidate) -> UIComponent:
    fund_nodes = [
        {"id": f.fund_id, "label": f.ticker, "group": f.manager_cluster_id, "kind": "FUND"}
        for f in candidate.signal_funds
    ]
    security_nodes = [
        {"id": s.security_id, "label": s.raw_identifier, "kind": "SECURITY"} for s in synthesis.securities
    ]
    edges = [
        {"source": fund_id, "target": s.security_id}
        for s in synthesis.securities
        for fund_id in s.holding_funds
    ]
    return UIComponent(
        type=ComponentType.MANAGER_BREADTH_GRAPH,
        title="Independent manager breadth",
        data={
            "nodes": fund_nodes + security_nodes,
            "edges": edges,
            "clusters": candidate.independent_clusters,
        },
        provenance=["ManagerGraphEngine", "config/fund_universe.json"],
    )


def evidence_cards(security: SecuritySynthesis) -> List[UIComponent]:
    supporting = [e for e in security.evidence() if e.stance == "SUPPORTS"]
    return [
        UIComponent(
            type=ComponentType.EVIDENCE_CARD,
            title=row.metric.replace("_", " "),
            data={"claim": row.claim, "sources": [row.source], "metric": row.metric, "value": row.value},
            actions=[UIAction(type=ActionType.OPEN_EVIDENCE, label="Trace", payload={"metric": row.metric})],
            provenance=[row.source],
        )
        for row in supporting
    ]


def counter_thesis(security: SecuritySynthesis) -> UIComponent:
    against = [e for e in security.evidence() if e.stance == "CONTRADICTS"]
    return UIComponent(
        type=ComponentType.COUNTER_THESIS_PANEL,
        title="What would make this wrong",
        data={
            "counter_claims": [
                {"claim": row.claim, "metric": row.metric, "value": row.value, "source": row.source}
                for row in against
            ]
            or [{"claim": "No contradicting evidence surfaced by the current engines.", "metric": "none", "value": 0.0, "source": "DisclosureSynthesizer"}],
            "ambiguity": round(security.ambiguity, 3),
            "manager_hhi": round(security.manager_hhi, 3),
        },
        actions=[UIAction(type=ActionType.OPEN_EVIDENCE, label="Show counter-evidence", payload={})],
        provenance=["DisclosureSynthesizer", "ManagerGraphEngine"],
    )


def implementation_comparison(candidate: StrategyCandidate, security: SecuritySynthesis) -> UIComponent:
    rows = [
        {
            "ticker": f.ticker,
            "name": f.name,
            "classification": f.classification,
            "liquidity": f.liquidity,
            "mandate_relevance": f.mandate_relevance,
            "manager_cluster": f.manager_cluster_id,
        }
        for f in candidate.implementation_funds
    ]
    return UIComponent(
        type=ComponentType.ETF_IMPLEMENTATION_COMPARISON,
        title="Candidate implementations",
        data={"candidates": rows, "target_state": security.state},
        actions=[
            UIAction(
                type=ActionType.DRAFT_INTENT,
                label=f"Design trade in {row['ticker']}",
                payload={"ticker": row["ticker"], "strategy_id": candidate.strategy_id},
            )
            for row in rows[:3]
        ],
        provenance=["config/fund_universe.json"],
    )


def signal_card(candidate: StrategyCandidate, security: SecuritySynthesis) -> UIComponent:
    return UIComponent(
        type=ComponentType.SIGNAL_CARD,
        title=f"{security.raw_identifier} - {security.state}",
        data={
            "ticker": security.raw_identifier,
            "state": security.state,
            "iav": round(security.iav.composite_score, 3),
            "clusters": security.manager_breadth,
            "strategy_id": candidate.strategy_id,
            "summary": candidate.summary(),
        },
        actions=[
            UIAction(
                type=ActionType.OPEN_THESIS,
                label="Open a thesis on this",
                payload={"strategy_id": candidate.strategy_id, "security_id": security.security_id},
            ),
            UIAction(type=ActionType.PIN_TO_WORKBENCH, label="Pin", payload={"strategy_id": candidate.strategy_id}),
        ],
        provenance=["InstitutionalAdoptionVelocity", "ManagerGraphEngine"],
    )


def synthesis_view(
    synthesis: ThemeSynthesis, candidate: StrategyCandidate, *, project_id: Optional[str] = None
) -> GenerativeView:
    view = new_view(
        f"Disclosure synthesis - {candidate.theme.replace('_', ' ')} / {candidate.function.replace('_', ' ')}",
        summary=(
            f"{synthesis.fund_count} disclosing funds across {synthesis.cluster_count} independent "
            f"clusters over {synthesis.observation_dates} disclosure dates."
        ),
        project_id=project_id,
        tool_calls=["synthesize_disclosures"],
    )
    if not synthesis.usable:
        view.components.append(
            UIComponent(
                type=ComponentType.METRIC,
                title="Synthesis blocked",
                data={"value": "; ".join(synthesis.blocking_reasons)},
            )
        )
        return view

    leader = synthesis.leader()
    view.components.append(iav_gauge(leader))
    view.components.append(adoption_table(synthesis))
    view.components.append(manager_breadth(synthesis, candidate))
    view.components.extend(evidence_cards(leader))
    view.components.append(counter_thesis(leader))
    view.components.append(signal_card(candidate, leader))
    if candidate.implementation_funds:
        view.components.append(implementation_comparison(candidate, leader))
    return view


def implementations_view(
    candidates: Sequence[Any], *, strategy_id: str, project_id: Optional[str] = None
) -> GenerativeView:
    """The side-by-side comparison. Nothing here decides which candidate wins."""
    view = new_view(
        "Implementation generation",
        summary=(
            f"{len(candidates)} eligible expressions generated for {strategy_id}, including the "
            "null option. Select one to size it."
        ),
        project_id=project_id,
        tool_calls=["generate_implementations"],
    )
    view.components.append(implementation_candidates(candidates, strategy_id=strategy_id))
    return view


def strategy_view(
    candidates: Sequence[StrategyCandidate],
    *,
    query: Optional[str] = None,
    board: Optional[Dict[str, List[FunnelPosition]]] = None,
    project_id: Optional[str] = None,
) -> GenerativeView:
    view = new_view(
        "Strategy generation",
        summary=f"{len(candidates)} candidate theme/function pairs ranked by observability.",
        project_id=project_id,
        tool_calls=["generate_strategies"],
    )
    view.components.append(strategy_candidates(candidates, query=query))
    if board:
        view.components.append(funnel_rail(board))
    return view


def catalyst_limitations(strategy: "CatalystStrategy") -> UIComponent:
    """States plainly which engines cannot speak to this trade, and why."""
    return UIComponent(
        type=ComponentType.COUNTER_THESIS_PANEL,
        title="What EDGE-TF cannot tell you here",
        data={
            "counter_claims": [{"claim": reason, "metric": "coverage", "value": 0.0, "source": "CatalystPlanner"} for reason in strategy.limitations],
            "ambiguity": 1.0,
            "manager_hhi": 0.0,
        },
        provenance=["CatalystPlanner", "config/fund_universe.json"],
    )


def catalyst_expressions(strategy: "CatalystStrategy") -> UIComponent:
    rows = [
        {
            "ticker": leg.ticker,
            "name": leg.name,
            "classification": leg.classification,
            "function": leg.function,
            "liquidity": leg.liquidity,
        }
        for leg in strategy.legs
    ]
    return UIComponent(
        type=ComponentType.ETF_IMPLEMENTATION_COMPARISON,
        title=f"{strategy.stance.value.title()} expressions",
        data={
            "candidates": rows,
            "benchmarks": [leg.ticker for leg in strategy.benchmarks],
            "target_state": "EVENT_DRIVEN",
        },
        actions=[
            UIAction(
                type=ActionType.DRAFT_INTENT,
                label=f"Design {row['ticker']} trade",
                payload={"ticker": row["ticker"], "strategy_id": strategy.strategy_id},
            )
            for row in rows[:3]
        ],
        provenance=["config/fund_universe.json", "research/lexicon.py"],
    )


CATALYST_FIELDS = [
    FieldSpec(
        field_id="catalyst_date",
        label="Catalyst date",
        kind=FieldKind.DATE,
        required=True,
        help="The dated event this trade is expressed against.",
    ),
    FieldSpec(
        field_id="secondary_catalyst_date",
        label="Secondary catalyst date",
        kind=FieldKind.DATE,
        help="A follow-on event, such as Jackson Hole after FOMC minutes.",
    ),
    FieldSpec(
        field_id="execution_buffer_days",
        label="Execution buffer (days)",
        kind=FieldKind.NUMBER,
        required=True,
    ),
    FieldSpec(field_id="max_loss", label="Maximum loss (USD)", kind=FieldKind.NUMBER, required=True),
    FieldSpec(
        field_id="invalidation_condition",
        label="Invalidation condition",
        kind=FieldKind.TEXT,
        required=True,
    ),
    FieldSpec(
        field_id="stance",
        label="Stance",
        kind=FieldKind.CHOICE,
        options=["HAWKISH", "DOVISH", "VOLATILITY"],
    ),
]


def catalyst_checklist(strategy: "CatalystStrategy") -> UIComponent:
    minimum = strategy.minimum_expiration()
    return UIComponent(
        type=ComponentType.RISK_BUDGET_PANEL,
        title="Event trade requirements",
        data={
            "budgets": [
                {
                    "requirement": "Catalyst date",
                    "value": str(strategy.catalyst_date or "REQUIRED"),
                    "satisfied": strategy.catalyst_date is not None,
                },
                {
                    "requirement": "Execution buffer (days)",
                    "value": strategy.execution_buffer_days,
                    "satisfied": True,
                },
                {
                    "requirement": "Earliest valid expiration",
                    "value": str(minimum or "-"),
                    "satisfied": minimum is not None,
                },
            ]
        },
        fields=CATALYST_FIELDS,
        provenance=["transactions/validator.py"],
    )


def catalyst_view(strategy: "CatalystStrategy", *, project_id: Optional[str] = None) -> GenerativeView:
    view = new_view(
        f"Catalyst trade - {strategy.event_label}",
        summary=(
            f"{strategy.stance.value.title()} stance. "
            f"{len(strategy.legs)} expression vehicle(s), {len(strategy.benchmarks)} benchmark(s). "
            "Adoption signal is unavailable for this complex."
        ),
        project_id=project_id,
        tool_calls=["plan_catalyst"],
    )
    if strategy.legs:
        view.components.append(catalyst_expressions(strategy))
    view.components.append(catalyst_checklist(strategy))
    view.components.append(catalyst_limitations(strategy))
    return view


__all__ = [
    "adoption_table",
    "catalyst_checklist",
    "catalyst_expressions",
    "catalyst_limitations",
    "catalyst_view",
    "counter_thesis",
    "evidence_cards",
    "funnel_rail",
    "iav_gauge",
    "implementation_candidates",
    "implementation_comparison",
    "implementations_view",
    "manager_breadth",
    "new_view",
    "signal_card",
    "strategy_candidates",
    "strategy_view",
    "synthesis_view",
]
