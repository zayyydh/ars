import sys
import os
import logging
from datetime import datetime, timezone

_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.extensions import celery, db
from app.models.db_models import Resume, ScreeningResult, Job

logger = logging.getLogger(__name__)


@celery.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="app.tasks.screening_task.run_screening",
)
def run_screening(self, file_bytes, filename, resume_id, job_id, result_id):
    from ml_service.parsers import extract as parse_resume
    from ml_service.extractors import extract as extract_entities
    from ml_service.scorer import screen

    result = db.session.get(ScreeningResult, result_id)
    resume = db.session.get(Resume, resume_id)
    job    = db.session.get(Job, job_id)

    if not all([result, resume, job]):
        return {"status": "failed", "error": "DB records not found"}

    try:
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
            result.error_message = str(parsed.warnings)
            db.session.commit()
            return {"status": "failed"}

        result.status = "processing"
        db.session.commit()

        profile        = extract_entities(parsed)
        resume.profile = profile.to_dict()
        db.session.commit()

        screening = screen(profile, job.jd_text)

        result.total_score      = screening.total_score
        result.skill_score      = screening.skill_score
        result.experience_score = screening.experience_score
        result.education_score  = screening.education_score
        result.verdict          = screening.verdict.value
        result.result_data      = screening.to_dict()
        result.status           = "completed"
        result.completed_at     = datetime.now(timezone.utc)
        db.session.commit()

        return {"status": "completed", "score": screening.total_score}

    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
        if isinstance(e, (ConnectionError, TimeoutError, OSError)):
            raise self.retry(exc=e)
        result.status        = "failed"
        result.error_message = str(e)
        db.session.commit()
        return {"status": "failed", "error": str(e)}