"""Console components package.

This package exposes the individual Streamlit component render functions so callers
(can import from console.components) have a single import point.
"""
from .signal_feed import render_signal_feed
from .gate_indicators import render_gate_indicators
from .approval_queue import render_approval_queue

__all__ = [
    "render_signal_feed",
    "render_gate_indicators",
    "render_approval_queue",
]
