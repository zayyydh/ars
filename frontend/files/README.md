# Resume Screening AI

Production-grade AI resume screener. Parses resumes, extracts structured candidate
profiles, and scores them against job descriptions using semantic skill matching,
experience analysis, and education comparison.

## Stack

| Layer      | Technology                              |
|------------|-----------------------------------------|
| Frontend   | React + TypeScript + Vite               |
| API        | Flask + Gunicorn                        |
| Queue      | Celery + Redis                          |
| Parsing    | PyMuPDF + pdfplumber + python-docx      |
| NLP        | spaCy + Transformers                    |
| LLM        | LangChain + OpenAI / Gemini             |
| Database   | PostgreSQL (SQLAlchemy ORM)             |
| Cache      | Redis                                   |
| Deploy     | Docker + docker-compose                 |

## Pipeline

```
Resume file (PDF/DOCX/scanned)
    ↓
[Layer 1+2]  Format detection + text extraction  →  ParsedResume
    ↓
[Layer 3]    Regex + spaCy + LLM extraction      →  CandidateProfile
    ↓
[Layer 4]    Skill + experience + education score →  ScreeningResult
    ↓
[Flask API]  HTTP endpoints + Celery async        →  JSON response
    ↓
[React UI]   Upload → Processing → Results
```

## Quick start

```bash
# 1. Set your API key
export OPENAI_API_KEY=sk-...

# 2. Start everything with Docker
docker-compose up --build

# 3. Open the app
open http://localhost:3000
```

## Development (without Docker)

```bash
# Terminal 1 — Flask API
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
export DATABASE_URL=postgresql://postgres:password@localhost:5432/resume_screener
export REDIS_URL=redis://localhost:6379/0
export OPENAI_API_KEY=sk-...
flask --app wsgi run --debug

# Terminal 2 — Celery worker
cd backend
celery -A wsgi:celery worker --loglevel=info

# Terminal 3 — React frontend
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## Test each layer independently

```bash
# Layer 1+2: parsing
cd backend/ml_service/parsers
python test_parsers.py resume.pdf

# Layer 3: entity extraction (no API key needed for regex + spaCy)
cd backend/ml_service/extractors
python test_extractors.py

# Layer 4: scoring (no API key needed for hardcoded sample)
cd backend/ml_service/scorer
python test_scorer.py
python test_scorer.py --batch
```

## API endpoints

| Method | Path                        | Description                        |
|--------|-----------------------------|------------------------------------|
| POST   | /api/jobs                   | Create a job with JD text          |
| GET    | /api/jobs/:id               | Get a job record                   |
| GET    | /api/jobs/:id/results       | All results for a job, ranked      |
| POST   | /api/resumes/upload         | Upload resume + trigger screening  |
| GET    | /api/resumes/:id            | Get parsed resume + profile        |
| GET    | /api/results/:id            | Poll for screening result          |
| GET    | /api/results?job_id=...     | List results with optional filters |
| GET    | /health                     | Liveness probe                     |

## Scoring weights (configurable)

| Dimension  | Default weight | What it measures                  |
|------------|----------------|-----------------------------------|
| Skills     | 50%            | Semantic skill overlap with JD    |
| Experience | 30%            | Years + seniority alignment       |
| Education  | 20%            | Degree level + field of study     |

Verdicts: **SHORTLIST** ≥ 70 · **REVIEW** ≥ 45 · **REJECT** < 45

## Project structure

```
resume-screener/
├── backend/
│   ├── ml_service/
│   │   ├── parsers/       ← Layer 1+2: format detection + extraction
│   │   ├── extractors/    ← Layer 3: regex + spaCy + LLM
│   │   └── scorer/        ← Layer 4: skill + exp + edu scoring
│   ├── app/
│   │   ├── routes/        ← Flask blueprints (jobs, resumes, results)
│   │   ├── models/        ← SQLAlchemy ORM
│   │   ├── services/      ← Pipeline orchestration
│   │   └── tasks/         ← Celery async tasks
│   ├── wsgi.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx        ← All three screens
│   │   ├── api/client.ts  ← API calls
│   │   └── types/         ← TypeScript contracts
│   ├── vite.config.ts
│   └── Dockerfile
└── docker-compose.yml
```
