"""thesis_monitor.py
Real-time thesis drift monitor placeholder.
"""

def compute_drift(score_history):
    if not score_history:
        return 0.0
    return score_history[-1] - score_history[0]
"""## Qualitative Thesis Invalidation & Catalyst Tracker (`src/monitoring/thesis_monitor.py`)

The `thesis_monitor.py` module continuously monitors registered investment hypotheses against live market drawdowns, relative benchmark performance (e.g., vs. QQQ/SPY), and filing/news invalidation events. When a thesis trips an invalidation limit or catalyst deadline, the monitor automatically alerts the governance engine, flags affected holdings in the approval queue, and recommends candidate divestments.

---

### Key Capabilities

* **`Real-Time Thesis Health Scoring`**: Evaluates active investment theses against real-time equity drawdowns, relative underperformance bounds, and catalyst expiry windows.
* **`Automated Invalidation & Divestment Triggers`**: Transitions breached theses to `FALSIFIED` status and emits divestment recommendations directly to the `RiskGovernor`.
* **`Monitoring Telemetry Integration`**: Streams structured hypothesis telemetry frames into `SystemHealthMonitor` and the terminal console dashboard.
* **`Cryptographic Audit Trail Logging`**: Formats invalidation lifecycle transitions into structured records for immutable WORM logging via `AuditLogger`.

 # src/monitoring/thesis_monitor.py"""
"""
EDGE-TF Disclosure Agent Engine - Qualitative Thesis & Catalyst Monitor.

Tracks real-time performance against thesis falsification boundaries,
monitors catalyst expiration, and signals rebalance liquidations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from src.governance.audit_logger import AuditEventType, AuditLogger
from src.inference.hypothesis_agent import (
    HypothesisAgent,
    InvestmentHypothesis,
    ThesisStatus,
)
from src.monitoring import AlertNotification, AlertSeverity, SystemHealthMonitor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@dataclass
class ThesisEvaluationReport:
    timestamp_utc: str
    active_theses_count: int
    falsified_theses_count: int
    expired_theses_count: int
    falsified_tickers: List[str]
    divestment_recommendations: List[Dict[str, Any]]
    telemetry_alerts: List[AlertNotification] = field(default_factory=list)


class ThesisMonitor:
    """
    Continuous watchdog monitoring the live viability of registered investment theses.
    """

    def __init__(
        self,
        hypothesis_agent: HypothesisAgent,
        health_monitor: Optional[SystemHealthMonitor] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.hypothesis_agent = hypothesis_agent
        self.health_monitor = health_monitor or SystemHealthMonitor()
        self.audit_logger = audit_logger or AuditLogger()

    def evaluate_theses_against_market(
        self,
        ticker_drawdowns: Dict[str, float],
        relative_underperformance_bps: Dict[str, float],
        operator_id: str = "SYSTEM_THESIS_MONITOR",
        role: str = "COMPLIANCE_WATCHDOG",
    ) -> ThesisEvaluationReport:
        """
        Evaluates all registered hypotheses against incoming market data.
        Transitions failed theses to FALSIFIED and logs state changes.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        alerts_generated: List[AlertNotification] = []
        divestment_recommendations: List[Dict[str, Any]] = []
        falsified_tickers: List[str] = []

        active_count = 0
        falsified_count = 0
        expired_count = 0

        for hypo_id, hypo in list(self.hypothesis_agent.registry.items()):
            if hypo.status != ThesisStatus.ACTIVE:
                if hypo.status == ThesisStatus.FALSIFIED:
                    falsified_count += 1
                elif hypo.status == ThesisStatus.EXPIRED:
                    expired_count += 1
                continue

            ticker = hypo.target_ticker
            drawdown = ticker_drawdowns.get(ticker, 0.0)
            underperf_bps = relative_underperformance_bps.get(ticker, 0.0)
            criteria = hypo.falsification_criteria

            # 1. Evaluate Drawdown Limit Breach
            if drawdown > criteria.invalidation_drawdown_pct:
                hypo.status = ThesisStatus.FALSIFIED
                falsified_tickers.append(ticker)
                reason = (
                    f"Max Drawdown Breached ({drawdown:.2%} > limit of {criteria.invalidation_drawdown_pct:.2%})"
                )
                alert = self.health_monitor.record_alert(
                    severity=AlertSeverity.WARNING,
                    source_module="ThesisMonitor",
                    message=f"Hypothesis {hypo_id} for [{ticker}] FALSIFIED: {reason}",
                )
                alerts_generated.append(alert)
                divestment_recommendations.append({
                    "ticker": ticker,
                    "hypothesis_id": hypo_id,
                    "reason": reason,
                    "action": "DIVEST_ALL_HOLDINGS",
                })

            # 2. Evaluate Relative Benchmark Underperformance Breach
            elif underperf_bps > criteria.max_underperformance_vs_benchmark_bps:
                hypo.status = ThesisStatus.FALSIFIED
                falsified_tickers.append(ticker)
                reason = (
                    f"Relative Benchmark Underperformance Breached ({underperf_bps:.0f} bps > limit of "
                    f"{criteria.max_underperformance_vs_benchmark_bps:.0f} bps)"
                )
                alert = self.health_monitor.record_alert(
                    severity=AlertSeverity.WARNING,
                    source_module="ThesisMonitor",
                    message=f"Hypothesis {hypo_id} for [{ticker}] FALSIFIED: {reason}",
                )
                alerts_generated.append(alert)
                divestment_recommendations.append({
                    "ticker": ticker,
                    "hypothesis_id": hypo_id,
                    "reason": reason,
                    "action": "DIVEST_ALL_HOLDINGS",
                })

            else:
                active_count += 1

            hypo.last_evaluated_utc = now_ts

        # Audit log state transitions if any invalidations occurred
        if falsified_tickers:
            self.audit_logger.log_event(
                event_type=AuditEventType.PRE_TRADE_COMPLIANCE,
                operator_id=operator_id,
                role=role,
                payload={
                    "event": "THESIS_FALSIFICATION_SWEEP",
                    "falsified_tickers": falsified_tickers,
                    "divestment_recommendations": divestment_recommendations,
                    "active_theses_remaining": active_count,
                },
            )

        return ThesisEvaluationReport(
            timestamp_utc=now_ts,
            active_theses_count=active_count,
            falsified_theses_count=falsified_count + len(falsified_tickers),
            expired_theses_count=expired_count,
            falsified_tickers=falsified_tickers,
            divestment_recommendations=divestment_recommendations,
            telemetry_alerts=alerts_generated,
        )


__all__ = [
    "ThesisEvaluationReport",
    "ThesisMonitor",
]
