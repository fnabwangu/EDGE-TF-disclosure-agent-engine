"""## Console Utilities Interface (`console/utils/__init__.py`)

The `console/utils/__init__.py` module acts as the public entry point for all formatting helpers, ANSI terminal styling utilities, cryptographic timestamp generators, and numerical transformation routines supporting the **EDGE-TF-disclosure-agent-engine** terminal console.

---

### Exported Utilities

* **`Color` & `style_text`**: Lightweight ANSI terminal formatting wrappers for green/amber/red status telemetry without external dependencies.
* **`format_currency` & `format_pct`**: Financial formatting helpers for large AUM figures, share quantities, basis points, and weights.
* **`generate_audit_hash`**: SHA-256 cryptographic fingerprinting utility for audit logging, sign-offs, and file integrity validation.
* **`get_utc_timestamp`**: Standardized ISO-8601 UTC timestamp generator.
* **`safe_divide`**: Zero-division guard for cross-sectional portfolio analytics and rebalance ratios.
Python"""
# console/utils/__init__.py
"""
EDGE-TF Disclosure Agent Engine - Console Utilities Module.

Provides shared formatting functions, ANSI styling helpers, timestamp utilities,
and cryptographic hashing routines for the terminal interface.
"""

from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Any, Optional, Union


class Color(str, Enum):
    """ANSI color codes for terminal console output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Standard Foregrounds
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


def style_text(text: Any, color: Color = Color.RESET, bold: bool = False) -> str:
    """Wraps text in ANSI escape codes for formatted console output."""
    prefix = f"{Color.BOLD.value if bold else ''}{color.value}"
    return f"{prefix}{str(text)}{Color.RESET.value}"


def format_currency(value: Union[float, int], decimals: int = 2) -> str:
    """Formats numeric values as currency strings (e.g., $1,250,000.00)."""
    try:
        return f"${float(value):,{decimals}f}"
    except (ValueError, TypeError):
        return "$0.00"


def format_pct(value: Union[float, int], decimals: int = 2, include_sign: bool = False) -> str:
    """Formats decimal proportions as percentages (e.g., 0.052 -> 5.20%)."""
    try:
        sign = "+" if include_sign and value > 0 else ""
        return f"{sign}{float(value) * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.00%"


def format_bps(value: Union[float, int], decimals: int = 1, include_sign: bool = True) -> str:
    """Formats decimal basis points (e.g., 0.0015 -> +15.0 bps)."""
    try:
        sign = "+" if include_sign and value > 0 else ""
        return f"{sign}{float(value) * 10000:.{decimals}f} bps"
    except (ValueError, TypeError):
        return "0.0 bps"


def get_utc_timestamp() -> str:
    """Returns current UTC timestamp in standardized ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def generate_audit_hash(payload: Union[str, bytes, dict]) -> str:
    """Generates a truncated SHA-256 hash fingerprint for audit records and payloads."""
    if isinstance(payload, dict):
        import json
        serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
    elif isinstance(payload, str):
        serialized = payload.encode("utf-8")
    else:
        serialized = payload

    return hashlib.sha256(serialized).hexdigest()[:16]


def safe_divide(numerator: float, denominator: float, fallback: float = 0.0) -> float:
    """Safely calculates division avoiding ZeroDivisionError or NaN returns."""
    try:
        if denominator == 0.0 or denominator is None:
            return fallback
        result = numerator / denominator
        return fallback if (result != result) else result  # Checks NaN
    except Exception:
        return fallback


__all__ = [
    "Color",
    "style_text",
    "format_currency",
    "format_pct",
    "format_bps",
    "get_utc_timestamp",
    "generate_audit_hash",
    "safe_divide",
]# console utils
