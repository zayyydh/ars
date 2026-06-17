"""
test_extractors.py — verify Layer 3 works correctly.

Run modes:
    python test_extractors.py                  ← synthetic text, no files or API needed
    python test_extractors.py --regex          ← regex extractor only
    python test_extractors.py --spacy          ← spaCy extractor only (needs en_core_web_sm)
    python test_extractors.py --llm            ← LLM extractor (needs OPENAI_API_KEY)
    python test_extractors.py resume.pdf       ← full pipeline on a real resume
"""

import sys
import json
import textwrap

# Sample resume text for testing without a real file
SAMPLE_RESUME = """
Zayd Khan
zayd.khan@gmail.com | +91-9876543210 | linkedin.com/in/zaydkhan | github.com/zaydkhan
Bangalore, India

SUMMARY
Full-stack software engineer with 4+ years of experience building scalable web applications
and offline-first systems. Passionate about privacy-first, open-source software.

EXPERIENCE

Software Engineer — TechCorp India (Jan 2021 – Present)
- Built REST APIs using Python, Flask, and PostgreSQL serving 100k+ daily users
- Led migration from monolithic to microservices architecture using Docker and Kubernetes
- Implemented real-time features using WebSockets and Redis pub/sub
- Mentored 3 junior developers; conducted code reviews and technical interviews

Junior Developer — StartupXYZ (Jun 2019 – Dec 2020)
- Developed React frontend components with TypeScript
- Integrated third-party APIs (Stripe, Twilio, SendGrid)
- Wrote unit tests achieving 85% code coverage (Jest, pytest)

SKILLS
Languages:  Python, JavaScript, TypeScript, Go, SQL
Frameworks: Flask, FastAPI, React, Node.js
Databases:  PostgreSQL, MongoDB, Redis
DevOps:     Docker, Kubernetes, GitHub Actions, AWS (EC2, S3, RDS)
Other:      spaCy, LangChain, Git, Linux

EDUCATION
B.Tech Computer Science — IIT Bombay (2015 – 2019) | CGPA: 8.7 / 10

PROJECTS
BlueChat — Offline Bluetooth P2P encrypted messenger (React Native, TweetNaCl)
Offline STT — Desktop speech-to-text app (Python, faster-whisper, Flask, PyWebView)
"""


def print_section(title: str, data) -> None:
    width = 62
    print(f"\n{'─' * width}")
    print(f"  {title}")
    print(f"{'─' * width}")
    if isinstance(data, dict):
        for k, v in data.items():
            if k.startswith("_"):
                continue
            val_str = json.dumps(v, indent=2) if isinstance(v, (list, dict)) else str(v)
            # Wrap long values
            if len(val_str) > 60:
                print(f"  {k}:")
                for line in val_str.splitlines():
                    print(f"      {line}")
            else:
                print(f"  {k:20s}: {val_str}")
    else:
        print(f"  {data}")


def test_regex():
    print("\n=== REGEX EXTRACTOR ===")
    sys.path.insert(0, "../../")
    from extractors.regex_extractor import extract
    result = extract(SAMPLE_RESUME)
    print_section("Regex results", result)
    print(f"\n  ✓ Found: {[k for k in result if not k.startswith('_')]}")


def test_spacy():
    print("\n=== SPACY EXTRACTOR ===")
    sys.path.insert(0, "../../")
    from extractors.spacy_extractor import extract
    result = extract(SAMPLE_RESUME)
    print_section("spaCy results", result)
    warnings = result.get("_warnings", [])
    if warnings:
        print(f"\n  ⚠ Warnings: {warnings}")


def test_llm():
    print("\n=== LLM EXTRACTOR ===")
    import os
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        print("  ⚠  No API key set. Export OPENAI_API_KEY=sk-... and retry.")
        print("  Skipping LLM test.")
        return
    sys.path.insert(0, "../../")
    from extractors.llm_extractor import extract, estimate_cost_usd
    est_cost = estimate_cost_usd(SAMPLE_RESUME)
    print(f"  Estimated cost: ${est_cost:.6f} USD")
    result = extract(SAMPLE_RESUME)
    print_section("LLM result (skills)", {
        "technical_skills": result.get("technical_skills"),
        "languages":        result.get("languages"),
        "tools":            result.get("tools"),
        "total_exp_years":  result.get("total_exp_years"),
        "current_title":    result.get("current_title"),
        "highest_degree":   result.get("highest_degree"),
    })


def test_full_pipeline(resume_path: str = None):
    print("\n=== FULL LAYER 2 → LAYER 3 PIPELINE ===")
    sys.path.insert(0, "../../")
    from parsers import extract as parse_resume
    from extractors import extract as extract_entities

    if resume_path:
        print(f"  Parsing: {resume_path}")
        parsed = parse_resume(resume_path)
    else:
        # Build a synthetic ParsedResume from sample text
        from parsers.models import ParsedResume, FileType, ParseStatus
        parsed = ParsedResume(
            raw_text   = SAMPLE_RESUME,
            file_type  = FileType.PDF_NATIVE,
            status     = ParseStatus.SUCCESS,
            filename   = "sample_resume.txt",
            page_count = 1,
        )

    print(f"  Parse status  : {parsed.status.value}")
    print(f"  Char count    : {parsed.char_count}")
    print(f"  Is usable     : {parsed.is_usable}")

    if not parsed.is_usable:
        print("  ✗ Resume not usable — stopping")
        return

    profile = extract_entities(parsed)

    print(f"\n  ── CandidateProfile ──")
    print(f"  Name           : {profile.name}")
    print(f"  Email          : {profile.email}")
    print(f"  Phone          : {profile.phone}")
    print(f"  LinkedIn       : {profile.linkedin}")
    print(f"  GitHub         : {profile.github}")
    print(f"  Location       : {profile.location}")
    print(f"  Total exp yrs  : {profile.total_exp_years}")
    print(f"  Current title  : {profile.current_title}")
    print(f"  Highest degree : {profile.highest_degree}")
    print(f"  Primary field  : {profile.primary_field}")
    print(f"  Confidence     : {profile.extraction_confidence}")
    print(f"\n  Skills ({len(profile.skills)}):")
    for s in profile.skills:
        print(f"    • {s}")
    print(f"\n  Experience ({len(profile.experience)} roles):")
    for e in profile.experience:
        print(f"    {e.title} @ {e.company}  [{e.start_date} – {e.end_date}]  {e.duration_months}mo")
    print(f"\n  Education ({len(profile.education)} entries):")
    for ed in profile.education:
        print(f"    {ed.degree} — {ed.institution}  ({ed.graduation_year})")

    if profile.extraction_warnings:
        print(f"\n  ⚠ Warnings:")
        for w in profile.extraction_warnings:
            print(f"    - {w}")

    print(f"\n  Summary: {profile.summary_line()}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        # Default: run everything except LLM (which needs an API key)
        test_regex()
        test_spacy()
        test_full_pipeline()

    elif "--regex" in args:
        test_regex()

    elif "--spacy" in args:
        test_spacy()

    elif "--llm" in args:
        test_llm()

    else:
        # Assume it's a file path
        test_full_pipeline(args[0])