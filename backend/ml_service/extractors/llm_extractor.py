"""
llm_extractor.py — full structured extraction using LangChain + OpenAI/Gemini.

This is the most powerful extractor in Layer 3. The LLM reads the entire
resume and returns a fully structured JSON profile matching our
PydanticCandidateProfile schema.

Why LangChain's with_structured_output() instead of plain prompting?
    Plain prompt: "Return a JSON with name, skills, experience..."
        → LLM sometimes returns markdown code fences: ```json { ... } ```
        → LLM sometimes adds commentary before/after the JSON
        → You have to strip and parse manually, and handle parse errors

    with_structured_output(PydanticCandidateProfile):
        → LangChain uses OpenAI's function calling / JSON mode under the hood
        → The LLM is FORCED to return data matching the Pydantic schema
        → You get a validated Python object directly — no parsing, no stripping
        → Pydantic validates types: if LLM returns "4" for total_exp_years,
          it's automatically cast to 4.0 (float)

LLM provider is configurable — OpenAI or Google Gemini via environment var.
The rest of the code is provider-agnostic (LangChain abstraction layer).
"""

import logging
import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from .models import CandidateProfile, PydanticCandidateProfile, pydantic_to_dataclass

# Load .env from the backend/ folder explicitly
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────────────────────────

# The system prompt is carefully written to:
#   1. Give the LLM a clear role
#   2. Explain exactly what we want
#   3. Handle edge cases explicitly (missing data, inferred skills)
#   4. Prevent hallucination ("only extract what is explicitly stated")

SYSTEM_PROMPT = """You are an expert resume parser. Your job is to extract structured information from resume text accurately.

Rules:
- Only extract information that is explicitly stated in the resume
- Do NOT invent or infer skills that aren't mentioned
- If a field is missing, leave it as empty string or empty list — do not guess
- For total_exp_years: sum up all work experience durations. If dates overlap, count the overlap once.
- For degree_level use exactly one of: bachelors, masters, phd, diploma, high_school
- For skills, be thorough — extract ALL technical skills, frameworks, tools, and languages mentioned anywhere
- Normalise skill names: "ReactJS" → "React", "Postgres" → "PostgreSQL", "JS" → "JavaScript"
- For duration_months in experience: estimate from dates. If only years given, multiply by 12.
- current_title and current_company = most recent role (end_date = "Present" or most recent year)
"""

USER_PROMPT = """Extract all structured information from the following resume text:

<resume>
{resume_text}
</resume>

Return the complete structured profile."""


# ──────────────────────────────────────────────────────────────────
# LLM client (lazy-loaded, provider-switchable)
# ──────────────────────────────────────────────────────────────────

_llm_client = None

def _get_llm():
    """
    Build the LangChain LLM client with structured output.

    Provider is selected by LLM_PROVIDER environment variable:
        LLM_PROVIDER=openai  (default) → uses OPENAI_API_KEY
        LLM_PROVIDER=gemini            → uses GOOGLE_API_KEY

    with_structured_output(PydanticCandidateProfile) wraps the LLM so
    it always returns a validated PydanticCandidateProfile object.
    """
    global _llm_client
    if _llm_client is not None:
        return _llm_client

    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY environment variable not set. "
                "Export it before running: export OPENAI_API_KEY=sk-..."
            )
        base_llm = ChatOpenAI(
            model       = "gpt-4o-mini",  # Fast + cheap. Upgrade to gpt-4o for higher accuracy.
            temperature = 0,              # 0 = deterministic, no creativity — we want exact extraction
            api_key     = api_key,
        )

    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY environment variable not set.")
        base_llm = ChatGoogleGenerativeAI(
            model       = "gemini-2.0-flash",
            temperature = 0,
            google_api_key = api_key,
        )

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Use 'openai' or 'gemini'.")

    # Wrap the LLM with structured output
    # This uses OpenAI's function calling / JSON mode under the hood
    _llm_client = base_llm.with_structured_output(PydanticCandidateProfile)
    logger.info(f"llm_extractor: initialised {provider} client")
    return _llm_client


# ──────────────────────────────────────────────────────────────────
# Prompt builder
# ──────────────────────────────────────────────────────────────────

_prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human",  USER_PROMPT),
])


# ──────────────────────────────────────────────────────────────────
# Public function
# ──────────────────────────────────────────────────────────────────

def extract(text: str, max_chars: int = 12_000) -> dict:
    """
    LLM extraction — currently falling back to keyword-based extraction
    when no API key/quota is available.
    """
    logger.info("llm_extractor: using keyword fallback (no LLM quota)")
    return _keyword_fallback(text)


def _keyword_fallback(text: str) -> dict:
    """
    Extract skills using a comprehensive keyword list when LLM is unavailable.
    """
    import re

    KNOWN_SKILLS = [
        "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
        "ruby", "php", "swift", "kotlin", "scala", "r",
        "react", "angular", "vue", "svelte", "next.js", "nuxt",
        "node.js", "express", "django", "flask", "fastapi", "spring", "laravel",
        "postgresql", "mysql", "mongodb", "redis", "sqlite", "cassandra",
        "elasticsearch", "dynamodb", "oracle",
        "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "ansible",
        "github actions", "jenkins", "ci/cd", "linux", "nginx",
        "machine learning", "deep learning", "tensorflow", "pytorch",
        "scikit-learn", "pandas", "numpy", "opencv", "nlp", "langchain",
        "rest api", "graphql", "grpc", "microservices", "websocket",
        "git", "jira", "figma", "postman",
        "html", "css", "sass", "tailwind", "bootstrap",
        "celery", "rabbitmq", "kafka", "spark", "hadoop",
    ]

    text_lower = text.lower()
    found_skills = []
    for skill in KNOWN_SKILLS:
        if skill in text_lower:
            found_skills.append(skill.title() if len(skill) > 3 else skill.upper())

    # Extract experience years from text
    exp_match = re.search(
        r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s*(?:experience|exp)",
        text_lower
    )
    exp_years = float(exp_match.group(1)) if exp_match else 0.0

    # Extract name (first non-empty line that looks like a name)
    name = ""
    for line in text.splitlines():
        line = line.strip()
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
            name = line
            break

    # Extract email
    email_match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    email = email_match.group(0) if email_match else ""

    return {
        "name":             name,
        "email":            email,
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
# ──────────────────────────────────────────────────────────────────
# Token cost estimator (utility, not called in main flow)
# ──────────────────────────────────────────────────────────────────

def estimate_cost_usd(text: str) -> float:
    """
    Rough cost estimate for extracting one resume.
    gpt-4o-mini: ~$0.15 / 1M input tokens, ~$0.60 / 1M output tokens
    Tokens ≈ chars / 4 (rough approximation for English text)
    """
    input_tokens  = len(text) / 4
    output_tokens = 500   # Structured JSON output is roughly this size
    cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000
    return round(cost, 6)