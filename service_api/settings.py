import os


class Config:
    TESTING = False
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost")
    RESULT_BACKEND = os.environ.get("RESULT_BACKEND", "redis://localhost")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:pwd@localhost/postgres"
    )
    UPLOAD_FOLDER = "statics/uploads"


class DevelopmentConfig(Config):
    TESTING = True
