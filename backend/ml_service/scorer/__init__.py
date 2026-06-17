"""
scorer/__init__.py — public API for Layer 4.

    from scorer import screen, batch_screen, ScreeningResult, JobRequirements
"""
from .scorer import screen, batch_screen
from .models import ScreeningResult, JobRequirements, Verdict

__all__ = ["screen", "batch_screen", "ScreeningResult", "JobRequirements", "Verdict"]