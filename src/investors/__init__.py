"""Versioned investor-inspired strategy prototypes over FactorResult."""

from src.investors.contracts import InvestorMode, InvestorProfile, StrategyEvaluationResult
from src.investors.engine import StrategyEvaluator
from src.investors.profiles import (
    EXPANDED_PROFILES, PILOT_PROFILES, SHADOW_PROFILES, ZHANG_KUN_V1,
    get_pilot_profile, get_profile,
)

__all__ = [
    "InvestorMode", "InvestorProfile", "StrategyEvaluationResult",
    "StrategyEvaluator", "PILOT_PROFILES", "EXPANDED_PROFILES",
    "SHADOW_PROFILES", "ZHANG_KUN_V1", "get_pilot_profile", "get_profile",
]
