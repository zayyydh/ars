"""
llm_extractor.py — skill extraction using keyword matching.
LLM bypassed (no API quota). Uses comprehensive keyword list instead.
"""

import re
import logging
import os

logger = logging.getLogger(__name__)

KNOWN_SKILLS = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "ruby", "php", "swift", "kotlin", "scala",
    "react", "angular", "vue", "svelte", "next.js",
    "node.js", "express", "django", "flask", "fastapi", "spring", "laravel",
    "postgresql", "mysql", "mongodb", "redis", "sqlite", "cassandra",
    "elasticsearch", "dynamodb",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "ansible",
    "github actions", "jenkins", "ci/cd", "linux", "nginx",
    "machine learning", "deep learning", "tensorflow", "pytorch",
    "scikit-learn", "pandas", "numpy", "opencv", "nlp", "langchain",
    "rest api", "graphql", "grpc", "microservices", "websocket",
    "git", "jira", "figma", "postman",
    "html", "css", "sass", "tailwind", "bootstrap",
    "celery", "rabbitmq", "kafka", "spark",
    "data structures", "algorithms", "object-oriented programming",
    "agile", "scrum", "devops",
]


def extract(text: str, max_chars: int = 12_000) -> dict:
    """Extract skills using keyword matching (no LLM required)."""
    logger.info("llm_extractor: using keyword fallback")
    return _keyword_fallback(text[:max_chars])


def _keyword_fallback(text: str) -> dict:
    text_lower = text.lower()

    # Find skills
    found_skills = []
    for skill in KNOWN_SKILLS:
        if skill in text_lower:
            # Capitalise nicely
            if skill in ("aws", "gcp", "nlp", "css", "html", "rest api",
                         "ci/cd", "php"):
                found_skills.append(skill.upper())
            elif len(skill) <= 3:
                found_skills.append(skill.upper())
            else:
                found_skills.append(skill.title())

    # Experience years
    exp_match = re.search(
        r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s*(?:experience|exp)",
        text_lower,
    )
    exp_years = float(exp_match.group(1)) if exp_match else 0.0

    # Name — first short capitalised line
    name = ""
    for line in text.splitlines():
        line = line.strip()
        words = line.split()
        if (2 <= len(words) <= 4
                and all(w[0].isupper() for w in words if w)
                and not any(c.isdigit() for c in line)):
            name = line
            break

    # Email
    email_match = re.search(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        text,
    )
    email = email_match.group(0) if email_match else ""

    # Phone
    phone_match = re.search(
        r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{3,5}\)?[\s\-.]?\d{3,5}[\s\-.]?\d{3,5}",
        text,
    )
    phone = phone_match.group(0).strip() if phone_match else ""

    return {
        "name":             name,
        "email":            email,
        "phone":            phone,
        "technical_skills": found_skills,
        "soft_skills":      [],
        "tools":            [],
        "languages":        [],
        "experience":       [],
        "education":        [],
        "total_exp_years":  exp_years,
        "current_title":    "",
        "current_company":  "",
        "highest_degree":   "",
        "primary_field":    "",
        "summary":          "",
        "_source":          "keyword_fallback",
    }


def estimate_cost_usd(text: str) -> float:
    return 0.0