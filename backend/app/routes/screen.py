"""
routes/screen.py — single endpoint that matches the frontend's call.

POST /api/screen
    FormData fields:
        resume           — the resume file (PDF/DOCX)
        job_description  — the job description text

    Returns JSON matching the frontend's expected shape:
        overall_score, skills_score, experience_score, education_score,
        verdict, strengths, gaps, suggestions
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
screen_bp = Blueprint("screen", __name__)


def _allowed_file(filename: str) -> bool:
    allowed = {"pdf", "docx", "doc"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


@screen_bp.post("/screen")
def screen_resume():
    # ── Validate inputs ──────────────────────────────────────────────────────
    if "resume" not in request.files:
        return jsonify({"error": "No resume file uploaded"}), 400

    file = request.files["resume"]
    jd_text = request.form.get("job_description", "").strip()

    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Use PDF or DOCX"}), 415

    if not jd_text or len(jd_text) < 20:
        return jsonify({"error": "Job description is too short"}), 400

    filename = secure_filename(file.filename)
    file_bytes = file.read()

    if len(file_bytes) < 100:
        return jsonify({"error": "File appears to be empty"}), 400

    # ── Run pipeline ─────────────────────────────────────────────────────────
    try:
        import sys, os
        _BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if _BACKEND not in sys.path:
            sys.path.insert(0, _BACKEND)

        from ml_service.parsers import extract as parse_resume
        from ml_service.extractors import extract as extract_entities
        from ml_service.scorer import screen

        # Layer 1+2: parse
        parsed = parse_resume(file_bytes, filename=filename)
        if not parsed.is_usable:
            return jsonify({
                "error": f"Could not parse resume: {parsed.warnings}"
            }), 422

        # Layer 3: extract
        profile = extract_entities(parsed)

        # Layer 4: score
        result = screen(profile, jd_text)

        # ── Build response matching frontend's expected shape ─────────────────
        strengths = result.matched_skills[:6]
        gaps      = result.missing_skills[:6]

        # Build suggestions based on gaps
        suggestions = []
        if gaps:
            suggestions.append(
                f"Add these missing skills to your resume: {', '.join(gaps[:3])}"
            )
        if result.exp_gap < 0:
            suggestions.append(
                f"The role requires {result.required_exp_years:.0f}+ years — "
                f"highlight any freelance or project experience to bridge the gap."
            )
        if not result.degree_match and result.required_degree:
            suggestions.append(
                f"Role prefers {result.required_degree} degree — "
                f"highlight relevant certifications or courses."
            )
        if result.extra_skills:
            suggestions.append(
                f"Highlight these relevant skills more prominently: "
                f"{', '.join(result.extra_skills[:3])}"
            )

        return jsonify({
            "overall_score":    round(result.total_score, 1),
            "skills_score":     round(result.skill_score, 1),
            "experience_score": round(result.experience_score, 1),
            "education_score":  round(result.education_score, 1),
            "verdict":          result.verdict.value,
            "matched_skills":   result.matched_skills,
            "missing_skills":   result.missing_skills,
            "strengths":        strengths,
            "gaps":             gaps,
            "suggestions":      suggestions,
            "candidate_name":   profile.name,
            "exp_years":        profile.total_exp_years,
            "warnings":         result.warnings,
        }), 200

    except Exception as e:
        logger.error(f"/api/screen failed: {e}", exc_info=True)
        return jsonify({"error": f"Screening failed: {str(e)}"}), 500