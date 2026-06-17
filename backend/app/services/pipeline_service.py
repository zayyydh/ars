"""
services/pipeline_service.py — orchestrates the ML pipeline.

This is the bridge between Flask routes and the ML pipeline.
Routes shouldn't know anything about parsers, extractors, or scorers —
they talk to this service, which handles:

    1. Deciding sync vs async: small files run inline, large ones go to Celery
    2. Persisting intermediate state to the DB (parse_status updates)
    3. Caching results in Redis to avoid re-scoring on every GET request
    4. Surfacing clean errors to routes without leaking internal stack traces

Why a service layer between routes and ML?
    Without it, routes become 100-line functions mixing HTTP logic (parse
    request, validate, return JSON) with business logic (call parser, call
    scorer, save to DB). Service layer separates these concerns so each
    piece stays small, testable, and replaceable.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

# Adjust path so the service can import from ml_service
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ml_service"))

from app.extensions import db, redis_client
from app.models.db_models import Job, Resume, ScreeningResult

logger = logging.getLogger(__name__)

# Files larger than this go to Celery async queue instead of running inline
ASYNC_THRESHOLD_BYTES = 500_000   # 500 KB

# Redis key prefix for cached results
CACHE_PREFIX = "screening_result:"


def create_job(jd_text: str) -> Job:
    """
    Persist a new Job to the database.
    JD parsing happens lazily (when the first resume is screened against it),
    not here — avoids paying the LLM cost at submission time.
    """
    job = Job(jd_text=jd_text.strip())
    db.session.add(job)
    db.session.commit()
    logger.info(f"pipeline_service: created job {job.id}")
    return job


def process_resume(
    file_bytes: bytes,
    filename:   str,
    job_id:     str,
) -> ScreeningResult:
    """
    Full pipeline: file → parse → extract → score → persist.

    For files under ASYNC_THRESHOLD_BYTES: runs synchronously and returns
    a completed ScreeningResult.

    For larger files: enqueues a Celery task and returns a ScreeningResult
    with status="pending" and a task_id for the client to poll.
    """
    job = Job.query.get(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    # 1. Create Resume record in DB (status=pending)
    resume = Resume(
        filename     = filename,
        file_type    = "unknown",   # Will be set after parsing
        parse_status = "pending",
    )
    db.session.add(resume)
    db.session.flush()  # Get the ID without full commit

    # 2. Create ScreeningResult record (status=pending)
    result = ScreeningResult(
        resume_id = resume.id,
        job_id    = job_id,
        status    = "pending",
    )
    db.session.add(result)
    db.session.commit()

    # 3. Decide: sync or async
    if len(file_bytes) > ASYNC_THRESHOLD_BYTES:
        return _dispatch_async(file_bytes, filename, resume.id, job_id, result.id)
    else:
        return _run_sync(file_bytes, filename, resume, job, result)


def _run_sync(
    file_bytes: bytes,
    filename:   str,
    resume:     Resume,
    job:        Job,
    result:     ScreeningResult,
) -> ScreeningResult:
    """Run the full pipeline inline and return a completed ScreeningResult."""
    try:
        # Import here (not at top) so the service module loads fast
        # even if ML dependencies aren't installed yet
        from parsers import extract as parse_resume
        from extractors import extract as extract_entities
        from scorer import screen

        # ── Layer 1 + 2: parse ───────────────────────────────────────────────
        resume.parse_status = "parsing"
        db.session.commit()

        parsed = parse_resume(file_bytes, filename=filename)
        resume.file_type    = parsed.file_type.value
        resume.raw_text     = parsed.raw_text
        resume.parse_status = "parsed" if parsed.is_usable else "failed"
        resume.warnings     = parsed.warnings
        db.session.commit()

        if not parsed.is_usable:
            result.status        = "failed"
            result.error_message = f"Could not parse resume: {parsed.warnings}"
            db.session.commit()
            return result

        # ── Layer 3: extract entities ────────────────────────────────────────
        result.status = "processing"
        db.session.commit()

        profile      = extract_entities(parsed)
        resume.profile = profile.to_dict()
        db.session.commit()

        # ── Layer 4: score ───────────────────────────────────────────────────
        screening = screen(profile, job.jd_text)

        # ── Persist result ───────────────────────────────────────────────────
        result.total_score      = screening.total_score
        result.skill_score      = screening.skill_score
        result.experience_score = screening.experience_score
        result.education_score  = screening.education_score
        result.verdict          = screening.verdict.value
        result.result_data      = screening.to_dict()
        result.status           = "completed"
        result.completed_at     = datetime.now(timezone.utc)
        db.session.commit()

        # ── Cache in Redis ───────────────────────────────────────────────────
        _cache_result(result)

        logger.info(
            f"pipeline_service: completed result {result.id} — "
            f"{screening.total_score:.1f} [{screening.verdict.value}]"
        )
        return result

    except Exception as e:
        logger.error(f"pipeline_service._run_sync: {e}", exc_info=True)
        result.status        = "failed"
        result.error_message = str(e)
        db.session.commit()
        return result


def _dispatch_async(
    file_bytes: bytes,
    filename:   str,
    resume_id:  str,
    job_id:     str,
    result_id:  str,
) -> ScreeningResult:
    """Enqueue a Celery task for large files. Returns immediately."""
    from app.tasks.screening_task import run_screening

    task = run_screening.delay(
        file_bytes = file_bytes,
        filename   = filename,
        resume_id  = resume_id,
        job_id     = job_id,
        result_id  = result_id,
    )

    result = ScreeningResult.query.get(result_id)
    result.task_id = task.id
    db.session.commit()

    logger.info(
        f"pipeline_service: dispatched async task {task.id} "
        f"for resume {resume_id}"
    )
    return result


def get_result(result_id: str) -> ScreeningResult | None:
    """
    Fetch a ScreeningResult by ID.
    Checks Redis cache first, falls back to DB.
    """
    # Try cache
    if redis_client:
        cached = redis_client.get(f"{CACHE_PREFIX}{result_id}")
        if cached:
            logger.debug(f"pipeline_service: cache hit for result {result_id}")
            # Return DB object (cache is just for fast existence check)

    return ScreeningResult.query.get(result_id)


def get_results_for_job(job_id: str) -> list[ScreeningResult]:
    """Return all screening results for a job, sorted by score descending."""
    return (
        ScreeningResult.query
        .filter_by(job_id=job_id, status="completed")
        .order_by(ScreeningResult.total_score.desc())
        .all()
    )


def _cache_result(result: ScreeningResult) -> None:
    """Store a lightweight cache entry in Redis after completing a result."""
    if not redis_client:
        return
    try:
        from flask import current_app
        ttl = current_app.config.get("RESULT_CACHE_TTL", 1800)
        redis_client.setex(
            f"{CACHE_PREFIX}{result.id}",
            ttl,
            json.dumps({"status": result.status, "score": result.total_score}),
        )
    except Exception as e:
        logger.warning(f"pipeline_service: Redis cache write failed — {e}")