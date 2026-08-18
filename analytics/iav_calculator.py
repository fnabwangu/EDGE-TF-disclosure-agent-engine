"""Compatibility entry point for Institutional Adoption Velocity.

Indicative NAV calculations live in :mod:`analytics.inav_calculator`.
"""

from .institutional_adoption_velocity import IAVInputs, IAVResult, InstitutionalAdoptionVelocity

__all__ = ["IAVInputs", "IAVResult", "InstitutionalAdoptionVelocity"]
