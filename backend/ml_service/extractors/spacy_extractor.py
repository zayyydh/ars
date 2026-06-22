"""
spacy_extractor.py — structural entity extraction using spaCy NER.

spaCy's Named Entity Recognition (NER) model reads text and tags spans:
    ORG   → "Google", "TCS", "IIT Bombay"
    DATE  → "January 2021", "2019 – 2022", "Present"
    GPE   → "Bangalore", "India" (Geo-Political Entity = location)
    PERSON→ "John Doe" (backup for name if regex missed it)

We use the small English model: en_core_web_sm
    - Size: ~12 MB
    - Speed: ~10k words/second on CPU
    - Accuracy: good enough for resume text (clean, formal language)

For production you could upgrade to en_core_web_lg (~560 MB) or a
fine-tuned resume-specific model for better accuracy. But sm is the
right starting point — don't over-engineer before you've measured.

What spaCy does that regex can't:
    - "Joined Amazon as SDE-2 in 2020" → ORG=Amazon, DATE=2020
    - "B.Tech from IIT Madras" → ORG=IIT Madras
    - Context-aware: "Python" in "Python experience" ≠ in "Python snake"
      (though skill extraction is weak in the base model — we rely on LLM for that)
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-load spaCy — importing it is slow (~0.5s), so we only do it
# the first time extract() is actually called, not at module import.
# This avoids slowing down the app startup for every other module
# that imports from the extractors package.
_nlp = None

import os  

def _get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    if os.getenv("DISABLE_SPACY", "false").lower() == "true":
        logger.info("spacy_extractor: disabled via env var")
        return None
    try:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
        logger.info("spacy_extractor: loaded en_core_web_sm")
        return _nlp
    except Exception as e:
        logger.warning(f"spacy_extractor: could not load model — {e}")
        return None

# ──────────────────────────────────────────────────────────────────
# Degree level normalisation
# ──────────────────────────────────────────────────────────────────

# Maps raw degree strings (lowercased) to our standard levels.
# Order matters in the dict — more specific patterns first.
DEGREE_PATTERNS = {
    "phd":        ["ph.d", "phd", "doctor of philosophy", "doctorate", "d.phil"],
    "masters":    ["m.tech", "m.e.", "mtech", "m.sc", "msc", "m.s.", "ms ",
                   "master of", "mba", "m.b.a", "pgdm", "post graduate"],
    "bachelors":  ["b.tech", "b.e.", "btech", "b.sc", "bsc", "b.s.", "bs ",
                   "bachelor of", "b.a.", "ba ", "be ", "b.com", "bcom"],
    "diploma":    ["diploma", "polytechnic", "certificate course"],
    "high_school":["12th", "10+2", "hsc", "ssc", "high school", "secondary"],
}

def _normalise_degree(raw: str) -> str:
    """
    Convert a raw degree string to a standard level label.
    Returns empty string if unrecognised.
    """
    lower = raw.lower()
    for level, patterns in DEGREE_PATTERNS.items():
        if any(p in lower for p in patterns):
            return level
    return ""


# ──────────────────────────────────────────────────────────────────
# Duration parsing
# ──────────────────────────────────────────────────────────────────

# Matches year ranges: "2019 – 2022", "Jan 2019 - Dec 2022", "2021 to Present"
_DATE_RANGE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\.?\s*\d{4})"
    r"\s*(?:–|-|to|—)\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\.?\s*\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)",
    re.IGNORECASE,
)

def _estimate_months(start: str, end: str) -> int:
    """
    Estimate duration in months from two date strings.
    This is intentionally approximate — we extract the year and guess month=6
    when the month is missing, giving a mid-year estimate.
    Returns 0 if parsing fails.
    """
    import datetime

    def _parse_year_month(s: str):
        s = s.strip()
        if re.search(r"present|current|now", s, re.IGNORECASE):
            now = datetime.date.today()
            return now.year, now.month
        year_match = re.search(r"\d{4}", s)
        if not year_match:
            return None, None
        year = int(year_match.group())
        month_map = {
            "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
            "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12
        }
        month = 6   # default: mid-year
        for abbr, num in month_map.items():
            if abbr in s.lower():
                month = num
                break
        return year, month

    try:
        sy, sm = _parse_year_month(start)
        ey, em = _parse_year_month(end)
        if sy and ey:
            return max(0, (ey - sy) * 12 + (em - sm))
    except Exception:
        pass
    return 0


# ──────────────────────────────────────────────────────────────────
# Public function
# ──────────────────────────────────────────────────────────────────

def extract(text: str) -> dict:
    """
    Run spaCy NER on the resume text.

    Returns a dict with keys (only when found):
        name, location, organisations, dates, degree_level,
        field_of_study, date_ranges (with estimated duration_months)
    """
    result: dict = {}
    warnings: list[str] = []

   nlp = _get_nlp()
if nlp is None:
    return {"_warnings": ["spaCy disabled"], "date_ranges": [], "total_exp_years": 0}
    # spaCy processes up to 1MB of text. For very long resumes, truncate.
    # Resumes are rarely more than 5000 words — this limit is a safety net.
    MAX_CHARS = 50_000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        warnings.append(f"Text truncated to {MAX_CHARS} chars for spaCy processing")

    doc = nlp(text)

    # ── Named entities ───────────────────────────────────────────────────────
    orgs    = []
    dates   = []
    persons = []
    gpes    = []   # Geo-political entities (cities, countries)

    for ent in doc.ents:
        label = ent.label_
        span  = ent.text.strip()

        if label == "ORG"    and span not in orgs:
            orgs.append(span)
        elif label == "DATE"   and span not in dates:
            dates.append(span)
        elif label == "PERSON" and span not in persons:
            persons.append(span)
        elif label == "GPE"    and span not in gpes:
            gpes.append(span)

    if orgs:
        result["organisations"] = orgs
    if dates:
        result["dates"] = dates
    if persons and not result.get("name"):
        # Use first PERSON entity as name fallback
        result["name"] = persons[0]
    if gpes:
        # First GPE is usually the candidate's location (it appears near the header)
        result["location"] = gpes[0]

    # ── Date ranges (for experience duration) ───────────────────────────────
    date_ranges = []
    for match in _DATE_RANGE.finditer(text):
        start = match.group(1)
        end   = match.group(2)
        months = _estimate_months(start, end)
        date_ranges.append({
            "start": start.strip(),
            "end":   end.strip(),
            "duration_months": months,
        })

    if date_ranges:
        result["date_ranges"]     = date_ranges
        result["total_exp_months"] = sum(r["duration_months"] for r in date_ranges)
        result["total_exp_years"]  = round(result["total_exp_months"] / 12, 1)

    # ── Degree detection ─────────────────────────────────────────────────────
    # Walk sentences — if a sentence contains a degree keyword, extract it
    degree_level = ""
    field_of_study = ""

    for sent in doc.sents:
        sent_text = sent.text.lower()
        level = _normalise_degree(sent_text)
        if level and not degree_level:
            degree_level = level
            # Try to extract field of study from the same sentence
            # Pattern: degree "in" field, or degree "of" field
            field_match = re.search(
                r"(?:in|of)\s+([A-Z][a-zA-Z\s&]+?)(?:\s*,|\s*\(|\s*from|\s*at|\s*–|$)",
                sent.text
            )
            if field_match:
                field_of_study = field_match.group(1).strip()

    if degree_level:
        result["degree_level"]  = degree_level
    if field_of_study:
        result["field_of_study"] = field_of_study

    if warnings:
        result["_warnings"] = warnings

    logger.debug(
        f"spacy_extractor: orgs={len(orgs)} dates={len(dates)} "
        f"ranges={len(date_ranges)} degree={degree_level!r}"
    )
    return result