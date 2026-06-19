"""
skill_scorer.py — score how well candidate skills match job requirements.

The core challenge: skill names are not standardised.
A JD says "React" — a candidate writes "ReactJS", "React.js", "Frontend development".
Keyword matching (does "React" appear in the skills list?) fails here.

Two matching strategies, applied in order:

    1. Alias matching  — curated dictionary of known equivalences
                         "ReactJS" → "React", "Postgres" → "PostgreSQL"
                         Fast, zero cost, handles 90% of cases

    2. Embedding similarity — converts skill names to vectors and measures
                              cosine similarity. "frontend development" is
                              semantically close to "React" in embedding space.
                              Slower, needs sentence-transformers model (~90MB).
                              Only used when alias matching scores < threshold.

The output of this file is:
    skill_score:    0–100
    matched_skills: list of JD skills the candidate has
    missing_skills: list of JD skills the candidate lacks
    extra_skills:   candidate skills not in the JD (shows breadth)
    skill_details:  per-skill breakdown for the UI
"""

import logging
import re
from dataclasses import dataclass
from .models import SkillMatchDetail

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Skill alias dictionary
# ──────────────────────────────────────────────────────────────────
# Maps any known variant → canonical name
# When comparing, we normalise BOTH the JD skill and candidate skill
# to their canonical form, then compare canonical names.

SKILL_ALIASES: dict[str, str] = {
    "r":          "r",
"tableau":    "tableau",
"power bi":   "power bi",
"powerbi":    "power bi",
"excel":      "excel",
"sql":        "sql",
"mysql":      "sql",
"postgresql": "sql",
"etl":        "etl",
"data warehousing": "data warehousing",
"machine learning": "machine learning",
"ml":         "machine learning",
"statistics": "statistics",
"statistical": "statistics",
    # JavaScript ecosystem
    "reactjs": "react", "react.js": "react",
    "vuejs": "vue", "vue.js": "vue",
    "angularjs": "angular",
    "nodejs": "node.js", "node": "node.js",
    "nextjs": "next.js", "next": "next.js",
    "expressjs": "express", "express.js": "express",
    "js": "javascript", "es6": "javascript", "es2015": "javascript",
    "ts": "typescript",

    # Python
    "python3": "python", "py": "python",
    "django rest framework": "django", "drf": "django",
    "flask-restful": "flask",
    "fastapi": "fastapi",

    # Databases
    "postgres": "postgresql", "psql": "postgresql",
    "mongo": "mongodb",
    "elastic": "elasticsearch", "elk": "elasticsearch",
    "mysql": "mysql", "mariadb": "mysql",

    # ML/AI
    "tf": "tensorflow", "tensorflow2": "tensorflow",
    "pytorch": "pytorch", "torch": "pytorch",
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "hugging face": "huggingface", "hf": "huggingface",
    "langchain": "langchain",
    "openai api": "openai",

    # DevOps/Cloud
    "k8s": "kubernetes", "kube": "kubernetes",
    "gke": "kubernetes",       # Google Kubernetes Engine
    "eks": "kubernetes",       # AWS EKS
    "docker compose": "docker",
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "gcp", "google cloud": "gcp",
    "azure": "azure", "microsoft azure": "azure",
    "ci/cd": "ci/cd", "cicd": "ci/cd",
    "github actions": "ci/cd",
    "jenkins": "jenkins",

    # Data
    "pandas": "pandas",
    "numpy": "numpy",
    "sql": "sql",              # Generic SQL ≈ any SQL dialect
    "mysql": "sql",
    "postgresql": "sql",       # Candidate knowing PostgreSQL satisfies "SQL" requirement

    # Other
    "rest": "rest api", "restful": "rest api", "rest apis": "rest api",
    "graphql": "graphql",
    "microservice": "microservices",
    "oop": "object-oriented programming", "oops": "object-oriented programming",
    "dsa": "data structures",
    "linux": "linux", "unix": "linux",
    "bash": "shell scripting", "shell": "shell scripting",
}

