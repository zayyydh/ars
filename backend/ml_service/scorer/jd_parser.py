"""
jd_parser.py — parse a raw job description into structured JobRequirements.

Same two-strategy approach as Layer 3:
    1. LLM   — primary, handles all the ambiguous phrasing JDs use
    2. Regex  — fallback for experience years when LLM is unavailable

Why JD parsing is harder than resume parsing:
    Resumes follow conventions. JDs are written by different people in
    different styles and often contradict themselves:
        "3+ years preferred, 2 years minimum"
        "React experience a plus" (is this required or preferred?)
        "Strong Python skills" (what does 'strong' mean in years?)

The LLM handles this ambiguity well. It understands that:
    - "proficiency in", "strong X skills", "experience with X" → required
    - "nice to have", "a plus", "familiarity" → preferred
    - "3+ years" → min_exp_years=3
"""
import os
import re
import logging
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from .models import JobRequirements

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Pydantic schema for LLM structured output
# ──────────────────────────────────────────────────────────────────

class PydanticJobRequirements(BaseModel):
    job_title:             str       = Field(default="",  description="Job title")
    company:               str       = Field(default="",  description="Company name if mentioned")
    location:              str       = Field(default="",  description="Job location")
    required_skills:       list[str] = Field(default_factory=list,
        description="Skills explicitly required: 'must have', 'required', 'proficiency in', 'experience with'")
    preferred_skills:      list[str] = Field(default_factory=list,
        description="Skills that are nice-to-have: 'preferred', 'a plus', 'familiarity', 'exposure to'")
    min_exp_years:         float     = Field(default=0.0,
        description="Minimum years of experience required. '3+ years' → 3.0")
    max_exp_years:         float     = Field(default=99.0,
        description="Maximum years. Usually 99 unless explicitly capped.")
    required_roles:        list[str] = Field(default_factory=list,
        description="Job titles or roles expected: 'Software Engineer', 'Data Analyst'")
    required_degree_level: str       = Field(default="",
        description="Minimum degree: bachelors / masters / phd / diploma or '' if not specified")
    preferred_fields:      list[str] = Field(default_factory=list,
        description="Preferred fields of study: 'Computer Science', 'Information Technology'")


JD_SYSTEM_PROMPT = """You are an expert job description analyser.
Extract structured requirements from the job description text.

Rules:
- Separate required skills (must-have) from preferred skills (nice-to-have)
- If unclear, put in required_skills
- Normalise skill names: ReactJS → React, Postgres → PostgreSQL
- For experience: "3+ years" → min=3.0, max=99.0. "2-5 years" → min=2.0, max=5.0
- Only extract degree level if explicitly stated
- Do not invent requirements not mentioned in the JD
"""


# ──────────────────────────────────────────────────────────────────
# Regex fallback patterns
# ──────────────────────────────────────────────────────────────────

# "3+ years", "minimum 2 years", "at least 5 years of experience"
_EXP_PATTERN = re.compile(
    r"(?:minimum\s+|at\s+least\s+|[\(\s])?(\d+(?:\.\d+)?)\s*\+?\s*"
    r"(?:years?|yrs?)(?:\s+of)?\s*(?:experience|exp)",
    re.IGNORECASE,
)

# Detect degree requirements
_DEGREE_PATTERNS = {
    "phd":       [r"ph\.?d", r"doctorate", r"doctor of"],
    "masters":   [r"m\.tech", r"m\.s\.", r"master", r"mba"],
    "bachelors": [r"b\.tech", r"b\.e\.", r"bachelor", r"b\.s\.", r"undergraduate"],
    "diploma":   [r"diploma"],
}

# Common skill keywords to extract when LLM is unavailable
_COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "react", "angular", "vue", "node.js", "django", "flask", "fastapi", "spring",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform",
    "machine learning", "deep learning", "tensorflow", "pytorch",
    "pandas", "numpy", "scikit-learn", "langchain", "spacy",
    "git", "linux", "rest api", "graphql", "microservices",
]


