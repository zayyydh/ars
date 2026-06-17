import os
from dotenv import load_dotenv

# Load .env from the backend/ folder
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


class Config:
    SECRET_KEY             = os.getenv("SECRET_KEY", "dev-secret-key")
    MAX_CONTENT_LENGTH     = 10 * 1024 * 1024
    UPLOAD_FOLDER          = os.getenv("UPLOAD_FOLDER", "/tmp/resume_uploads")
    ALLOWED_EXTENSIONS     = {"pdf", "docx", "doc"}

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/resume_screener"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle":  300,
    }

    REDIS_URL             = os.getenv("REDIS_URL",             "redis://localhost:6379/0")
    CELERY_BROKER_URL     = os.getenv("CELERY_BROKER_URL",     "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    LLM_PROVIDER   = os.getenv("LLM_PROVIDER",  "openai")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

    SCORE_SHORTLIST_THRESHOLD = float(os.getenv("SCORE_SHORTLIST_THRESHOLD", "70"))
    SCORE_REVIEW_THRESHOLD    = float(os.getenv("SCORE_REVIEW_THRESHOLD",    "45"))
    RESULT_CACHE_TTL          = int(os.getenv("RESULT_CACHE_TTL", "1800"))

    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173"
    ).split(",")


class DevelopmentConfig(Config):
    DEBUG   = True
    TESTING = False


class ProductionConfig(Config):
    DEBUG   = False
    TESTING = False


class TestingConfig(Config):
    TESTING  = True
    DEBUG    = True
    SQLALCHEMY_DATABASE_URI  = "sqlite:///:memory:"
    CELERY_TASK_ALWAYS_EAGER = True


config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
}

def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)