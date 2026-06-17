"""
regex_extractor.py — deterministic extraction of contact fields.

Regex is the right tool for fields that always have a predictable shape:
    - Emails       always match  user@domain.tld
    - Phone numbers always match  +91-XXXXXXXXXX or (XXX) XXX-XXXX etc.
    - LinkedIn URLs always contain linkedin.com/in/
    - GitHub URLs  always contain github.com/

We use COMPILED patterns (re.compile at module level) — not re.search()
called fresh every time. Compiled patterns are ~10x faster because the
regex engine only parses the pattern string once at import time.

Why regex wins over LLM for contacts:
    - Zero latency (no API call)
    - Zero cost
    - Never hallucinates an email address
    - 100% reproducible — same input always gives same output

Why regex LOSES for skills/experience:
    - "3 years of Python experience" ≠ a fixed pattern
    - Skill names are unbounded (new frameworks appear constantly)
    - Context matters: "Python" in "Python snake" ≠ "Python" the language
"""

import re
import logging
from .models import CandidateProfile

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Compiled regex patterns
# ──────────────────────────────────────────────────────────────────

# Email: standard RFC-5321 simplified pattern
# Captures: local-part @ domain . tld
# Won't match: emails with IP literals or unusual TLDs over 6 chars
_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,6}\b"
)

# Phone: handles most international and Indian formats
# Examples matched:
#   +91-9876543210   +1 (555) 123-4567   9876543210   (022) 2345-6789
_PHONE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?"          # optional country code: +91, +1
    r"(?:\(?\d{2,4}\)?[\s\-.]?)?"       # optional area code: (022), 022
    r"\d{3,5}[\s\-.]?\d{3,5}"           # core number: 98765-43210
    r"(?!\d)"                            # not followed by more digits
)

# LinkedIn: profile URLs in various forms
# Matches: linkedin.com/in/username, www.linkedin.com/in/username, /in/username
_LINKEDIN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9\-_%]+)",
    re.IGNORECASE
)

# GitHub: profile URLs
# Matches: github.com/username (but NOT github.com/username/repo — that's a repo)
_GITHUB = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9\-]+)(?:/[^\s]*)?",
    re.IGNORECASE
)

# Location: "City, State" or "City, Country" patterns
# Examples: "Bangalore, India"  "San Francisco, CA"  "London, UK"
# This is heuristic — locations don't have a fixed format
_LOCATION = re.compile(
    r"\b([A-Z][a-zA-Z\s]+),\s*([A-Z]{2}|[A-Z][a-zA-Z]+)\b"
)

# Name heuristic: first non-empty line of resume is usually the name
# We validate it looks like a name: 2-4 words, each capitalised, no numbers
_NAME_LINE = re.compile(
    r"^([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})$"
)

# Total experience: "X years of experience", "X+ years", "X yrs"
# Used as a fallback if the LLM doesn't extract total_exp_years
_TOTAL_EXP = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s*(?:experience|exp)",
    re.IGNORECASE
)


# ──────────────────────────────────────────────────────────────────
# Public function
# ──────────────────────────────────────────────────────────────────

def extract(text: str) -> dict:
    """
    Run all regex patterns against the resume text.

    Returns a plain dict (not CandidateProfile) — this is intentional.
    The orchestrator (entity_extractor.py) merges results from all three
    extractors, so each returns a dict that's easy to merge.

    Keys returned:
        name, email, phone, linkedin, github, location, total_exp_years
        (only keys where we found something — missing keys = not found)
    """
    result = {}
    warnings = []

    # ── Email ───────────────────────────────────────────────────────────────
    emails = _EMAIL.findall(text)
    if emails:
        # Take the first one — resumes usually have one primary email
        result["email"] = emails[0].lower()
        if len(emails) > 1:
            warnings.append(
                f"Multiple emails found: {emails} — using first one"
            )
    else:
        warnings.append("No email address found")

    # ── Phone ───────────────────────────────────────────────────────────────
    # Phone regex is intentionally broad — filter out false positives by
    # checking that the match has at least 7 digits total
    raw_phones = _PHONE.findall(text)
    valid_phones = [
        p.strip() for p in raw_phones
        if len(re.sub(r"\D", "", p)) >= 7   # count only digit characters
    ]
    if valid_phones:
        result["phone"] = valid_phones[0]

    # ── LinkedIn ────────────────────────────────────────────────────────────
    linkedin_match = _LINKEDIN.search(text)
    if linkedin_match:
        username = linkedin_match.group(1)
        result["linkedin"] = f"linkedin.com/in/{username}"

    # ── GitHub ──────────────────────────────────────────────────────────────
    github_match = _GITHUB.search(text)
    if github_match:
        username = github_match.group(1)
        # Exclude common false positives (GitHub org pages, docs, etc.)
        if username.lower() not in ("features", "pricing", "blog", "about", "login"):
            result["github"] = f"github.com/{username}"

    # ── Name (heuristic) ────────────────────────────────────────────────────
    name = _extract_name(text)
    if name:
        result["name"] = name

    # ── Location ────────────────────────────────────────────────────────────
    location_match = _LOCATION.search(text)
    if location_match:
        result["location"] = location_match.group(0)

    # ── Total experience (fallback) ──────────────────────────────────────────
    exp_match = _TOTAL_EXP.search(text)
    if exp_match:
        result["total_exp_years"] = float(exp_match.group(1))

    if warnings:
        result["_warnings"] = warnings

    logger.debug(f"regex_extractor: found {list(result.keys())}")
    return result


# ──────────────────────────────────────────────────────────────────
# Name extraction helper
# ──────────────────────────────────────────────────────────────────

def _extract_name(text: str) -> str:
    """
    Extract the candidate's name using a positional heuristic.

    Resumes almost universally put the name as the very first content line.
    We check the first 5 non-empty lines and pick the first one that:
        - Contains 2–4 words
        - Each word is Title Case (first letter capitalised)
        - Contains no digits (rules out "John Doe | +91-9876543210")
        - Is not an obvious header ("Curriculum Vitae", "Resume", "Profile")

    This is intentionally conservative — we'd rather return empty string
    than confidently return the wrong name. The LLM extractor will fill
    this in if regex misses it.
    """
    EXCLUDE = {
        "curriculum vitae", "resume", "cv", "profile",
        "personal information", "contact", "about me",
    }

    lines = text.splitlines()
    checked = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        checked += 1
        if checked > 8:   # Don't look past the first 8 lines
            break

        # Must be 2-4 words, no digits
        words = stripped.split()
        if not (2 <= len(words) <= 4):
            continue
        if any(char.isdigit() for char in stripped):
            continue
        if stripped.lower() in EXCLUDE:
            continue

        # Each word should start with a capital letter
        if all(w[0].isupper() for w in words if w):
            return stripped

    return ""