"""
diagnose.py — run this from the backend/ folder to check everything.
Usage: python diagnose.py
"""

import sys
import os

print("=" * 60)
print("RESUME SCREENER — BACKEND DIAGNOSTIC")
print("=" * 60)

# ── 1. Python version ────────────────────────────────────────────
print(f"\n[1] Python version: {sys.version}")
print(f"    Executable:      {sys.executable}")

# ── 2. Working directory ─────────────────────────────────────────
cwd = os.getcwd()
print(f"\n[2] Working directory: {cwd}")

backend_dir = os.path.dirname(os.path.abspath(__file__))
print(f"    Script location:   {backend_dir}")

if cwd != backend_dir:
    print("    ⚠  WARNING: you are NOT running this from the backend/ folder")
    print(f"    ⚠  Run:  cd \"{backend_dir}\"  then  python diagnose.py")
else:
    print("    ✓  Running from correct directory")

# ── 3. Add backend to path ───────────────────────────────────────
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
print(f"\n[3] sys.path[0]: {sys.path[0]}")

# ── 4. Check app package ─────────────────────────────────────────
print("\n[4] Checking app package structure:")
checks = [
    "app",
    "app/__init__.py",
    "app/extensions.py",
    "app/config.py",
    "app/models",
    "app/models/__init__.py",
    "app/models/db_models.py",
    "app/routes",
    "app/routes/__init__.py",
    "app/routes/jobs.py",
    "app/routes/resumes.py",
    "app/routes/results.py",
    "app/services/__init__.py",
    "app/services/pipeline_service.py",
    "app/tasks/__init__.py",
    "app/tasks/screening_task.py",
]
all_ok = True
for f in checks:
    full = os.path.join(backend_dir, f)
    exists = os.path.isdir(full) if f.endswith(("/", "app", "models", "routes", "services", "tasks")) or "." not in f.split("/")[-1] else os.path.isfile(full)
    # simpler check
    exists = os.path.exists(full)
    icon = "✓" if exists else "✕ MISSING"
    if not exists:
        all_ok = False
    print(f"    {icon}  {f}")

if all_ok:
    print("    → All files present")

# ── 5. Check ml_service package ──────────────────────────────────
print("\n[5] Checking ml_service package:")
ml_checks = [
    "ml_service/__init__.py",
    "ml_service/parsers/__init__.py",
    "ml_service/parsers/models.py",
    "ml_service/parsers/format_detector.py",
    "ml_service/parsers/pdf_parser.py",
    "ml_service/parsers/docx_parser.py",
    "ml_service/parsers/ocr_parser.py",
    "ml_service/parsers/text_extractor.py",
    "ml_service/extractors/__init__.py",
    "ml_service/extractors/models.py",
    "ml_service/extractors/regex_extractor.py",
    "ml_service/extractors/spacy_extractor.py",
    "ml_service/extractors/llm_extractor.py",
    "ml_service/extractors/entity_extractor.py",
    "ml_service/scorer/__init__.py",
    "ml_service/scorer/models.py",
    "ml_service/scorer/jd_parser.py",
    "ml_service/scorer/skill_scorer.py",
    "ml_service/scorer/experience_scorer.py",
    "ml_service/scorer/education_scorer.py",
    "ml_service/scorer/scorer.py",
]
ml_ok = True
for f in ml_checks:
    exists = os.path.exists(os.path.join(backend_dir, f))
    icon = "✓" if exists else "✕ MISSING"
    if not exists:
        ml_ok = False
    print(f"    {icon}  {f}")

# ── 6. Check pip packages ────────────────────────────────────────
print("\n[6] Checking installed packages:")
packages = [
    ("flask",             "flask"),
    ("flask_sqlalchemy",  "flask-sqlalchemy"),
    ("flask_cors",        "flask-cors"),
    ("celery",            "celery"),
    ("redis",             "redis"),
    ("sqlalchemy",        "sqlalchemy"),
    ("psycopg2",          "psycopg2-binary"),
    ("dotenv",            "python-dotenv"),
    ("pymupdf",           "pymupdf"),
    ("pdfplumber",        "pdfplumber"),
    ("docx",              "python-docx"),
    ("PIL",               "Pillow"),
    ("pytesseract",       "pytesseract"),
    ("spacy",             "spacy"),
    ("langchain",         "langchain"),
    ("langchain_openai",  "langchain-openai"),
    ("pydantic",          "pydantic"),
]
missing_pkgs = []
for import_name, pip_name in packages:
    try:
        __import__(import_name)
        print(f"    ✓  {pip_name}")
    except ImportError:
        print(f"    ✕  {pip_name}  ← NOT INSTALLED")
        missing_pkgs.append(pip_name)

# ── 7. Try importing app modules ─────────────────────────────────
print("\n[7] Trying to import app modules:")

def try_import(module, label):
    try:
        __import__(module)
        print(f"    ✓  {label}")
        return True
    except Exception as e:
        print(f"    ✕  {label}")
        print(f"       Error: {e}")
        return False

try_import("app.config",             "app.config")
try_import("app.extensions",         "app.extensions")
try_import("app.models.db_models",   "app.models.db_models")
try_import("app.routes.jobs",        "app.routes.jobs")
try_import("app.routes.resumes",     "app.routes.resumes")
try_import("app.routes.results",     "app.routes.results")
try_import("app.services.pipeline_service", "app.services.pipeline_service")

# ── 8. Try importing ml_service ──────────────────────────────────
print("\n[8] Trying to import ml_service modules:")
try_import("ml_service.parsers.models",        "parsers.models")
try_import("ml_service.parsers.text_extractor","parsers.text_extractor")
try_import("ml_service.extractors.models",     "extractors.models")
try_import("ml_service.scorer.models",         "scorer.models")

# ── 9. Try creating the Flask app ────────────────────────────────
print("\n[9] Trying to create Flask app:")
try:
    from app import create_app
    application = create_app()
    print("    ✓  Flask app created successfully")
    print(f"    ✓  Routes registered: {[str(r) for r in application.url_map.iter_rules()][:5]}...")
except Exception as e:
    print(f"    ✕  Flask app creation failed")
    print(f"       Error: {e}")
    import traceback
    traceback.print_exc()

# ── 10. Check .env file ──────────────────────────────────────────
print("\n[10] Checking .env file:")
env_path = os.path.join(backend_dir, ".env")
if os.path.exists(env_path):
    print(f"    ✓  .env found at {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key = line.split("=")[0]
                # Don't print actual values of secrets
                if "KEY" in key or "PASSWORD" in key or "SECRET" in key:
                    print(f"    ✓  {key}=***")
                else:
                    print(f"    ✓  {line}")
else:
    print(f"    ✕  .env NOT FOUND at {env_path}")
    print("       Create backend/.env with your DB URL, Redis URL, and API key")

# ── Summary ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
if missing_pkgs:
    print(f"\n  ✕ Missing packages — run:")
    print(f"    pip install {' '.join(missing_pkgs)}")
else:
    print("\n  ✓ All packages installed")

if not ml_ok:
    print("\n  ✕ Some ml_service files missing")
    print("    Make sure ml_service/__init__.py exists (can be empty)")
else:
    print("  ✓ ml_service structure complete")

print("\n  Run this script with your venv active:")
print("  env\\Scripts\\activate  (Windows)")
print("  python diagnose.py")
print()