# ──────────────────────────────────────────────────────────────────
# LLM client (shared lazy loader)
# ──────────────────────────────────────────────────────────────────

_llm_client = None

def _get_llm():
    global _llm_client
    if _llm_client is not None:
        return _llm_client
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        base = ChatOpenAI(
            model="gpt-4o-mini", temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        base = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
    _llm_client = base.with_structured_output(PydanticJobRequirements)
    return _llm_client


# ──────────────────────────────────────────────────────────────────
# Public function
# ──────────────────────────────────────────────────────────────────

def parse(jd_text: str) -> JobRequirements:
    """
    Parse a job description string into a JobRequirements dataclass.
    Tries LLM first, falls back to regex if LLM is unavailable.
    """
    jd_text = jd_text.strip()
    if not jd_text:
        logger.warning("jd_parser: empty job description")
        return JobRequirements()

    # Try LLM first
    llm_result = _parse_with_llm(jd_text)
    if llm_result:
        logger.info(
            f"jd_parser: LLM extracted {len(llm_result.required_skills)} required "
            f"+ {len(llm_result.preferred_skills)} preferred skills"
        )
        return llm_result

    # Fallback to regex
    logger.info("jd_parser: LLM unavailable — falling back to regex extraction")
    return _parse_with_regex(jd_text)


def _parse_with_llm(jd_text: str) -> JobRequirements | None:
    """Use LangChain structured output to parse the JD."""
    try:
        from langchain_core.prompts import ChatPromptTemplate
        llm = _get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", JD_SYSTEM_PROMPT),
            ("human", "Parse this job description:\n\n<jd>{jd_text}</jd>"),
        ])
        messages = prompt.format_messages(jd_text=jd_text[:8000])
        p: PydanticJobRequirements = llm.invoke(messages)

        return JobRequirements(
            raw_jd_text           = jd_text,
            job_title             = p.job_title,
            company               = p.company,
            location              = p.location,
            required_skills       = p.required_skills,
            preferred_skills      = p.preferred_skills,
            min_exp_years         = p.min_exp_years,
            max_exp_years         = p.max_exp_years,
            required_roles        = p.required_roles,
            required_degree_level = p.required_degree_level,
            preferred_fields      = p.preferred_fields,
        )
    except Exception as e:
        logger.warning(f"jd_parser: LLM parse failed — {e}")
        return None


def _parse_with_regex(jd_text: str) -> JobRequirements:
    """
    Regex-based JD parsing. Less accurate than LLM but needs no API key.
    Used as fallback or for development/testing without API access.
    """
    text_lower = jd_text.lower()

    # Extract experience years
    exp_matches = _EXP_PATTERN.findall(jd_text)
    min_exp = float(min(exp_matches)) if exp_matches else 0.0

    # Extract degree level
    degree = ""
    for level, patterns in _DEGREE_PATTERNS.items():
        if any(re.search(p, text_lower) for p in patterns):
            degree = level
            break

    # Extract skills by scanning for known keywords
    found_skills = [s for s in _COMMON_SKILLS if s in text_lower]

    # Very rough required/preferred split:
    # Skills appearing near "required/must" → required; near "preferred/plus" → preferred
    required, preferred = [], []
    for skill in found_skills:
        # Find the skill's position in text and look at surrounding context
        idx = text_lower.find(skill)
        context = text_lower[max(0, idx-80):idx+80]
        if any(w in context for w in ["required", "must", "mandatory", "essential"]):
            required.append(skill)
        elif any(w in context for w in ["preferred", "plus", "nice", "familiarity"]):
            preferred.append(skill)
        else:
            required.append(skill)  # Default to required when ambiguous

    return JobRequirements(
        raw_jd_text           = jd_text,
        required_skills       = required,
        preferred_skills      = preferred,
        min_exp_years         = min_exp,
        required_degree_level = degree,
    )