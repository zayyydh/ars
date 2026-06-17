"""
routes/jobs.py — job posting endpoints.

Blueprint: /api/jobs

POST /api/jobs
    Body: { "jd_text": "We are looking for..." }
    Creates a new job record. Returns job ID.
    The JD is stored raw — parsing happens lazily at screening time.

GET /api/jobs/<job_id>
    Returns the job record with its parsed requirements.

GET /api/jobs/<job_id>/results
    Returns all screening results for this job, ranked by score.
"""

from flask import Blueprint, request, jsonify, current_app
from app.services import pipeline_service
from app.models.db_models import Job

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.post("/jobs")
def create_job():
    """
    Submit a job description. Returns a job_id for use in resume uploads.

    Request body (JSON):
        {
            "jd_text": "Full job description text...",
            "title":   "Software Engineer" (optional, auto-extracted from JD)
        }
    """
    data = request.get_json(silent=True)

    if not data or not data.get("jd_text", "").strip():
        return jsonify({"error": "jd_text is required"}), 400

    jd_text = data["jd_text"].strip()
    if len(jd_text) < 50:
        return jsonify({"error": "Job description too short (minimum 50 characters)"}), 400

    if len(jd_text) > 20_000:
        return jsonify({"error": "Job description too long (maximum 20,000 characters)"}), 400

    try:
        job = pipeline_service.create_job(jd_text)
        return jsonify({
            "job_id":  job.id,
            "message": "Job created successfully",
            "job":     job.to_dict(),
        }), 201

    except Exception as e:
        current_app.logger.error(f"routes/jobs: create_job failed — {e}")
        return jsonify({"error": "Failed to create job"}), 500


@jobs_bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    """Return a job record by ID."""
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.to_dict()), 200


@jobs_bp.get("/jobs/<job_id>/results")
def get_job_results(job_id: str):
    """
    Return all screening results for a job, sorted by score.
    Used by the frontend to render the ranked candidate list.
    """
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    results = pipeline_service.get_results_for_job(job_id)
    return jsonify({
        "job_id":  job_id,
        "count":   len(results),
        "results": [r.to_dict() for r in results],
    }), 200