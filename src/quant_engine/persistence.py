"""Legacy compatibility shim for persistence decay."""

import math


def persistence_decay(value: float, half_life_periods: float, periods: int) -> float:
    return value * math.exp(-(math.log(2) / half_life_periods) * periods)

__all__ = ["persistence_decay"]
