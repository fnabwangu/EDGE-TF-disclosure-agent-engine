"""
Intent completeness validation.

Path: transactions/validator.py

Encodes the mandate that no position may exist without a thesis, a catalyst,
a defined maximum loss, an exit plan and an invalidation condition. Findings
are field-addressable so a generative UI can highlight exactly what is missing.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from transactions.schemas import (
    TradeIntent,
    ValidationFinding,
    ValidationResult,
)

DEFAULT_EXECUTION_BUFFER_DAYS = 14


def _error(code: str, message: str, field: Optional[str] = None) -> ValidationFinding:
    return ValidationFinding(code=code, severity="ERROR", message=message, field=field)


def _warn(code: str, message: str, field: Optional[str] = None) -> ValidationFinding:
    return ValidationFinding(code=code, severity="WARNING", message=message, field=field)


def validate_intent(intent: TradeIntent, *, today: Optional[date] = None) -> ValidationResult:
    today = today or date.today()
    findings: List[ValidationFinding] = []

    if not intent.thesis_id.strip():
        findings.append(_error("THESIS_MISSING", "Intent has no linked thesis.", "thesis_id"))
    if not intent.invalidation_condition:
        findings.append(
            _error(
                "INVALIDATION_MISSING",
                "An explicit invalidation condition is required before sizing capital.",
                "invalidation_condition",
            )
        )
    if not intent.exit_plan:
        findings.append(_error("EXIT_PLAN_MISSING", "No exit plan defined.", "exit_plan"))
    if intent.max_loss <= 0:
        findings.append(_error("MAX_LOSS_MISSING", "Portfolio max loss must be positive.", "max_loss"))

    if intent.instrument_type == "OPTION":
        findings.extend(_validate_option_intent(intent, today))
    else:
        if intent.requested_quantity is not None and intent.requested_quantity <= 0:
            findings.append(
                _error("QUANTITY_INVALID", "Requested quantity must be positive.", "requested_quantity")
            )
        if intent.requested_notional is not None and intent.requested_notional <= 0:
            findings.append(
                _error("NOTIONAL_INVALID", "Requested notional must be positive.", "requested_notional")
            )

    if not intent.profit_targets:
        findings.append(_warn("PROFIT_TARGETS_MISSING", "No profit targets defined.", "profit_targets"))

    passed = not any(f.severity == "ERROR" for f in findings)
    return ValidationResult(passed=passed, findings=findings)


def _validate_option_intent(intent: TradeIntent, today: date) -> List[ValidationFinding]:
    findings: List[ValidationFinding] = []

    if intent.catalyst_id is None:
        findings.append(_error("CATALYST_MISSING", "Option intent requires a catalyst.", "catalyst_id"))
    if intent.catalyst_date is None:
        findings.append(
            _error("CATALYST_DATE_MISSING", "Option intent requires an expected catalyst date.", "catalyst_date")
        )
    if intent.maximum_holding_period_days is None:
        findings.append(
            _error(
                "HOLDING_PERIOD_MISSING",
                "Option intent requires a maximum holding period.",
                "maximum_holding_period_days",
            )
        )
    if not intent.profit_targets:
        findings.append(
            _error("PROFIT_TARGETS_MISSING", "Option intent requires profit targets.", "profit_targets")
        )

    buffer_days = intent.execution_buffer_days
    if buffer_days is None:
        buffer_days = DEFAULT_EXECUTION_BUFFER_DAYS
        findings.append(
            _warn(
                "EXECUTION_BUFFER_DEFAULTED",
                f"No execution buffer supplied; defaulting to {DEFAULT_EXECUTION_BUFFER_DAYS} days.",
                "execution_buffer_days",
            )
        )

    for leg in intent.legs:
        if leg.limit_price <= 0:
            findings.append(
                _error("ENTRY_PREMIUM_MISSING", f"{leg.option_symbol}: entry premium required.", "legs")
            )
        if leg.expiration <= today:
            findings.append(
                _error("EXPIRATION_PAST", f"{leg.option_symbol}: expiration is not in the future.", "legs")
            )
        if intent.catalyst_date is not None:
            required = (intent.catalyst_date - today).days + buffer_days
            available = (leg.expiration - today).days
            if available <= required:
                findings.append(
                    _error(
                        "EXPIRATION_BEFORE_CATALYST_BUFFER",
                        (
                            f"{leg.option_symbol}: expiration {leg.expiration} does not exceed "
                            f"catalyst {intent.catalyst_date} plus {buffer_days}d execution buffer."
                        ),
                        "legs",
                    )
                )

    return findings


__all__ = ["DEFAULT_EXECUTION_BUFFER_DAYS", "validate_intent"]
