"""
jd_parser.py — parse a raw job description into structured JobRequirements.
Uses regex-based extraction (LLM bypassed — no quota available).
"""

import re
import logging
from .models import JobRequirements

logger = logging.getLogger(__name__)

_EXP_PATTERN = re.compile(
    r"(?:minimum\s+|at\s+least\s+)?(\d+(?:\.\d+)?)\s*\+?\s*"
    r"(?:years?|yrs?)(?:\s+of)?\s*(?:experience|exp)",
    re.IGNORECASE,
)

_DEGREE_PATTERNS = {
    "phd":       [r"ph\.?d", r"doctorate", r"doctor of"],
    "masters":   [r"m\.tech", r"m\.s\.", r"master", r"mba"],
    "bachelors": [r"b\.tech", r"b\.e\.", r"bachelor", r"b\.s\.", r"undergraduate"],
    "diploma":   [r"diploma"],
}

_COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "react", "angular", "vue", "node.js", "django", "flask", "fastapi", "spring",
    "postgresql", "mysql", "mongodb", "redis", "sqlite", "elasticsearch",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn",
    "pandas", "numpy", "langchain", "spacy",
    "rest api", "graphql", "microservices", "git", "linux", "ci/cd",
    "celery", "rabbitmq", "kafka", "html", "css",
]


def parse(jd_text: str) -> JobRequirements:
    """Parse a job description using regex only. No LLM required."""
    jd_text = jd_text.strip()
    if not jd_text:
        logger.warning("jd_parser: empty job description")
        return JobRequirements()
    logger.info("jd_parser: using regex parser")
    return _parse_with_regex(jd_text)


def _parse_with_regex(jd_text: str) -> JobRequirements:
    text_lower = jd_text.lower()

    exp_matches = _EXP_PATTERN.findall(jd_text)
    min_exp = float(min(exp_matches)) if exp_matches else 0.0

    degree = ""
    for level, patterns in _DEGREE_PATTERNS.items():
        if any(re.search(p, text_lower) for p in patterns):
            degree = level
            break

    required, preferred = [], []
    for skill in _COMMON_SKILLS:
        if skill not in text_lower:
            continue
        idx = text_lower.find(skill)
        context = text_lower[max(0, idx - 120):idx + 120]
        if any(w in context for w in ["preferred", "plus", "nice", "familiarity", "bonus"]):
            preferred.append(skill)
        else:
            required.append(skill)

    job_title = ""
    for line in jd_text.splitlines():
        line = line.strip()
        if 3 < len(line) < 80 and not line.endswith(":"):
            job_title = line
            break

    logger.info(
        f"jd_parser: {len(required)} required + {len(preferred)} preferred skills, "
        f"min_exp={min_exp}, degree={degree!r}"
    )

    return JobRequirements(
        raw_jd_text=jd_text,
        job_title=job_title,
        required_skills=required,
        preferred_skills=preferred,
        min_exp_years=min_exp,
        required_degree_level=degree,
    )