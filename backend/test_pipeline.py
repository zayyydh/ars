import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from ml_service.parsers import extract as parse
from ml_service.extractors import extract as extract_entities
from ml_service.scorer import screen

# Change this to your actual resume path
RESUME_PATH = r'C:\Users\MSI33\Downloads\backend-developer2 - Template 18.pdf'

print("Step 1: Parsing...")
parsed = parse(RESUME_PATH)
print(f"  Status: {parsed.status.value}")
print(f"  Chars:  {parsed.char_count}")

print("\nStep 2: Extracting entities...")
profile = extract_entities(parsed)
print(f"  Name:       {profile.name}")
print(f"  Skills:     {profile.skills[:8]}")
print(f"  Exp years:  {profile.total_exp_years}")
print(f"  Confidence: {profile.extraction_confidence}")

print("\nStep 3: Scoring...")
jd = """Software Engineer - Backend
3+ years Python experience required.
Skills: Python, FastAPI, PostgreSQL, Docker, Redis.
B.Tech in Computer Science."""

result = screen(profile, jd)
print(f"  Score:   {result.total_score}")
print(f"  Verdict: {result.verdict.value}")
print(f"  Matched: {result.matched_skills}")
print(f"  Missing: {result.missing_skills}")