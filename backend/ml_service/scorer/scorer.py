"""
scorer.py — Layer 4 orchestrator. The final step of the entire pipeline.

Takes CandidateProfile + raw JD text → returns ScreeningResult.

This is the function Flask calls. It owns the full scoring flow:
    1. Parse the JD into JobRequirements
    2. Run skill_scorer
    3. Run experience_scorer
    4. Run education_scorer
    5. Combine into weighted total score
    6. Apply verdict thresholds
    7. Return ScreeningResult

The weighted formula:
    total = skill_score  * weight_skills     (default 0.50)
          + exp_score    * weight_experience (default 0.30)
          + edu_score    * weight_education  (default 0.20)

Verdict thresholds (configurable):
    SHORTLIST  total >= 70
    REVIEW     total >= 45
    REJECT     total < 45
"""

import logging
from .models import JobRequirements, ScreeningResult, Verdict, SkillMatchDetail
from .jd_parser import parse as parse_jd
from . import skill_scorer, experience_scorer, education_scorer
from ..extractors.models import CandidateProfile

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# Verdict thresholds — tune these per deployment
# ──────────────────────────────────────────────────────────────────
THRESHOLD_SHORTLIST = 70.0
THRESHOLD_REVIEW    = 45.0


def screen(
    candidate:   CandidateProfile,
    jd_text:     str,
    jd_override: JobRequirements | None = None,
) -> ScreeningResult:
    """
    Run the full scoring pipeline for one candidate against one job.

    Args:
        candidate:   Output of Layer 3 entity extraction
        jd_text:     Raw job description text (string pasted by the user)
        jd_override: Pre-parsed JobRequirements (skip JD parsing if provided).
                     Useful for batch screening — parse JD once, reuse for many candidates.

    Returns:
        ScreeningResult with score, verdict, breakdown, and skill gap details.
    """
    warnings: list[str] = list(candidate.extraction_warnings)

    # ── Step 1: parse the job description ───────────────────────────────────
    if jd_override is not None:
        jd = jd_override
        logger.info("scorer: using pre-parsed JobRequirements")
    else:
        logger.info("scorer: parsing job description")
        jd = parse_jd(jd_text)

    if not jd.required_skills and not jd.preferred_skills:
        warnings.append(
            "No skills could be extracted from the job description. "
            "Skill score will be neutral (50). Consider pasting a more detailed JD."
        )

    # ── Step 2: skill scoring ────────────────────────────────────────────────
    logger.info(
        f"scorer: skill match — candidate has {len(candidate.skills)} skills, "
        f"JD requires {len(jd.required_skills)} + {len(jd.preferred_skills)} preferred"
    )
    skill_result = skill_scorer.score(
        candidate_skills = candidate.skills,
        required_skills  = jd.required_skills,
        preferred_skills = jd.preferred_skills,
    )

    # ── Step 3: experience scoring ───────────────────────────────────────────
    logger.info(
        f"scorer: experience match — candidate has {candidate.total_exp_years:.1f} yrs, "
        f"JD requires {jd.min_exp_years}+"
    )
    candidate_roles = _collect_roles(candidate)
    exp_result = experience_scorer.score(
        candidate_exp_years = candidate.total_exp_years,
        min_exp_years       = jd.min_exp_years,
        max_exp_years       = jd.max_exp_years,
        candidate_roles     = candidate_roles,
        required_roles      = jd.required_roles,
    )

    # ── Step 4: education scoring ────────────────────────────────────────────
    logger.info(
        f"scorer: education match — candidate: {candidate.highest_degree!r}, "
        f"required: {jd.required_degree_level!r}"
    )
    edu_result = education_scorer.score(
        candidate_degree  = candidate.highest_degree,
        required_degree   = jd.required_degree_level,
        candidate_field   = candidate.primary_field,
        preferred_fields  = jd.preferred_fields,
    )

    # ── Step 5: weighted total ───────────────────────────────────────────────
    skill_score = skill_result.score
    exp_score   = exp_result["score"]
    edu_score   = edu_result["score"]

    total = (
        skill_score * jd.weight_skills     +
        exp_score   * jd.weight_experience +
        edu_score   * jd.weight_education
    )
    total = round(min(100.0, max(0.0, total)), 1)

    # ── Step 6: verdict ──────────────────────────────────────────────────────
    if total >= THRESHOLD_SHORTLIST:
        verdict = Verdict.SHORTLIST
    elif total >= THRESHOLD_REVIEW:
        verdict = Verdict.REVIEW
    else:
        verdict = Verdict.REJECT

    # ── Step 7: assemble ScreeningResult ────────────────────────────────────
    result = ScreeningResult(
        # Scores
        total_score       = total,
        verdict           = verdict,
        skill_score       = skill_score,
        experience_score  = exp_score,
        education_score   = edu_score,

        # Skill breakdown
        matched_skills    = skill_result.matched_skills,
        missing_skills    = skill_result.missing_skills,
        extra_skills      = skill_result.extra_skills,
        skill_details     = skill_result.details,

        # Experience breakdown
        candidate_exp_years = exp_result["candidate_years"],
        required_exp_years  = exp_result["required_years"],
        exp_gap             = exp_result["exp_gap"],

        # Education breakdown
        candidate_degree  = edu_result["candidate_degree"],
        required_degree   = edu_result["required_degree"],
        degree_match      = edu_result["degree_match"],

        # Metadata
        candidate_name    = candidate.name,
        job_title         = jd.job_title,
        warnings          = warnings,
    )

    logger.info(
        f"scorer: done — {candidate.name} for '{jd.job_title}' → "
        f"{total:.1f}/100 [{verdict.value}]"
    )
    return result


def batch_screen(
    candidates: list[CandidateProfile],
    jd_text:    str,
) -> list[ScreeningResult]:
    """
    Screen multiple candidates against the same JD.

    Parses the JD once and reuses it for all candidates — avoids N LLM calls
    for JD parsing when screening a batch. Results are sorted by score descending.

    Example:
        results = batch_screen([profile1, profile2, profile3], jd_text)
        for r in results:
            print(r.summary())
    """
    logger.info(f"scorer: batch screening {len(candidates)} candidates")

    # Parse JD once
    jd = parse_jd(jd_text)
    logger.info(
        f"scorer: JD parsed — {len(jd.required_skills)} required skills, "
        f"{jd.min_exp_years}+ yrs exp required"
    )

    results = []
    for i, candidate in enumerate(candidates, 1):
        logger.info(f"scorer: processing candidate {i}/{len(candidates)}: {candidate.name}")
        result = screen(candidate, jd_text="", jd_override=jd)
        results.append(result)

    # Sort by total score descending — top candidates first
    results.sort(key=lambda r: r.total_score, reverse=True)
    return results


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _collect_roles(candidate: CandidateProfile) -> list[str]:
    """
    Build a list of the candidate's job titles for role matching.
    Combines current_title + all ExperienceEntry titles.
    """
    roles = []
    if candidate.current_title:
        roles.append(candidate.current_title)
    for exp in candidate.experience:
        if exp.title and exp.title not in roles:
            roles.append(exp.title)
    return roles