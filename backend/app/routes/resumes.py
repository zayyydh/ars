"""
routes/resumes.py — resume upload and retrieval endpoints.

Blueprint: /api/resumes

POST /api/resumes/upload
    Accepts a multipart form upload.
    Validates file type and size.
    Triggers the screening pipeline (sync or async).
    Returns the screening result ID for polling.

GET /api/resumes/<resume_id>
    Returns the parsed resume record with extracted profile.
"""

import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.services import pipeline_service
from app.models.db_models import Resume

resumes_bp = Blueprint("resumes", __name__)


def _allowed_file(filename: str) -> bool:
    """Check file extension is in the allowed set."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", {"pdf", "docx"})


@resumes_bp.post("/resumes/upload")
def upload_resume():
    """
    Upload a resume and screen it against a job.

    Request: multipart/form-data
        file:    (binary) The resume file (.pdf or .docx)
        job_id:  (string) The ID of the job to screen against

    Response 202:
        {
            "result_id": "uuid",
            "resume_id": "uuid",
            "status":    "pending" | "completed",
            "result":    { ... }   ← only present when status="completed" (sync path)
        }

    Why 202 (Accepted) instead of 200 (OK)?
        HTTP 202 means "I received your request and I'm working on it."
        For async jobs, there's no result yet — 202 is semantically correct.
        For sync jobs (small files), we still return 202 for consistency
        and include the result in the body.
    """
    # ── Validate job_id ──────────────────────────────────────────────────────
    job_id = request.form.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    # ── Validate file presence ───────────────────────────────────────────────
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # ── Validate file type ───────────────────────────────────────────────────
    filename = secure_filename(file.filename)
    if not _allowed_file(filename):
        return jsonify({
            "error": f"Unsupported file type. Allowed: PDF, DOCX"
        }), 415

    # ── Read file bytes ──────────────────────────────────────────────────────
    # Read into memory — we pass bytes to the pipeline, not a file path.
    # This avoids race conditions from saving to disk first.
    file_bytes = file.read()

    # Double-check size (Werkzeug also checks MAX_CONTENT_LENGTH but let's be explicit)
    max_size = current_app.config.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)
    if len(file_bytes) > max_size:
        return jsonify({
            "error": f"File too large. Maximum size: {max_size // (1024*1024)} MB"
        }), 413

    if len(file_bytes) < 100:
        return jsonify({"error": "File appears to be empty"}), 400

    # ── Run pipeline ─────────────────────────────────────────────────────────
    try:
        result = pipeline_service.process_resume(
            file_bytes = file_bytes,
            filename   = filename,
            job_id     = job_id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"routes/resumes: upload failed — {e}")
        return jsonify({"error": "Failed to process resume"}), 500

    # ── Build response ───────────────────────────────────────────────────────
    response_body = {
        "result_id": result.id,
        "resume_id": result.resume_id,
        "status":    result.status,
    }

    # If sync path completed inline, include the full result in the response
    # so the client doesn't have to poll
    if result.status == "completed":
        response_body["result"] = result.to_dict()
    elif result.status == "pending":
        response_body["task_id"]    = result.task_id
        response_body["poll_url"]   = f"/api/results/{result.id}"
        response_body["message"]    = (
            "Resume is being processed. Poll poll_url for the result."
        )

    return jsonify(response_body), 202


@resumes_bp.get("/resumes/<resume_id>")
def get_resume(resume_id: str):
    """Return the parsed resume and extracted profile."""
    resume = Resume.query.get(resume_id)
    if not resume:
        return jsonify({"error": "Resume not found"}), 404

    include_text = request.args.get("include_text", "false").lower() == "true"
    return jsonify(resume.to_dict(include_text=include_text)), 200