# Semantic groups: skills within a group are considered partial matches
# If JD requires "React" and candidate has "Angular", it's not a match,
# but it shows frontend experience — used for confidence adjustment
SEMANTIC_GROUPS: list[set[str]] = [
    {"react", "angular", "vue", "svelte", "frontend"},
    {"postgresql", "mysql", "sqlite", "oracle", "sql"},
    {"mongodb", "cassandra", "dynamodb", "nosql"},
    {"aws", "gcp", "azure", "cloud"},
    {"docker", "kubernetes", "containerisation"},
    {"tensorflow", "pytorch", "keras", "deep learning"},
    {"python", "java", "go", "javascript", "typescript"},
    {"rest api", "graphql", "grpc", "api"},
    {"machine learning", "deep learning", "ai", "nlp", "data science"},
    {"leadership", "team lead", "mentoring", "management"},
]


# ──────────────────────────────────────────────────────────────────
# Embedding model (lazy-loaded)
# ──────────────────────────────────────────────────────────────────

_embed_model = None

def _get_embeddings():
    """
    Load sentence-transformers model for semantic similarity.
    Model: all-MiniLM-L6-v2 — 90MB, fast, good at short phrase similarity.
    Only loaded once per process, cached in _embed_model.
    Falls back gracefully if not installed.
    """
    global _embed_model
    if _embed_model is not None:
        return _embed_model
    try:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("skill_scorer: loaded sentence-transformers model")
        return _embed_model
    except ImportError:
        logger.info(
            "skill_scorer: sentence-transformers not installed — "
            "using alias matching only. Install with: pip install sentence-transformers"
        )
        return None


# ──────────────────────────────────────────────────────────────────
# Public function
# ──────────────────────────────────────────────────────────────────

@dataclass
class SkillScoreResult:
    score:          float
    matched_skills: list[str]
    missing_skills: list[str]
    extra_skills:   list[str]
    details:        list[SkillMatchDetail]


def score(
    candidate_skills: list[str],
    required_skills:  list[str],
    preferred_skills: list[str],
) -> SkillScoreResult:
    """
    Score skill match between candidate and job requirements.

    Scoring formula:
        required_match_rate  = matched_required / total_required
        preferred_match_rate = matched_preferred / total_preferred

        skill_score = (required_match_rate * 0.75 + preferred_match_rate * 0.25) * 100

    Why this split?
        Missing a required skill is a hard signal against.
        Missing a preferred skill is a soft signal.
        Having ALL required + 0 preferred = 75 points (still a good match).
        Having ALL required + ALL preferred = 100 points.
    """
    if not required_skills and not preferred_skills:
        logger.warning("skill_scorer: no skills in JD — returning 50 (neutral)")
        return SkillScoreResult(50.0, [], [], list(candidate_skills), [])

    # Normalise all skill lists to canonical forms
    cand_normalised  = {_normalise(s): s for s in candidate_skills}
    req_normalised   = [_normalise(s) for s in required_skills]
    pref_normalised  = [_normalise(s) for s in preferred_skills]

    matched:  list[str] = []
    missing:  list[str] = []
    details:  list[SkillMatchDetail] = []

    # Try to match each required skill
    for i, req_norm in enumerate(req_normalised):
        original_req = required_skills[i]
        match_result = _find_match(req_norm, cand_normalised)
        details.append(SkillMatchDetail(
            skill       = original_req,
            matched     = match_result is not None,
            matched_as  = match_result or "",
            similarity  = 1.0 if match_result else 0.0,
            is_required = True,
        ))
        if match_result:
            matched.append(original_req)
        else:
            missing.append(original_req)

    # Try to match each preferred skill
    for i, pref_norm in enumerate(pref_normalised):
        original_pref = preferred_skills[i]
        match_result = _find_match(pref_norm, cand_normalised)
        details.append(SkillMatchDetail(
            skill       = original_pref,
            matched     = match_result is not None,
            matched_as  = match_result or "",
            similarity  = 1.0 if match_result else 0.0,
            is_required = False,
        ))
        if match_result:
            matched.append(original_pref)

    # Extra skills: candidate has but JD didn't ask for
    all_jd_normalised = set(req_normalised + pref_normalised)
    extra = [
        orig for norm, orig in cand_normalised.items()
        if norm not in all_jd_normalised
    ]

    # Compute score
    n_req  = len(req_normalised)
    n_pref = len(pref_normalised)
    n_matched_req  = sum(1 for d in details if d.is_required  and d.matched)
    n_matched_pref = sum(1 for d in details if not d.is_required and d.matched)

    req_rate  = n_matched_req  / n_req  if n_req  > 0 else 1.0
    pref_rate = n_matched_pref / n_pref if n_pref > 0 else 1.0

    raw_score = (req_rate * 0.75 + pref_rate * 0.25) * 100

    # Bonus: extra skills show breadth (+up to 5 points)
    breadth_bonus = min(5.0, len(extra) * 0.5)
    final_score   = min(100.0, raw_score + breadth_bonus)

    logger.debug(
        f"skill_scorer: {n_matched_req}/{n_req} required, "
        f"{n_matched_pref}/{n_pref} preferred → {final_score:.1f}"
    )

    return SkillScoreResult(
        score          = round(final_score, 1),
        matched_skills = matched,
        missing_skills = missing,
        extra_skills   = extra[:20],  # Cap at 20 for UI clarity
        details        = details,
    )


