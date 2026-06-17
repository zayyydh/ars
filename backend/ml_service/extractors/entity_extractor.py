"""
entity_extractor.py — Layer 3 orchestrator.

Runs all three extractors and merges their results into one CandidateProfile.

Merge priority chain (most → least trusted):
    1. Regex    → email, phone, linkedin, github  (deterministic, zero hallucination)
    2. LLM      → skills, experience, education   (semantic understanding)
    3. spaCy    → fills gaps the LLM missed        (fast, structural)

"Merge priority" means: if Regex found an email AND the LLM found an email,
we use Regex's result. If only the LLM found it, we use the LLM's result.
spaCy results only fill in when both Regex and LLM came up empty.

This approach is called "tiered fallback with source priority" — each extractor
is trusted for what it's best at, and lower-priority results never overwrite
higher-priority ones.
"""

import logging
from .models import (
    CandidateProfile, ExperienceEntry, EducationEntry
)
from . import regex_extractor, spacy_extractor, llm_extractor
from ..parsers.models import ParsedResume

logger = logging.getLogger(__name__)


def extract(parsed_resume: ParsedResume) -> CandidateProfile:
    """
    Run all three extractors and return a merged CandidateProfile.

    Args:
        parsed_resume: The ParsedResume from Layer 2

    Returns:
        CandidateProfile — fully populated, ready for Layer 4 scoring

    Never raises — all extractor errors are caught, logged, and reflected
    in extraction_warnings so the pipeline keeps running.
    """
    text     = parsed_resume.raw_text
    warnings = list(parsed_resume.warnings)   # Carry Layer 2 warnings forward

    if not text.strip():
        logger.warning("entity_extractor: received empty text")
        return CandidateProfile(
            extraction_confidence = 0.0,
            extraction_warnings   = ["Empty resume text — nothing to extract"],
        )

    # ── Step 1: run all three extractors ────────────────────────────────────
    logger.info("entity_extractor: running regex extractor")
    regex_result  = _safe_extract(regex_extractor.extract,  text, "regex")

    logger.info("entity_extractor: running spaCy extractor")
    spacy_result  = _safe_extract(spacy_extractor.extract,  text, "spacy")

    logger.info("entity_extractor: running LLM extractor")
    llm_result    = _safe_extract(llm_extractor.extract,    text, "llm")

    # Collect warnings from all extractors
    for result in [regex_result, spacy_result, llm_result]:
        warnings.extend(result.pop("_warnings", []))

    # ── Step 2: merge into CandidateProfile ─────────────────────────────────
    profile = _merge(regex_result, spacy_result, llm_result)

    # ── Step 3: post-merge enrichment ───────────────────────────────────────
    _compute_total_experience(profile, spacy_result)
    _normalise_skills(profile)
    _set_highest_degree(profile)

    # ── Step 4: compute extraction confidence ───────────────────────────────
    profile.extraction_confidence = _confidence_score(profile)
    profile.extraction_warnings   = warnings

    logger.info(f"entity_extractor: done — {profile.summary_line()}")
    return profile


# ──────────────────────────────────────────────────────────────────
# Merge logic
# ──────────────────────────────────────────────────────────────────

def _merge(
    regex:  dict,
    spacy:  dict,
    llm:    dict,
) -> CandidateProfile:
    """
    Apply the priority chain: Regex > LLM > spaCy for each field.

    Contact fields    → Regex wins (deterministic)
    Skills/experience → LLM wins (semantic)
    Structural gaps   → spaCy fills in
    """
    profile = CandidateProfile()

    # ── Contact fields: Regex > LLM > spaCy ─────────────────────────────────
    profile.email    = _first(regex.get("email"),    llm.get("email"),    "")
    profile.phone    = _first(regex.get("phone"),    llm.get("phone"),    "")
    profile.linkedin = _first(regex.get("linkedin"), llm.get("linkedin"), "")
    profile.github   = _first(regex.get("github"),   llm.get("github"),   "")
    profile.name     = _first(regex.get("name"),     llm.get("name"),     spacy.get("name", ""))
    profile.location = _first(regex.get("location"), llm.get("location"), spacy.get("location", ""))

    # ── Skills: LLM wins (deepest understanding), deduplicate ───────────────
    profile.technical_skills = _dedup_list(llm.get("technical_skills", []))
    profile.soft_skills      = _dedup_list(llm.get("soft_skills",      []))
    profile.tools            = _dedup_list(llm.get("tools",            []))
    profile.languages        = _dedup_list(llm.get("languages",        []))
    profile.skills           = _dedup_list(
        profile.technical_skills + profile.soft_skills + profile.tools
    )

    # ── Experience: LLM wins ─────────────────────────────────────────────────
    raw_exp = llm.get("experience", [])
    profile.experience = _parse_experience_list(raw_exp)
    profile.current_title   = llm.get("current_title",   "")
    profile.current_company = llm.get("current_company", "")

    # ── Education: LLM wins ──────────────────────────────────────────────────
    raw_edu = llm.get("education", [])
    profile.education = _parse_education_list(raw_edu)

    # spaCy fills degree_level if LLM missed it
    profile.highest_degree = _first(
        llm.get("highest_degree"),
        spacy.get("degree_level"),
        "",
    )
    profile.primary_field = _first(
        llm.get("primary_field"),
        spacy.get("field_of_study"),
        "",
    )

    # ── Summary ──────────────────────────────────────────────────────────────
    profile.summary = llm.get("summary", "")

    # ── Total experience: LLM wins, spaCy as fallback ────────────────────────
    llm_years   = float(llm.get("total_exp_years",    0) or 0)
    spacy_years = float(spacy.get("total_exp_years",  0) or 0)
    regex_years = float(regex.get("total_exp_years",  0) or 0)
    profile.total_exp_years = llm_years or spacy_years or regex_years

    return profile


