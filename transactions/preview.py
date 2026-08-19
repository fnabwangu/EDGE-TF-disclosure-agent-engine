"""
Transaction preview construction.

Path: transactions/preview.py

Turns a validated intent plus a live quote and portfolio snapshot into the
exact object a human reviews. Nothing here mutates state or contacts a broker.
"""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field

from transactions.schemas import (
    Quote,
    RiskDecision,
    TradeIntent,
    TransactionPreview,
    ValidationResult,
    compute_intent_hash,
)

MAX_ACCEPTABLE_SPREAD_PCT = 0.02
WARN_SPREAD_PCT = 0.01
OPTION_CONTRACT_MULTIPLIER = 100


class PortfolioSnapshot(BaseModel):
    nav: float = Field(gt=0)
    positions_market_value: Dict[str, float] = Field(default_factory=dict)
    option_market_value: float = 0.0

    def weight_of(self, symbol: str) -> float:
        return self.positions_market_value.get(symbol, 0.0) / self.nav

    @property
    def option_allocation(self) -> float:
        return self.option_market_value / self.nav


def resolve_quantity(intent: TradeIntent, price: float) -> float:
    if intent.instrument_type == "OPTION":
        return float(sum(leg.quantity for leg in intent.legs))
    if intent.requested_quantity is not None:
        return float(intent.requested_quantity)
    if price <= 0:
        return 0.0
    return float(int(intent.requested_notional / price))


def liquidity_status(spread_pct: float) -> str:
    if spread_pct > MAX_ACCEPTABLE_SPREAD_PCT:
        return "FAIL"
    if spread_pct > WARN_SPREAD_PCT:
        return "WARN"
    return "PASS"


def build_preview(
    intent: TradeIntent,
    *,
    quote: Quote,
    portfolio: PortfolioSnapshot,
    risk: RiskDecision,
    validation: ValidationResult,
    user_id: str,
    strategy_state: str = "UNKNOWN",
) -> TransactionPreview:
    price = intent.limit_price or quote.mid
    quantity = resolve_quantity(intent, price)
    multiplier = OPTION_CONTRACT_MULTIPLIER if intent.instrument_type == "OPTION" else 1
    notional = quantity * price * multiplier

    signed = notional if intent.direction == "BUY" else -notional
    weight_before = portfolio.weight_of(quote.symbol)
    weight_after = (portfolio.positions_market_value.get(quote.symbol, 0.0) + signed) / portfolio.nav

    option_before: Optional[float] = None
    option_after: Optional[float] = None
    if intent.instrument_type == "OPTION":
        option_before = portfolio.option_allocation
        option_after = (portfolio.option_market_value + signed) / portfolio.nav

    spread = quote.spread_pct
    intent_hash = compute_intent_hash(
        intent,
        user_id=user_id,
        risk_record_hash=risk.record_hash,
        preview_timestamp=quote.timestamp,
        estimated_price=price,
    )

    return TransactionPreview(
        intent_id=intent.intent_id,
        intent_hash=intent_hash,
        symbol=quote.symbol,
        side=intent.direction,
        quantity=quantity,
        estimated_price=price,
        estimated_notional=notional,
        estimated_portfolio_weight_before=weight_before,
        estimated_portfolio_weight_after=weight_after,
        current_option_allocation=option_before,
        post_trade_option_allocation=option_after,
        expected_max_loss=intent.max_loss,
        spread_pct=spread,
        liquidity_status=liquidity_status(spread),
        strategy_state=strategy_state,
        risk_gate_passed=risk.passed,
        risk_reasons=list(risk.reasons),
        validation=validation,
        quote_timestamp=quote.timestamp,
        rationale=intent.rationale,
        invalidation_condition=intent.invalidation_condition,
        approval_required=True,
    )


__all__ = [
    "MAX_ACCEPTABLE_SPREAD_PCT",
    "OPTION_CONTRACT_MULTIPLIER",
    "PortfolioSnapshot",
    "WARN_SPREAD_PCT",
    "build_preview",
    "liquidity_status",
    "resolve_quantity",
]