# ──────────────────────────────────────────────────────────────────
# Matching logic
# ──────────────────────────────────────────────────────────────────

def _normalise(skill: str) -> str:
    cleaned = re.sub(r"[^\w\s\+\#\.]", "", skill.lower().strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return SKILL_ALIASES.get(cleaned, cleaned)

def _find_match(jd_skill_norm: str, cand_map: dict[str, str]) -> str | None:
    """
    Try to match a normalised JD skill against the candidate skill map.

    Returns the original candidate skill string if matched, else None.

    Match cascade:
        1. Exact match after normalisation          (highest confidence)
        2. JD skill is contained in candidate skill ("sql" in "postgresql")
        3. Candidate skill is contained in JD skill ("python" in "python 3")
        4. Embedding similarity ≥ 0.75              (semantic match)
    """
    # 1. Exact match
    if jd_skill_norm in cand_map:
        return cand_map[jd_skill_norm]

    # 2. Substring matches (bidirectional)
    for cand_norm, cand_orig in cand_map.items():
        if jd_skill_norm in cand_norm or cand_norm in jd_skill_norm:
            return cand_orig

    # 3. Embedding similarity (optional, only if model loaded)
    embed_match = _embedding_match(jd_skill_norm, cand_map, threshold=0.75)
    if embed_match:
        return embed_match

    return None


def _embedding_match(
    jd_skill: str,
    cand_map: dict[str, str],
    threshold: float = 0.75,
) -> str | None:
    """
    Use sentence embeddings to find semantically similar skills.

    Example: jd_skill="frontend development" vs cand_skill="react"
    These are semantically related — embedding similarity will be high.

    Returns original candidate skill string if similarity ≥ threshold.
    """
    model = _get_embeddings()
    if model is None:
        return None

    if not cand_map:
        return None

    try:
        import numpy as np
        cand_keys = list(cand_map.keys())

        # Encode all skills in one batch (faster than one-by-one)
        all_texts  = [jd_skill] + cand_keys
        embeddings = model.encode(all_texts, normalize_embeddings=True)

        jd_vec    = embeddings[0]
        cand_vecs = embeddings[1:]

        # Cosine similarity — since vectors are normalised, dot product = cosine sim
        similarities = np.dot(cand_vecs, jd_vec)
        best_idx     = int(np.argmax(similarities))
        best_sim     = float(similarities[best_idx])

        if best_sim >= threshold:
            best_norm = cand_keys[best_idx]
            logger.debug(
                f"skill_scorer: embedding match '{jd_skill}' → "
                f"'{best_norm}' (sim={best_sim:.3f})"
            )
            return cand_map[best_norm]

    except Exception as e:
        logger.warning(f"skill_scorer: embedding match failed — {e}")

    return None