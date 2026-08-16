"""persistence.py
Multi-period exponential persistence decay (placeholder).
"""
import math

def persistence_decay(value: float, half_life_periods: float, periods: int) -> float:
    rate = math.log(2) / half_life_periods
    return value * math.exp(-rate * periods)
