"""
experience_scorer.py — score experience against JD requirements.

Two sub-dimensions:
    1. Years of experience — does the candidate meet the minimum?
    2. Role/seniority match — are their past titles relevant?

Scoring is intentionally non-linear:
    - Meeting the minimum exactly = full score, not a penalty
    - Exceeding the minimum = small bonus (up to 10 pts) — more experience is good
    - Falling short by 1 year = moderate penalty
    - Falling short by 3+ years = heavy penalty
    - Exceeding the MAXIMUM (if set) = moderate penalty (overqualified)

Why non-linear?
    A JD says "3+ years". A candidate with 3 years and one with 7 years both
    qualify. Linear scoring would give 7/3 = 233% — nonsensical.
    We cap the bonus for over-qualification and penalise under-qualification
    on a curve so a 2.5-year candidate (close to 3) isn't scored the same
    as a 0-year candidate.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Seniority levels ordered lowest → highest
SENIORITY_LEVELS = [
    "intern", "trainee",
    "junior", "associate", "entry",
    "mid", "intermediate",
    "senior", "lead", "principal", "staff",
    "manager", "director", "head", "vp", "chief", "cto", "ceo",
]


def score(
    candidate_exp_years: float,
    min_exp_years:       float,
    max_exp_years:       float,
    candidate_roles:     list[str],
    required_roles:      list[str],
) -> dict:
    """
    Score experience match.

    Returns:
        dict with keys:
            score           (0–100)
            years_score     (0–100, just the years component)
            role_score      (0–100, just the role relevance component)
            exp_gap         (negative = underqualified, 0+ = meets/exceeds)
            candidate_years
            required_years
    """
    years_score = _score_years(candidate_exp_years, min_exp_years, max_exp_years)
    role_score  = _score_roles(candidate_roles, required_roles)

    # Combine: years are more objective, weight them more
    # If no role requirements, 100% years score
    if not required_roles:
        combined = years_score
    else:
        combined = years_score * 0.70 + role_score * 0.30

    exp_gap = candidate_exp_years - min_exp_years

    logger.debug(
        f"experience_scorer: {candidate_exp_years:.1f}yrs vs min={min_exp_years:.1f} "
        f"→ years={years_score:.1f} role={role_score:.1f} combined={combined:.1f}"
    )

    return {
        "score":           round(combined,    1),
        "years_score":     round(years_score, 1),
        "role_score":      round(role_score,  1),
        "exp_gap":         round(exp_gap,     1),
        "candidate_years": candidate_exp_years,
        "required_years":  min_exp_years,
    }


def _score_years(actual: float, minimum: float, maximum: float) -> float:
    """
    Score years of experience on a 0–100 scale.

    Curve:
        actual >= minimum              → 85 base points
        actual >= minimum + 2          → up to 100 (bonus for breadth)
        actual == 0 and minimum == 0   → 75 (neutral — no req, no exp)
        actual < minimum               → scaled penalty using square root
        actual > maximum (if set)      → slight penalty for overqualification
    """
    # No experience requirement → neutral score
    if minimum <= 0:
        return 75.0

    # Candidate has no experience at all
    if actual <= 0:
        return 0.0

    # Underqualified
    if actual < minimum:
        # How far short are they, as a fraction of the requirement?
        shortfall_fraction = (minimum - actual) / minimum
        # Square root curve: being 50% short = 29% penalty (not 50%)
        # This avoids punishing a 2.8yr candidate for a 3yr req as harshly
        # as a 0yr candidate.
        import math
        penalty = math.sqrt(shortfall_fraction)
        return max(0.0, round((1 - penalty) * 85, 1))

    # Meets minimum exactly or above
    base = 85.0

    # Bonus for exceeding minimum (capped at +15 = 100 total)
    excess = actual - minimum
    bonus  = min(15.0, excess * 3)   # +3 pts per extra year, up to +15

    score = base + bonus

    # Penalty if exceeds stated maximum (overqualified)
    if maximum < 90 and actual > maximum:
        overqualified_by = actual - maximum
        penalty = min(15.0, overqualified_by * 5)
        score -= penalty

    return round(min(100.0, max(0.0, score)), 1)


def _score_roles(candidate_roles: list[str], required_roles: list[str]) -> float:
    """
    Score how relevant the candidate's past roles are to what the JD asks for.

    Strategy:
        1. Normalise both lists to lowercase
        2. Check for keyword overlap (title words in common)
        3. Check seniority alignment (if JD wants "senior", does candidate have senior exp?)
    """
    if not required_roles:
        return 75.0   # No role requirement → neutral

    if not candidate_roles:
        return 40.0   # Has experience (we wouldn't call this if exp=0) but no title data

    cand_text = " ".join(candidate_roles).lower()
    req_text  = " ".join(required_roles).lower()

    # Extract meaningful words (skip generic words)
    STOP_WORDS = {"the", "a", "an", "of", "and", "or", "in", "at", "for", "to"}

    req_words  = {w for w in re.findall(r"\w+", req_text)  if w not in STOP_WORDS and len(w) > 2}
    cand_words = {w for w in re.findall(r"\w+", cand_text) if w not in STOP_WORDS and len(w) > 2}

    if not req_words:
        return 75.0

    overlap     = req_words & cand_words
    overlap_rate = len(overlap) / len(req_words)

    # Seniority alignment bonus/penalty
    req_seniority  = _seniority_level(req_text)
    cand_seniority = _seniority_level(cand_text)
    seniority_bonus = _seniority_bonus(cand_seniority, req_seniority)

    base  = overlap_rate * 80   # Up to 80 points for title keyword match
    total = min(100.0, base + seniority_bonus)

    return round(total, 1)


def _seniority_level(text: str) -> int:
    """
    Return the seniority index (position in SENIORITY_LEVELS) found in text.
    Returns -1 if no seniority keyword found.
    """
    text_lower = text.lower()
    for i, level in enumerate(SENIORITY_LEVELS):
        if level in text_lower:
            return i
    return -1


def _seniority_bonus(candidate_idx: int, required_idx: int) -> float:
    """
    Return a bonus/penalty based on seniority gap.
        Same level         → +10
        One level above    → +5  (slightly senior is fine)
        Two+ levels above  → 0   (overqualified)
        One level below    → -10
        Two+ levels below  → -20
    """
    if candidate_idx < 0 or required_idx < 0:
        return 5.0   # Can't determine → small neutral bonus

    diff = candidate_idx - required_idx
    if diff == 0:    return 10.0
    elif diff == 1:  return 5.0
    elif diff >= 2:  return 0.0
    elif diff == -1: return -10.0
    else:            return -20.0