# ──────────────────────────────────────────────────────────────────
# Post-merge enrichment
# ──────────────────────────────────────────────────────────────────

def _compute_total_experience(profile: CandidateProfile, spacy_result: dict) -> None:
    """
    If total_exp_years is still 0, compute it from ExperienceEntry durations.
    This handles the case where the LLM failed but we still have experience entries.
    """
    if profile.total_exp_years > 0:
        return

    total_months = sum(e.duration_months for e in profile.experience)
    if total_months > 0:
        profile.total_exp_years = round(total_months / 12, 1)
        return

    # Final fallback: spaCy date ranges
    spacy_months = spacy_result.get("total_exp_months", 0)
    if spacy_months > 0:
        profile.total_exp_years = round(spacy_months / 12, 1)


def _normalise_skills(profile: CandidateProfile) -> None:
    """
    Apply common normalisation rules to skill names.
    The LLM is instructed to normalise but sometimes misses these.
    """
    NORMALISE_MAP = {
        "reactjs": "React",      "react.js": "React",
        "nodejs":  "Node.js",    "node.js":  "Node.js",   "node":    "Node.js",
        "vuejs":   "Vue.js",     "vue.js":   "Vue.js",
        "js":      "JavaScript", "javascript": "JavaScript",
        "ts":      "TypeScript", "typescript":  "TypeScript",
        "py":      "Python",     "python3":  "Python",
        "postgres":"PostgreSQL", "postgresql": "PostgreSQL",
        "mongo":   "MongoDB",    "mongodb":  "MongoDB",
        "k8s":     "Kubernetes", "kubernetes": "Kubernetes",
        "tf":      "TensorFlow", "tensorflow": "TensorFlow",
    }

    def normalise_list(lst: list[str]) -> list[str]:
        result = []
        for s in lst:
            key = s.lower().strip()
            result.append(NORMALISE_MAP.get(key, s))
        return result

    profile.technical_skills = normalise_list(profile.technical_skills)
    profile.languages        = normalise_list(profile.languages)
    profile.tools            = normalise_list(profile.tools)
    profile.skills           = _dedup_list(
        profile.technical_skills + profile.soft_skills + profile.tools
    )


def _set_highest_degree(profile: CandidateProfile) -> None:
    """
    If highest_degree is empty but we have education entries, derive it.
    Rank: phd > masters > bachelors > diploma > high_school
    """
    if profile.highest_degree:
        return

    RANK = {"phd": 5, "masters": 4, "bachelors": 3, "diploma": 2, "high_school": 1}
    best = ""
    best_rank = 0

    for edu in profile.education:
        rank = RANK.get(edu.degree_level, 0)
        if rank > best_rank:
            best_rank = rank
            best = edu.degree_level

    profile.highest_degree = best


# ──────────────────────────────────────────────────────────────────
# Confidence scoring
# ──────────────────────────────────────────────────────────────────

def _confidence_score(profile: CandidateProfile) -> float:
    """
    Rate 0–1 how complete and reliable the extraction is.

    We award points for key fields being populated:
        0.15  name
        0.15  email
        0.20  skills (at least 3)
        0.25  experience (at least 1 entry)
        0.15  education (at least 1 entry)
        0.10  total_exp_years > 0
    """
    score = 0.0
    if profile.name:                           score += 0.15
    if profile.email:                          score += 0.15
    if len(profile.skills) >= 3:               score += 0.20
    if len(profile.experience) >= 1:           score += 0.25
    if len(profile.education)  >= 1:           score += 0.15
    if profile.total_exp_years > 0:            score += 0.10
    return round(score, 2)


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _first(*values):
    """Return the first non-empty, non-None value from the arguments."""
    for v in values:
        if v:
            return v
    return values[-1] if values else ""


def _dedup_list(lst: list) -> list:
    """Deduplicate a list while preserving order."""
    seen = set()
    result = []
    for item in lst:
        key = str(item).lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _parse_experience_list(raw: list) -> list[ExperienceEntry]:
    """
    Convert raw experience dicts (from LLM) to ExperienceEntry dataclasses.
    Handles both dict input (from LLM JSON) and already-dataclass input.
    """
    entries = []
    for item in raw:
        if isinstance(item, ExperienceEntry):
            entries.append(item)
        elif isinstance(item, dict):
            entries.append(ExperienceEntry(
                company         = item.get("company", ""),
                title           = item.get("title", ""),
                start_date      = item.get("start_date", ""),
                end_date        = item.get("end_date", ""),
                duration_months = int(item.get("duration_months", 0) or 0),
                description     = item.get("description", ""),
                skills_used     = item.get("skills_used", []),
            ))
    return entries


def _parse_education_list(raw: list) -> list[EducationEntry]:
    """Convert raw education dicts to EducationEntry dataclasses."""
    entries = []
    for item in raw:
        if isinstance(item, EducationEntry):
            entries.append(item)
        elif isinstance(item, dict):
            entries.append(EducationEntry(
                institution     = item.get("institution", ""),
                degree          = item.get("degree", ""),
                degree_level    = item.get("degree_level", ""),
                field_of_study  = item.get("field_of_study", ""),
                graduation_year = item.get("graduation_year", ""),
                cgpa            = item.get("cgpa", ""),
            ))
    return entries


def _safe_extract(fn, text: str, name: str) -> dict:
    """
    Call an extractor function safely. Returns {} on any exception
    so one broken extractor never crashes the whole pipeline.
    """
    try:
        return fn(text) or {}
    except Exception as e:
        logger.error(f"entity_extractor: {name} extractor raised — {e}")
        return {"_warnings": [f"{name} extractor error: {e}"]}