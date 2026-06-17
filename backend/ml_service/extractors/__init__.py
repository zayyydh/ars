"""
extractors/__init__.py — public API for Layer 3.

Other layers import like:
    from extractors import extract_entities, CandidateProfile
"""

from .entity_extractor import extract
from .models import CandidateProfile, ExperienceEntry, EducationEntry

__all__ = ["extract", "CandidateProfile", "ExperienceEntry", "EducationEntry"]