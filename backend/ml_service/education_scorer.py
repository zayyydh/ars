"""
education_scorer.py — score education against JD requirements.

Education scoring is the simplest of the three dimensions because
degree levels have a natural ordering:
    phd > masters > bachelors > diploma > high_school

Key design decisions:
    1. Meeting the required level = full score
    2. Exceeding it (masters when bachelors required) = full score + small bonus
    3. One level below = partial score (diploma for bachelors req)
    4. Two+ levels below = low score
    5. Field of study match adds a bonus (CS degree for a software role)
    6. If JD has NO education requirement → neutral score (70)

Why education has the lowest weight (20%)?
    In software engineering, a self-taught developer with a diploma
    and strong skills/experience beats an under-skilled PhD candidate.
    Education is a signal, not a gate — except for roles that legally
    require certain qualifications (medicine, law, chartered accounting).
    For those roles you'd raise the weight to 40-50%.
"""

import logging

logger = logging.getLogger(__name__)

# Degree level → numeric rank (higher = more qualified)
DEGREE_RANK: dict[str, int] = {
    "high_school": 1,
    "diploma":     2,
    "bachelors":   3,
    "masters":     4,
    "phd":         5,
}

# Fields considered closely related for bonus calculation
# If the JD prefers "Computer Science" and candidate has one of these → partial bonus
RELATED_FIELDS: list[set[str]] = [
    {"computer science", "cs", "software engineering", "information technology",
     "it", "computer engineering", "ce", "computing"},
    {"data science", "statistics", "mathematics", "applied mathematics",
     "machine learning", "artificial intelligence"},
    {"electrical engineering", "electronics", "ece", "ee",
     "telecommunications", "signal processing"},
    {"business", "mba", "management", "finance", "economics",
     "business administration"},
    {"mechanical engineering", "civil engineering", "chemical engineering"},
]


def score(
    candidate_degree:  str,
    required_degree:   str,
    candidate_field:   str,
    preferred_fields:  list[str],
) -> dict:
    """
    Score education match.

    Returns:
        dict with keys:
            score          (0–100)
            degree_score   (0–100, just the level component)
            field_score    (0–100, just the field component)
            degree_match   (bool)
            candidate_degree
            required_degree
    """
    degree_score, degree_match = _score_degree(candidate_degree, required_degree)
    field_score                = _score_field(candidate_field, preferred_fields)

    # If no education requirement at all → neutral
    if not required_degree and not preferred_fields:
        combined = 70.0
    elif not required_degree:
        # Only field preference, no degree level requirement
        combined = 70.0 + field_score * 0.30
    else:
        # Degree level is primary (70%), field is secondary (30%)
        combined = degree_score * 0.70 + field_score * 0.30

    logger.debug(
        f"education_scorer: degree={degree_score:.1f} field={field_score:.1f} "
        f"→ {combined:.1f}"
    )

    return {
        "score":            round(combined,     1),
        "degree_score":     round(degree_score, 1),
        "field_score":      round(field_score,  1),
        "degree_match":     degree_match,
        "candidate_degree": candidate_degree,
        "required_degree":  required_degree,
    }


def _score_degree(candidate: str, required: str) -> tuple[float, bool]:
    """
    Score degree level match.

    Returns (score 0–100, is_match bool)
    """
    # No requirement → neutral, always a match
    if not required:
        return 75.0, True

    # No candidate degree info → assume diploma-level (conservative)
    if not candidate:
        logger.debug("education_scorer: no candidate degree info — defaulting to diploma")
        candidate = "diploma"

    cand_rank = DEGREE_RANK.get(candidate.lower(), 2)
    req_rank  = DEGREE_RANK.get(required.lower(),  3)

    gap = cand_rank - req_rank

    if gap >= 0:
        # Meets or exceeds requirement
        base_score = 90.0
        # Small bonus for exceeding (e.g. masters when bachelors required)
        bonus = min(10.0, gap * 5)
        return min(100.0, base_score + bonus), True

    # Below requirement
    # gap = -1: one level below → 60 points
    # gap = -2: two levels below → 30 points
    # gap = -3+: three levels below → 10 points
    gap_abs = abs(gap)
    if gap_abs == 1:   return 60.0, False
    elif gap_abs == 2: return 30.0, False
    else:              return 10.0, False


def _score_field(candidate_field: str, preferred_fields: list[str]) -> float:
    """
    Score field of study match.

    Returns 0–100:
        100 = exact or near-exact match ("Computer Science" == "CS")
        70  = related field ("Information Technology" for "Computer Science")
        40  = unrelated but STEM ("Mechanical Engineering" for CS role)
        20  = unrelated non-STEM
        50  = no preferred fields stated (neutral)
    """
    if not preferred_fields:
        return 50.0   # No preference → neutral

    if not candidate_field:
        return 40.0   # Unknown field — can't score

    cand_lower = candidate_field.lower().strip()

    # Exact match check
    for pref in preferred_fields:
        pref_lower = pref.lower().strip()
        if cand_lower == pref_lower or pref_lower in cand_lower or cand_lower in pref_lower:
            return 100.0

    # Related field check — same cluster in RELATED_FIELDS
    for pref in preferred_fields:
        pref_lower = pref.lower().strip()
        cand_cluster = _find_cluster(cand_lower)
        pref_cluster = _find_cluster(pref_lower)
        if cand_cluster is not None and cand_cluster == pref_cluster:
            return 70.0

    # Check if candidate is at least in a STEM cluster
    if _find_cluster(cand_lower) is not None:
        return 40.0

    return 20.0


def _find_cluster(field: str) -> int | None:
    """Return the index of the RELATED_FIELDS cluster this field belongs to, or None."""
    for i, cluster in enumerate(RELATED_FIELDS):
        if any(keyword in field for keyword in cluster):
            return i
    return None