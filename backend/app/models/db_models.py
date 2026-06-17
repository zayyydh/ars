"""
models/db_models.py — SQLAlchemy ORM models (database tables).

Three tables:
    Job           — a job posting with its description and requirements
    Resume        — an uploaded resume file (text extracted, profile stored)
    ScreeningResult — the score for one (Resume, Job) pair

Why store the extracted profile and score as JSON columns?
    The ML output (CandidateProfile, ScreeningResult) are rich nested
    structures. Normalising every field into separate columns would mean
    dozens of columns and complex JOINs for every read.

    PostgreSQL's JSONB column type stores JSON but also lets you query
    INTO the JSON (e.g. WHERE profile->>'email' = 'x'). Best of both worlds:
    the flexibility of a document store with the reliability of a relational DB.
"""

import uuid
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)

def _uuid():
    return str(uuid.uuid4())


class Job(db.Model):
    """
    A job posting. Created when the user submits a JD.
    One Job can have many ScreeningResults (one per resume screened).
    """
    __tablename__ = "jobs"

    id          = db.Column(db.String(36), primary_key=True, default=_uuid)
    title       = db.Column(db.String(256), nullable=False, default="")
    company     = db.Column(db.String(256), nullable=False, default="")
    location    = db.Column(db.String(256), nullable=False, default="")
    jd_text     = db.Column(db.Text,        nullable=False)  # Raw JD text
    requirements = db.Column(db.JSON,       nullable=True)   # Parsed JobRequirements as JSON
    created_at  = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at  = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationship: one job → many screening results
    results     = db.relationship("ScreeningResult", back_populates="job",
                                   cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "title":        self.title,
            "company":      self.company,
            "location":     self.location,
            "jd_text":      self.jd_text,
            "requirements": self.requirements,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
            "result_count": len(self.results),
        }


class Resume(db.Model):
    """
    An uploaded resume. Stores both the raw text and the extracted profile.
    One Resume can be screened against many Jobs.
    """
    __tablename__ = "resumes"

    id           = db.Column(db.String(36), primary_key=True, default=_uuid)
    filename     = db.Column(db.String(512), nullable=False)
    file_type    = db.Column(db.String(32),  nullable=False)   # "pdf_native", "docx", etc.
    raw_text     = db.Column(db.Text,        nullable=True)    # Extracted text from Layer 2
    profile      = db.Column(db.JSON,        nullable=True)    # CandidateProfile as JSON
    parse_status = db.Column(db.String(32),  nullable=False, default="pending")
    # "pending" → "parsing" → "parsed" → "failed"
    warnings     = db.Column(db.JSON,        nullable=True, default=list)
    created_at   = db.Column(db.DateTime(timezone=True), default=_now)

    # Relationship
    results      = db.relationship("ScreeningResult", back_populates="resume",
                                    cascade="all, delete-orphan")

    def to_dict(self, include_text: bool = False) -> dict:
        d = {
            "id":           self.id,
            "filename":     self.filename,
            "file_type":    self.file_type,
            "parse_status": self.parse_status,
            "profile":      self.profile,
            "warnings":     self.warnings,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
        }
        if include_text:
            d["raw_text"] = self.raw_text
        return d


class ScreeningResult(db.Model):
    """
    The scoring result for one (resume, job) pair.
    This is what the frontend displays in the results view.
    """
    __tablename__ = "screening_results"

    id               = db.Column(db.String(36), primary_key=True, default=_uuid)
    resume_id        = db.Column(db.String(36), db.ForeignKey("resumes.id"), nullable=False)
    job_id           = db.Column(db.String(36), db.ForeignKey("jobs.id"),    nullable=False)

    # Scores
    total_score      = db.Column(db.Float, nullable=True)
    skill_score      = db.Column(db.Float, nullable=True)
    experience_score = db.Column(db.Float, nullable=True)
    education_score  = db.Column(db.Float, nullable=True)
    verdict          = db.Column(db.String(32), nullable=True)  # "SHORTLIST", "REVIEW", "REJECT"

    # Full result JSON — contains matched_skills, missing_skills, skill_details, etc.
    result_data      = db.Column(db.JSON, nullable=True)

    # Task tracking
    task_id          = db.Column(db.String(64), nullable=True)   # Celery task ID
    status           = db.Column(db.String(32), nullable=False, default="pending")
    # "pending" → "processing" → "completed" → "failed"
    error_message    = db.Column(db.Text, nullable=True)

    created_at       = db.Column(db.DateTime(timezone=True), default=_now)
    completed_at     = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    resume           = db.relationship("Resume", back_populates="results")
    job              = db.relationship("Job",    back_populates="results")

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "resume_id":        self.resume_id,
            "job_id":           self.job_id,
            "total_score":      self.total_score,
            "skill_score":      self.skill_score,
            "experience_score": self.experience_score,
            "education_score":  self.education_score,
            "verdict":          self.verdict,
            "result_data":      self.result_data,
            "status":           self.status,
            "error_message":    self.error_message,
            "created_at":       self.created_at.isoformat()    if self.created_at    else None,
            "completed_at":     self.completed_at.isoformat()  if self.completed_at  else None,
        }