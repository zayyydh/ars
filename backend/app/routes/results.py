"""
routes/results.py — screening result retrieval.

Blueprint: /api/results

GET /api/results/<result_id>
    The polling endpoint. Frontend calls this every 2s until status="completed".
    Returns the full ScreeningResult when done.

GET /api/results?job_id=<id>&verdict=SHORTLIST
    List results for a job with optional verdict filter.
    Used for the "all candidates" view sorted by score.
"""

from flask import Blueprint, request, jsonify
from app.services import pipeline_service
from app.models.db_models import ScreeningResult

results_bp = Blueprint("results", __name__)


@results_bp.get("/results/<result_id>")
def get_result(result_id: str):
    """
    Polling endpoint. Returns current status and result when complete.

    Response shape:
        {
            "id":       "uuid",
            "status":   "pending" | "processing" | "completed" | "failed",
            "result":   { ... }   ← only when status="completed"
            "error":    "..."     ← only when status="failed"
        }

    Frontend polling pattern:
        const poll = async (resultId) => {
            const r = await fetch(`/api/results/${resultId}`)
            const data = await r.json()
            if (data.status === 'completed') return data.result
            if (data.status === 'failed')    throw new Error(data.error)
            await sleep(2000)
            return poll(resultId)   // retry
        }
    """
    result = pipeline_service.get_result(result_id)
    if not result:
        return jsonify({"error": "Result not found"}), 404

    response = {
        "id":     result.id,
        "status": result.status,
    }

    if result.status == "completed":
        response["result"] = result.to_dict()

    elif result.status == "failed":
        response["error"] = result.error_message or "Screening failed"

    elif result.status in ("pending", "processing"):
        response["message"] = "Screening in progress — check back shortly"

    return jsonify(response), 200


@results_bp.get("/results")
def list_results():
    """
    List results with optional filters.

    Query params:
        job_id  (required) — filter by job
        verdict (optional) — SHORTLIST | REVIEW | REJECT
        limit   (optional) — max results to return (default 50)
    """
    job_id = request.args.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "job_id query parameter is required"}), 400

    verdict_filter = request.args.get("verdict", "").upper()
    limit          = min(int(request.args.get("limit", 50)), 200)

    query = (
        ScreeningResult.query
        .filter_by(job_id=job_id, status="completed")
        .order_by(ScreeningResult.total_score.desc())
    )

    if verdict_filter in ("SHORTLIST", "REVIEW", "REJECT"):
        query = query.filter_by(verdict=verdict_filter)

    results = query.limit(limit).all()

    return jsonify({
        "job_id":  job_id,
        "count":   len(results),
        "results": [r.to_dict() for r in results],
    }), 200