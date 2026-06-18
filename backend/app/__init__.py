import sys
import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from .config import get_config
from .extensions import db, celery


def create_app(config_override=None):
    app = Flask(__name__)

    cfg = config_override or get_config()
    app.config.from_object(cfg)

    logging.basicConfig(
        level=logging.DEBUG if app.config.get("DEBUG") else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    CORS(app, origins=app.config.get("CORS_ORIGINS",
         ["http://localhost:3000", "http://localhost:5173"]))

    db.init_app(app)
    with app.app_context():
        db.create_all()
        app.logger.info("Database tables ready")

    _init_redis(app)
    _init_celery(app)

    os.makedirs(app.config.get("UPLOAD_FOLDER", "/tmp/resume_uploads"), exist_ok=True)

    from .routes.jobs import jobs_bp
    from .routes.resumes import resumes_bp
    from .routes.results import results_bp
    from .routes.screen import screen_bp

    app.register_blueprint(jobs_bp,    url_prefix="/api")
    app.register_blueprint(resumes_bp, url_prefix="/api")
    app.register_blueprint(results_bp, url_prefix="/api")
    app.register_blueprint(screen_bp,  url_prefix="/api")

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large"}), 413

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"500: {e}")
        return jsonify({"error": "Internal server error"}), 500

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    app.logger.info(f"App ready — debug={app.config.get('DEBUG')}")
    return app


def _init_redis(app):
    import app.extensions as ext
    try:
        import redis
        client = redis.from_url(
            app.config.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        client.ping()
        ext.redis_client = client
        app.logger.info("Redis connected")
    except Exception as e:
        app.logger.warning(f"Redis not available ({e}) — caching disabled")
        ext.redis_client = None


def _init_celery(app):
    celery.conf.update(
        broker_url=app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        result_backend=app.config.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        task_track_started=True,
        broker_connection_retry_on_startup=True,
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    app.logger.info("Celery configured")