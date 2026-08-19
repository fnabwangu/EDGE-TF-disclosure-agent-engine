"""
Conversational agent.

Path: orchestration/agent.py

The chat surface. A turn routes a message to an intent, calls deterministic
tools, and composes a view. Chat messages and button clicks land on the same
handlers, so a click is just a pre-parsed sentence.

`LanguageModel` is the seam for a real model: implement `route` to map free
text onto an Intent. With no model configured, `KeywordRouter` runs, so the
whole funnel is operable offline and the deterministic path stays testable.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Protocol
from approvals.service import ApprovalService
from orchestration import ui_composer as compose
from research.catalyst import CatalystPlanner, CatalystStrategy
from research.funnel import FunnelStage, ResearchFunnel
from research.lexicon import Stance, TradeKind, expand
from transactions.schemas import TradeIntent
from transactions.service import TransactionService
from ui.registry import approval_inbox, approval_panel, continuity_panel
from ui.hydration import hydrate
from ui.schemas import ActionType, ComponentType, GenerativeView, UIComponent
from ui.state import Persistence, ProjectStateSnapshot, UIEvent, UIEventType
from workbench.schemas import EventKind, Evidence, IdeaState, Thesis, WatchCondition
from workbench.store import WorkbenchStore

BASE_ALLOCATION = 0.02
DEFAULT_MAX_LOSS_PCT = 0.15
CATALYST_BUFFER_DAYS = 14


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class Intent:
    name: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str
    view: Optional[GenerativeView] = None
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentTurn:
    reply: str
    view: Optional[GenerativeView] = None
    tool_calls: List[str] = field(default_factory=list)


class LanguageModel(Protocol):
    def route(
        self, message: str, *, history: List[ChatMessage], intents: List[str], context: str = ""
    ) -> Optional[Intent]: ...


class KeywordRouter:
    """Deterministic intent routing, used when no language model is configured."""

    PATTERNS = [
        ("continuity", r"\b(where (did|were) we|left off|catch me up|recap|resume)\b"),
        ("inbox", r"\b(inbox|waiting on me|pending|approvals?)\b"),
        ("board", r"\b(pipeline|funnel|board|stages?)\b"),
        ("synthesize", r"\b(synth|synthesi[sz]e|disclosures?|holdings|analy[sz]e|dig into)\b"),
        ("design_trade", r"\b(size it|design a trade|implement|position it)\b"),
        ("open_thesis", r"\b(open a thesis|start a thesis|track this|save this)\b"),
        ("generate", r"\b(strateg|idea|theme|find|show me|explore|screen|research)\b"),
        ("help", r"\b(help|what can you do|how does this work)\b"),
    ]

    def route(
        self, message: str, *, history: List[ChatMessage], intents: List[str], context: str = ""
    ) -> Optional[Intent]:
        text = message.lower().strip()

        # A dated macro event outranks every keyword: it is not an adoption trade.
        concept = expand(message)
        if concept.kind is TradeKind.MACRO_EVENT:
            return Intent(name="catalyst", args={"query": message.strip(), "stance": concept.stance.value})

        for name, pattern in self.PATTERNS:
            if re.search(pattern, text):
                return Intent(name=name, args={"query": message.strip()})
        return Intent(name="generate", args={"query": message.strip()})


class ChatAgent:
    INTENTS = [
        "generate",
        "synthesize",
        "open_thesis",
        "design_trade",
        "catalyst",
        "inbox",
        "continuity",
        "board",
        "help",
    ]

    def __init__(
        self,
        *,
        funnel: ResearchFunnel,
        workbench: WorkbenchStore,
        transactions: TransactionService,
        approvals: ApprovalService,
        project_id: str,
        session_id: str,
        user_id: str,
        model: Optional[LanguageModel] = None,
    ):
        self.funnel = funnel
        self.workbench = workbench
        self.transactions = transactions
        self.approvals = approvals
        self.project_id = project_id
        self.session_id = session_id
        self.user_id = user_id
        self.model = model or KeywordRouter()
        self.history: List[ChatMessage] = []
        self.focus_strategy_id: Optional[str] = None
        self.catalyst_planner = CatalystPlanner(self.funnel.generator)
        self.catalysts: Dict[str, CatalystStrategy] = {}
        self.focus_concept = None

    # -- entry points ------------------------------------------------------

    def send(self, message: str) -> AgentTurn:
        self.history.append(ChatMessage(role="user", content=message))
        intent = self.model.route(
            message, history=self.history, intents=self.INTENTS, context=self.state_context()
        ) or Intent("help")
        turn = self.dispatch(intent)
        self.history.append(ChatMessage(role="assistant", content=turn.reply, view=turn.view))
        return turn

    def project_state(self) -> ProjectStateSnapshot:
        """Authoritative state. The UI is never the source of truth; this is."""
        return self.workbench.project_state(self.project_id, session_id=self.session_id)

    def state_context(self) -> str:
        return self.project_state().as_context()

    def record_ui_event(self, event: UIEvent) -> Optional[AgentTurn]:
        """Persist an interaction, then let the affected view regenerate from state."""
        self.workbench.record_ui_event(event)
        if event.event_type is not UIEventType.FIELD_CHANGED:
            return None
        if event.field_id in {"catalyst_date", "secondary_catalyst_date", "execution_buffer_days", "stance"}:
            if self.focus_concept is not None:
                return self._do_catalyst(query="", stance=self.project_state().value("stance"))
        return None

    def act(self, action: Dict[str, Any]) -> Optional[AgentTurn]:
        """A button click is a pre-parsed intent; it runs the same handlers."""
        kind = action.get("type")
        payload = action.get("payload", {})
        mapping = {
            ActionType.SYNTHESIZE_DISCLOSURES.value: "synthesize",
            ActionType.OPEN_THESIS.value: "open_thesis",
            ActionType.DRAFT_INTENT.value: "design_trade",
        }
        if kind not in mapping:
            return None
        turn = self.dispatch(Intent(name=mapping[kind], args=dict(payload)))
        self.history.append(ChatMessage(role="assistant", content=turn.reply, view=turn.view))
        return turn

    def dispatch(self, intent: Intent) -> AgentTurn:
        handler = getattr(self, f"_do_{intent.name}", None)
        if handler is None:
            return AgentTurn(reply=f"I do not have a handler for '{intent.name}'.")
        turn = handler(**intent.args) if intent.args else handler()
        if turn.view is not None:
            hydrate(turn.view, self.project_state())
        return turn

    # -- handlers ----------------------------------------------------------

    def _do_help(self, query: str = "") -> AgentTurn:
        return AgentTurn(
            reply=(
                "I work the funnel in order. Ask me to **find strategies** in a theme, then "
                "**synthesize the disclosures** for one, then **open a thesis**, then **design a trade**. "
                "I can draft and price, but every commitment of capital needs your approval."
            )
        )

    def _do_generate(self, query: str = "") -> AgentTurn:
        concept = expand(query)
        if concept.kind is TradeKind.MACRO_EVENT:
            return self._do_catalyst(query=query, stance=concept.stance.value)
        # An unrecognized follow-up stays on the topic already in play.
        if not concept.matched and self.focus_concept is not None:
            return self._do_catalyst(query=query, stance=concept.stance.value)

        cleaned = re.sub(
            r"\b(find|show me|strateg\w*|ideas?|about|for|in|explore|screen|research|trade)\b", " ", query.lower()
        )
        candidates = self.funnel.generate(cleaned.strip() or None)
        if not candidates:
            return AgentTurn(reply=self._no_candidates_message(query, concept))

        top = candidates[0]
        view = compose.strategy_view(
            candidates, query=cleaned.strip() or None, board=self.funnel.board(), project_id=self.project_id
        )
        return AgentTurn(
            reply=(
                f"{len(candidates)} candidates. The most observable is **{top.strategy_id}** - {top.summary()}. "
                "Pick one to synthesize its disclosures."
            ),
            view=view,
            tool_calls=["generate_strategies"],
        )

    def _do_catalyst(self, query: str = "", stance: Optional[str] = None) -> AgentTurn:
        concept = expand(query)
        if not concept.matched and self.focus_concept is not None:
            # Follow-up such as "what if they are hawkish": keep the event, change the view.
            carried = self.focus_concept
            concept.concepts = list(carried.concepts)
            concept.functions = set(carried.functions)
            concept.themes = set(carried.themes)
        if stance:
            try:
                concept.stance = Stance(stance)
            except ValueError:
                pass
        if not concept.matched:
            return AgentTurn(reply=self._no_candidates_message(query, concept))
        self.focus_concept = concept

        snapshot = self.project_state()
        dates = [d for d in (_as_date(snapshot.value("catalyst_date")), _as_date(snapshot.value("secondary_catalyst_date"))) if d]
        buffer_days = snapshot.value("execution_buffer_days")

        strategy = self.catalyst_planner.plan(
            concept,
            # The position must survive to the last dated event, not the first.
            catalyst_date=max(dates) if dates else None,
            execution_buffer_days=int(buffer_days) if buffer_days else CATALYST_BUFFER_DAYS,
        )
        self.catalysts[strategy.strategy_id] = strategy
        view = compose.catalyst_view(strategy, project_id=self.project_id)

        if not strategy.legs:
            return AgentTurn(
                reply=(
                    f"**{strategy.event_label}** is a dated macro event, not an institutional adoption theme, "
                    "and this universe holds no instrument expressing that stance."
                ),
                view=view,
            )

        tickers = ", ".join(leg.ticker for leg in strategy.legs[:4])
        benchmarks = ", ".join(leg.ticker for leg in strategy.benchmarks[:3])
        return AgentTurn(
            reply=(
                f"**{strategy.event_label}** is a dated macro event, so I am routing it down the catalyst path, "
                f"not the adoption path.\n\n"
                f"**I cannot give you an IAV here.** The rates, FX and volatility complex in this universe contains "
                f"no active disclosing managers - only passive benchmarks and leveraged implementation vehicles - "
                f"so manager breadth and active quantity deviation have nothing to read. Disclosure lag would not "
                f"resolve a single-day policy catalyst anyway.\n\n"
                f"What I can do: a **{strategy.stance.value.lower()}** stance expresses through **{tickers}**"
                + (f", benchmarked against {benchmarks}" if benchmarks else "")
                + self._catalyst_dates_sentence(strategy)
            ),
            view=view,
            tool_calls=["plan_catalyst"],
        )

    @staticmethod
    def _catalyst_dates_sentence(strategy) -> str:
        if strategy.catalyst_date is None:
            return (
                ". Give me the catalyst date and I will size it with the event discipline enforced - "
                "expiry must clear the catalyst plus the execution buffer."
            )
        return (
            f".\n\nUsing the dates you entered: catalyst **{strategy.catalyst_date}**, buffer "
            f"{strategy.execution_buffer_days} days, so any expiry must fall after "
            f"**{strategy.minimum_expiration()}**."
        )

    def _no_candidates_message(self, query: str, concept) -> str:
        themes = ", ".join(self.funnel.generator.themes()[:6])
        if concept.matched:
            return (
                f"I mapped that to {', '.join(sorted(concept.functions)[:5])}, but no theme/function pair there "
                f"clears the manager-breadth floor. Covered themes: {themes}."
            )
        return (
            f"Nothing in the universe matches that. I cover institutional adoption across: {themes}. "
            "For a dated macro event, name the event (FOMC, Jackson Hole, CPI) and I will route it as a catalyst trade."
        )

    def _do_synthesize(self, query: str = "", strategy_id: Optional[str] = None) -> AgentTurn:
        concept = expand(query)
        if concept.kind is TradeKind.MACRO_EVENT and not strategy_id:
            return self._do_catalyst(query=query, stance=concept.stance.value)

        strategy_id = strategy_id or self._resolve_strategy(query)
        if strategy_id is None:
            return AgentTurn(
                reply=(
                    "I have no candidates in play yet. Ask me to find strategies in a theme first - "
                    f"I cover {', '.join(self.funnel.generator.themes()[:6])}."
                )
            )

        candidate = self.funnel.candidate(strategy_id)
        synthesis = self.funnel.synthesize(strategy_id)
        self.focus_strategy_id = strategy_id
        view = compose.synthesis_view(synthesis, candidate, project_id=self.project_id)

        if not synthesis.usable:
            return AgentTurn(
                reply=f"Synthesis blocked for **{strategy_id}**: {'; '.join(synthesis.blocking_reasons)}.",
                view=view,
                tool_calls=["synthesize_disclosures"],
            )

        leader = synthesis.leader()
        return AgentTurn(
            reply=(
                f"Across {synthesis.fund_count} funds in {synthesis.cluster_count} independent clusters, "
                f"**{leader.raw_identifier}** shows IAV {leader.iav.composite_score:+.3f} "
                f"({leader.conviction.quality_tier}), active deviation {leader.aqd_pct:+.2%}, "
                f"persistence {leader.persistence:+.2f}. Open a thesis to make this durable."
            ),
            view=view,
            tool_calls=["synthesize_disclosures"],
        )

    def _do_open_thesis(
        self, query: str = "", strategy_id: Optional[str] = None, security_id: Optional[str] = None
    ) -> AgentTurn:
        strategy_id = strategy_id or self._resolve_strategy(query)
        synthesis = self.funnel.synthesis(strategy_id) if strategy_id else None
        if synthesis is None or not synthesis.usable:
            return AgentTurn(reply="Synthesize the disclosures first - a thesis needs evidence behind it.")

        candidate = self.funnel.candidate(strategy_id)
        security = next((s for s in synthesis.securities if s.security_id == security_id), synthesis.leader())
        floor = round(max(0.05, security.iav.composite_score * 0.5), 3)
        self.focus_strategy_id = strategy_id

        thesis = Thesis(
            thesis_id=f"th-{uuid.uuid4().hex[:8]}",
            project_id=self.project_id,
            title=f"{candidate.theme.replace('_', ' ')} / {candidate.function.replace('_', ' ')}",
            claim=candidate.thesis_seed,
            universe=[security.raw_identifier] + candidate.implementation_tickers[:3],
            invalidation_condition=f"IAV falls below {floor}",
            conviction=max(0.0, min(1.0, (security.iav.composite_score + 1) / 2)),
            strategy_module="EDGE_TF",
        )
        self._append(EventKind.THESIS_CREATED, subject_id=thesis.thesis_id, payload=thesis.model_dump(mode="json"))
        self._append(
            EventKind.STATE_CHANGED,
            subject_id=thesis.thesis_id,
            payload={"state": IdeaState.RESEARCHING.value, "reason": f"opened from {strategy_id}"},
        )
        for row in security.evidence():
            evidence = Evidence(
                evidence_id=str(uuid.uuid4()),
                thesis_id=thesis.thesis_id,
                claim=row.claim,
                stance=row.stance,
                metric=row.metric,
                value=row.value,
                source_uri=f"engine://{row.source}",
            )
            self._append(
                EventKind.EVIDENCE_ADDED if row.stance == "SUPPORTS" else EventKind.COUNTER_EVIDENCE_ADDED,
                subject_id=thesis.thesis_id,
                payload=evidence.model_dump(mode="json"),
            )
        self._append(
            EventKind.STATE_CHANGED,
            subject_id=thesis.thesis_id,
            payload={"state": IdeaState.EVIDENCED.value, "reason": "disclosure synthesis attached"},
        )
        self._append(
            EventKind.WATCH_CONDITION_SET,
            subject_id=thesis.thesis_id,
            payload=WatchCondition(
                condition_id=f"wc-{uuid.uuid4().hex[:6]}",
                metric="iav",
                operator="<",
                threshold=floor,
                on_breach="DEMOTE",
                description="Adoption velocity collapse",
            ).model_dump(mode="json"),
        )
        self.funnel.mark(strategy_id, FunnelStage.TRADE_DESIGN, thesis_id=thesis.thesis_id)

        view = compose.new_view(
            f"Thesis opened - {thesis.title}", project_id=self.project_id, tool_calls=["create_thesis"]
        )
        view.components.append(compose.signal_card(candidate, security))
        view.components.extend(compose.evidence_cards(security))
        view.components.append(compose.counter_thesis(security))
        if candidate.implementation_funds:
            view.components.append(compose.implementation_comparison(candidate, security))

        return AgentTurn(
            reply=(
                f"Opened **{thesis.title}** with {len(security.evidence())} pieces of evidence and a standing "
                f"watch condition: IAV below {floor} demotes it automatically, in this session or any later one."
            ),
            view=view,
            tool_calls=["create_thesis", "record_evidence", "set_watch_condition"],
        )

    def _do_design_trade(
        self, query: str = "", ticker: Optional[str] = None, strategy_id: Optional[str] = None
    ) -> AgentTurn:
        if strategy_id and strategy_id.startswith("catalyst:"):
            return self._design_catalyst_trade(strategy_id, ticker)

        concept = expand(query)
        if concept.kind is TradeKind.MACRO_EVENT and not strategy_id:
            return self._do_catalyst(query=query, stance=concept.stance.value)

        strategy_id = strategy_id or self._resolve_strategy(query)
        synthesis = self.funnel.synthesis(strategy_id) if strategy_id else None
        if synthesis is None or not synthesis.usable:
            known = ", ".join(sorted(self.funnel._synthesis)) or "none yet"
            return AgentTurn(
                reply=(
                    "I size from evidence, and none is attached yet. Synthesized strategies: "
                    f"{known}. Ask me to synthesize one, or name a dated macro event and I will "
                    "route it as a catalyst trade instead."
                )
            )

        position = self.funnel.positions.get(strategy_id)
        if position is None or position.thesis_id is None:
            return AgentTurn(
                reply=(
                    f"**{strategy_id}** is synthesized but has no thesis. No position exists without a "
                    "recorded reason and invalidation - say 'open a thesis on this' first."
                )
            )

        candidate = self.funnel.candidate(strategy_id)
        security = synthesis.leader()
        ticker = ticker or (candidate.implementation_tickers[0] if candidate.implementation_tickers else None)
        if ticker is None:
            return AgentTurn(reply="No implementation vehicle exists for this strategy.")

        nav = self.transactions.portfolio.snapshot().nav
        leverage = float(security.conviction.requested_leverage)
        notional = nav * BASE_ALLOCATION * leverage

        intent = TradeIntent(
            intent_id=f"intent-{uuid.uuid4().hex[:8]}",
            strategy_module="EDGE_TF",
            underlying=ticker,
            instrument_type="ETF",
            direction="BUY" if security.iav.composite_score >= 0 else "SELL",
            thesis_id=position.thesis_id,
            requested_notional=round(notional, 2),
            max_loss=round(notional * DEFAULT_MAX_LOSS_PCT, 2),
            maximum_holding_period_days=180,
            profit_targets=[1.15, 1.30],
            invalidation_condition=f"IAV falls below {max(0.05, security.iav.composite_score * 0.5):.3f}",
            exit_plan="Scale out at both targets; exit in full on invalidation or watch-condition breach.",
            rationale=(
                f"{security.manager_breadth} independent clusters, active deviation {security.aqd_pct:+.2%}, "
                f"IAV {security.iav.composite_score:+.3f} ({security.conviction.quality_tier})."
            ),
            generated_by="EDGE_TF",
        )
        self.transactions.register_draft(intent)
        self._append(
            EventKind.INTENT_LINKED,
            subject_id=position.thesis_id,
            payload={"intent_id": intent.intent_id, "state": "DRAFT"},
        )
        record = self.transactions.create_preview(
            intent.intent_id, user_id=self.user_id, strategy_state=security.state
        )
        self._append(
            EventKind.INTENT_STATE_CHANGED,
            payload={"intent_id": intent.intent_id, "state": record.state.value},
        )
        self.funnel.mark(strategy_id, FunnelStage.APPROVAL, intent_id=intent.intent_id)

        view = compose.new_view(
            f"Proposed implementation - {ticker}", project_id=self.project_id, tool_calls=["request_preview"]
        )
        if record.preview is not None:
            view.components.append(approval_panel(record.preview))
        else:
            view.components.append(
                UIComponent(type=ComponentType.METRIC, title="Preview blocked", data={"value": record.state.value})
            )

        preview = record.preview
        detail = (
            f"{preview.side} {preview.quantity:g} {preview.symbol} at {preview.estimated_price:,.2f} "
            f"(${preview.estimated_notional:,.0f}), weight {preview.estimated_portfolio_weight_before:.2%} -> "
            f"{preview.estimated_portfolio_weight_after:.2%}."
            if preview
            else "No preview could be produced."
        )
        return AgentTurn(
            reply=f"Drafted at conviction leverage {leverage:.2f}x. {detail} This needs your approval.",
            view=view,
            tool_calls=["draft_trade_intent", "request_preview"],
        )

    def _design_catalyst_trade(self, strategy_id: str, ticker: Optional[str]) -> AgentTurn:
        strategy = self.catalysts.get(strategy_id)
        if strategy is None:
            return AgentTurn(reply="That catalyst plan is no longer in this session. Name the event again.")

        view = compose.catalyst_view(strategy, project_id=self.project_id)
        if strategy.catalyst_date is None:
            return AgentTurn(
                reply=(
                    f"I will not size **{strategy.event_label}** without a catalyst date. An event trade needs "
                    "the dated catalyst, an execution buffer, a defined max loss and an invalidation condition - "
                    "expiry has to clear the catalyst plus the buffer. Give me the date and I will draft it."
                ),
                view=view,
            )

        leg = next((l for l in strategy.legs if l.ticker == ticker), strategy.primary)
        return AgentTurn(
            reply=(
                f"Ready to draft {leg.ticker} for {strategy.event_label} on {strategy.catalyst_date}. "
                f"Earliest valid expiration is {strategy.minimum_expiration()}."
            ),
            view=view,
        )

    def _do_inbox(self, query: str = "") -> AgentTurn:
        actions = self.approvals.pending(project_id=self.project_id)
        previews = [
            r.preview
            for r in self.transactions.records()
            if r.preview is not None and r.state.value == "AWAITING_APPROVAL"
        ]
        view = compose.new_view("Waiting on you", project_id=self.project_id, tool_calls=["get_approval_inbox"])
        view.components.append(approval_inbox(previews=previews, actions=actions))
        count = len(actions) + len(previews)
        return AgentTurn(
            reply=f"{count} item(s) need a decision from you." if count else "Nothing is waiting on you.",
            view=view,
            tool_calls=["get_approval_inbox"],
        )

    def _do_continuity(self, query: str = "") -> AgentTurn:
        brief = self.workbench.open_session(project_id=self.project_id, actor=self.user_id)
        self.session_id = brief.session_id
        view = compose.new_view("Where we left off", project_id=self.project_id, tool_calls=["open_session"])
        view.components.append(continuity_panel(brief))
        return AgentTurn(
            reply=(
                f"{len(brief.active_theses)} active thesis/theses, {len(brief.open_transactions)} open transaction(s), "
                f"{len(brief.breached_conditions)} breached condition(s) since your last session."
            ),
            view=view,
            tool_calls=["open_session"],
        )

    def _do_board(self, query: str = "") -> AgentTurn:
        view = compose.new_view("Research pipeline", project_id=self.project_id)
        view.components.append(compose.funnel_rail(self.funnel.board()))
        return AgentTurn(reply="Here is where every idea currently sits.", view=view)

    # -- internals ---------------------------------------------------------

    def _resolve_strategy(self, query: str) -> Optional[str]:
        text = (query or "").lower()

        explicit = re.search(r"\b([a-z][a-z_]+):([a-z][a-z_]+)\b", text)
        if explicit:
            return f"{explicit.group(1)}:{explicit.group(2)}"

        for strategy_id in self.funnel.positions:
            if strategy_id.lower() in text:
                return strategy_id

        # Match on the function half only; theme words are too common to disambiguate.
        tokens = {t for t in re.split(r"[^a-z0-9]+", text) if len(t) > 3}
        best, best_hits = None, 0
        for strategy_id in self.funnel.positions:
            function_words = set(strategy_id.partition(":")[2].split("_"))
            hits = len(tokens & function_words)
            if hits > best_hits:
                best, best_hits = strategy_id, hits
        if best:
            return best

        if self.focus_strategy_id:
            return self.focus_strategy_id
        viable = [s for s, p in self.funnel.positions.items() if p.blocked_reason is None]
        return viable[0] if viable else next(iter(self.funnel.positions), None)

    def _append(self, kind: EventKind, **kwargs: Any) -> None:
        self.workbench.append(
            kind, project_id=self.project_id, session_id=self.session_id, actor=self.user_id, **kwargs
        )


__all__ = ["AgentTurn", "ChatAgent", "ChatMessage", "Intent", "KeywordRouter", "LanguageModel"]
