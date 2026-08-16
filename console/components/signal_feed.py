import streamlit as st

def render_signal_feed():
    st.header("Signal Feed")
    st.write("No live signals in scaffold — connect ingestion pipeline to see messages.")
## Signal Feed & Real-Time Alpha Telemetry (`console/components/signal_feed.py`)

The `signal_feed.py` module handles real-time quantitative signal streaming, multi-factor Z-score telemetry, ranking shifts, and overlay trigger feeds for the interactive ETF terminal console.

---

### Key Capabilities

* **`Real-Time Signal Streaming`**: Formats raw momentum, quality, low-volatility, and composite alpha scores into live console monitors.
* **`Factor Attribution & Decomposition`**: Displays individual Z-score contributions to each constituent's aggregate alpha rank.
* **`Overlay Trigger Alerts`**: Highlights derivative overlay states (e.g., covered call target delta, active hedge coverage, roll triggers).
* **`Rank Shift Analytics`**: Tracks top positive and negative momentum gainers within the fund universe across rebalance cycles.
Python
# console/components/signal_feed.py
"""
EDGE-TF Disclosure Agent Engine - Signal Feed & Alpha Telemetry Component.

Streams quantitative factor scores, composite alpha rankings, and systematic
overlay triggers to the terminal console.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd


@dataclass
class AlphaSignalSnapshot:
    ticker: str
    composite_alpha: float
    rank: int
    prior_rank: Optional[int]
    momentum_zscore: float
    quality_zscore: float
    low_vol_zscore: float
    target_weight: float
    overlay_shares: int
    signal_timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SignalFeedTelemetry:
    """
    Renders real-time factor score streams, rank movement deltas,
    and derivative overlay alerts for the ETF console.
    """

    @staticmethod
    def format_rank_change(current_rank: int, prior_rank: Optional[int]) -> str:
        """Formats visual rank change indicator."""
        if prior_rank is None:
            return "NEW"
        delta = prior_rank - current_rank  # Positive delta means rank improved (e.g., 5 -> 2 = +3)
        if delta > 0:
            return f"▲ +{delta}"
        elif delta < 0:
            return f"▼ {delta}"
        return "― 0"

    def render_top_alpha_signals(
        self,
        signals: List[AlphaSignalSnapshot],
        top_n: int = 10,
        show_factors: bool = True
    ) -> str:
        """Formats the top N composite alpha assets into an aligned terminal table."""
        if not signals:
            return "\n[SIGNAL FEED]: No active alpha signals available."

        # Sort by rank
        sorted_signals = sorted(signals, key=lambda s: s.rank)[:top_n]
        rows = []

        for s in sorted_signals:
            rank_display = f"#{s.rank:<2} ({self.format_rank_change(s.rank, s.prior_rank)})"
            record = {
                "Rank": rank_display,
                "Ticker": s.ticker,
                "Alpha Score": f"{s.composite_alpha:+.3f}",
                "Target Wt %": f"{s.target_weight:.2%}",
                "Covered Calls": f"{s.overlay_shares:,d} shs" if s.overlay_shares > 0 else "None",
            }

            if show_factors:
                record["Mom Z"] = f"{s.momentum_zscore:+.2f}"
                record["Qual Z"] = f"{s.quality_zscore:+.2f}"
                record["LowVol Z"] = f"{s.low_vol_zscore:+.2f}"

            rows.append(record)

        df = pd.DataFrame(rows)
        lines = [
            "\n" + "=" * 80,
            f"  QUANTITATIVE ALPHA SIGNAL STREAM  |  TOP {len(sorted_signals)} CONSTITUENTS",
            "=" * 80,
            df.to_string(index=False),
            "=" * 80
        ]
        return "\n".join(lines)

    def render_overlay_status(self, signals: List[AlphaSignalSnapshot]) -> str:
        """Summarizes systematic option overlay coverage across the portfolio."""
        active_overlays = [s for s in signals if s.overlay_shares > 0]
        total_overlay_shares = sum(s.overlay_shares for s in active_overlays)

        lines = [
            "\n--- [SYSTEMATIC DERIVATIVES OVERLAY MONITOR] ---",
            f"Active Overlay Positions : {len(active_overlays)} tickers",
            f"Total Covered Shares     : {total_overlay_shares:,d} shares",
            f"Active Contracts         : {total_overlay_shares // 100:,d} contracts"
        ]

        if active_overlays:
            lines.append("Constituents Under Active Write:")
            for s in active_overlays[:5]:
                lines.append(
                    f"  • {s.ticker:<5}: {s.overlay_shares:,d} shs "
                    f"({s.overlay_shares // 100} calls) | Target Weight: {s.target_weight:.2%}"
                )
            if len(active_overlays) > 5:
                lines.append(f"  ... and {len(active_overlays) - 5} additional covered positions.")

        lines.append("------------------------------------------------")
        return "\n".join(lines)

    def render_momentum_movers(
        self,
        signals: List[AlphaSignalSnapshot],
        top_movers_count: int = 3
    ) -> str:
        """Displays top momentum gainers and losers based on rank shifts."""
        movers = [s for s in signals if s.prior_rank is not None]
        if not movers:
            return "[RANK DRIFT]: Insufficient historical signal history for rank change telemetry."

        movers.sort(key=lambda s: (s.prior_rank - s.rank), reverse=True)
        gainers = movers[:top_movers_count]
        losers = movers[-top_movers_count:]

        lines = [
            "\n*** [ALPHA CONSTITUENT RANK DRIFT] ***",
            "Top Upgrades:"
        ]
        for g in gainers:
            delta = g.prior_rank - g.rank
            lines.append(f"  ▲ {g.ticker:<5} : +{delta} ranks (#{g.prior_rank} → #{g.rank}) | Alpha: {g.composite_alpha:+.3f}")

        lines.append("Top Downgrades:")
        for l in reversed(losers):
            delta = l.prior_rank - l.rank
            lines.append(f"  ▼ {l.ticker:<5} : {delta} ranks (#{l.prior_rank} → #{l.rank}) | Alpha: {l.composite_alpha:+.3f}")

        lines.append("**************************************")
        return "\n".join(lines)


__all__ = [
    "AlphaSignalSnapshot",
    "SignalFeedTelemetry",
]
