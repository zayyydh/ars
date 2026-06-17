"""
test_scorer.py — test the Layer 4 scoring engine end-to-end.

Run modes:
    python test_scorer.py              ← hardcoded sample candidate + JD
    python test_scorer.py --batch      ← test batch screening with 3 candidates
    python test_scorer.py resume.pdf   ← score a real resume against the sample JD
"""

import sys
sys.path.insert(0, "../../")

from backend.ml_service.extractors.models import (
    CandidateProfile,
    ExperienceEntry,
    EducationEntry,
)

from backend.ml_service.scorer import (
    screen,
    batch_screen,
    Verdict,
)

# ──────────────────────────────────────────────────────────────────
# Sample data
# ──────────────────────────────────────────────────────────────────

SAMPLE_JD = """
Software Engineer — Backend (Python)
TechCorp | Bangalore, India

We are looking for an experienced Backend Software Engineer to join our
growing platform team.

Requirements:
- 3+ years of professional software engineering experience
- Strong proficiency in Python (Django or FastAPI)
- Experience with PostgreSQL and Redis
- Familiarity with Docker and Kubernetes
- Understanding of REST API design principles
- B.Tech / B.E. in Computer Science or related field

Nice to have:
- Experience with AWS or GCP
- Knowledge of Celery for async task processing
- Contributions to open-source projects
- Experience with CI/CD pipelines (GitHub Actions, Jenkins)
"""

# Strong match candidate
CANDIDATE_STRONG = CandidateProfile(
    name             = "Zayd Khan",
    email            = "zayd@example.com",
    total_exp_years  = 4.5,
    current_title    = "Senior Software Engineer",
    current_company  = "TechCorp",
    highest_degree   = "bachelors",
    primary_field    = "Computer Science",
    skills           = [
        "Python", "FastAPI", "Django", "PostgreSQL", "Redis",
        "Docker", "Kubernetes", "AWS", "Celery", "GitHub Actions",
        "REST API", "React", "Git", "Linux",
    ],
    technical_skills = ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"],
    languages        = ["Python", "JavaScript", "Go"],
    experience       = [
        ExperienceEntry(
            company="TechCorp", title="Senior Software Engineer",
            start_date="2022", end_date="Present", duration_months=24,
        ),
        ExperienceEntry(
            company="StartupXYZ", title="Software Engineer",
            start_date="2020", end_date="2022", duration_months=24,
        ),
    ],
    education        = [
        EducationEntry(
            institution="IIT Bombay", degree="B.Tech Computer Science",
            degree_level="bachelors", field_of_study="Computer Science",
            graduation_year="2020",
        )
    ],
    extraction_confidence = 0.95,
)

# Weak match candidate
CANDIDATE_WEAK = CandidateProfile(
    name             = "Alex Smith",
    email            = "alex@example.com",
    total_exp_years  = 1.0,
    current_title    = "Junior Developer",
    highest_degree   = "diploma",
    primary_field    = "Information Technology",
    skills           = ["JavaScript", "React", "HTML", "CSS", "MySQL"],
    technical_skills = ["JavaScript", "React", "MySQL"],
    languages        = ["JavaScript"],
    experience       = [
        ExperienceEntry(
            company="Freelance", title="Junior Developer",
            start_date="2023", end_date="Present", duration_months=12,
        ),
    ],
    education        = [
        EducationEntry(
            institution="Local College",
            degree="Diploma in IT",
            degree_level="diploma",
            field_of_study="Information Technology",
        )
    ],
    extraction_confidence = 0.80,
)

# Mid match candidate
CANDIDATE_MID = CandidateProfile(
    name             = "Priya Sharma",
    email            = "priya@example.com",
    total_exp_years  = 3.0,
    current_title    = "Software Engineer",
    highest_degree   = "masters",
    primary_field    = "Data Science",
    skills           = [
        "Python", "Flask", "MySQL", "MongoDB", "Docker",
        "REST API", "Git", "Machine Learning",
    ],
    technical_skills = ["Python", "Flask", "MySQL", "Docker"],
    languages        = ["Python", "Java"],
    experience       = [
        ExperienceEntry(
            company="DataCo", title="Software Engineer",
            start_date="2021", end_date="Present", duration_months=36,
        ),
    ],
    education        = [
        EducationEntry(
            institution="NIT Trichy",
            degree="M.Tech Data Science",
            degree_level="masters",
            field_of_study="Data Science",
            graduation_year="2021",
        )
    ],
    extraction_confidence = 0.88,
)


# ──────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────

VERDICT_EMOJI = {
    Verdict.SHORTLIST: "✅",
    Verdict.REVIEW:    "⚠️ ",
    Verdict.REJECT:    "❌",
}

def print_result(result) -> None:
    emoji = VERDICT_EMOJI.get(result.verdict, "?")
    print(result.summary())
    print(f"\n  {emoji} VERDICT: {result.verdict.value}")
    print(f"\n  Matched skills  : {result.matched_skills}")
    print(f"  Missing skills  : {result.missing_skills}")
    if result.extra_skills:
        print(f"  Extra skills    : {result.extra_skills[:5]}")
    if result.warnings:
        print(f"\n  ⚠ Warnings:")
        for w in result.warnings:
            print(f"    - {w}")
    print()


def test_single():
    print("\n" + "=" * 62)
    print("  TEST: Single candidate screening")
    print("=" * 62)

    print("\n── Strong match candidate ──")
    result = screen(CANDIDATE_STRONG, SAMPLE_JD)
    print_result(result)

    print("── Weak match candidate ──")
    result = screen(CANDIDATE_WEAK, SAMPLE_JD)
    print_result(result)

    print("── Mid match candidate ──")
    result = screen(CANDIDATE_MID, SAMPLE_JD)
    print_result(result)


def test_batch():
    print("\n" + "=" * 62)
    print("  TEST: Batch screening (ranked)")
    print("=" * 62)

    candidates = [CANDIDATE_WEAK, CANDIDATE_MID, CANDIDATE_STRONG]
    results    = batch_screen(candidates, SAMPLE_JD)

    print(f"\nRanked results for: {results[0].job_title or 'Role'}\n")
    for rank, r in enumerate(results, 1):
        emoji = VERDICT_EMOJI.get(r.verdict, "?")
        print(
            f"  #{rank}  {emoji} {r.candidate_name:<20} "
            f"Score: {r.total_score:5.1f}  "
            f"[Skill:{r.skill_score:.0f} Exp:{r.experience_score:.0f} Edu:{r.education_score:.0f}]  "
            f"{r.verdict.value}"
        )


def test_with_resume(path: str):
    print(f"\n{'='*62}")
    print(f"  TEST: Real resume — {path}")
    print("=" * 62)

    from parsers import extract as parse_resume
    from extractors import extract as extract_entities

    parsed  = parse_resume(path)
    if not parsed.is_usable:
        print(f"  ✗ Resume not usable: {parsed.warnings}")
        return

    profile = extract_entities(parsed)
    print(f"\n  Candidate: {profile.summary_line()}")

    result  = screen(profile, SAMPLE_JD)
    print_result(result)


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--batch" in args:
        test_batch()
    elif args:
        test_with_resume(args[0])
    else:
        test_single()
        test_batch()