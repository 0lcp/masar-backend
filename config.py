import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ---- Core ----
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")

    # ---- Database (SQLite = free, no external service needed) ----
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'masar.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # ---- JWT ----
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-this-too")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # ---- Email (Resend API — HTTPS, يتجاوز حجب SMTP على Render) ----
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Masar <onboarding@resend.dev>")

    # ---- Frontend URL (used inside email links) ----
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5500")

    # ---- Allowed origins for CORS (comma-separated) ----
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            "ALLOWED_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500"
        ).split(",")
        if origin.strip()
    ]

    # ---- Token expiry ----
    EMAIL_TOKEN_MAX_AGE = 60 * 60 * 24        # 24 hours to verify email
    RESET_TOKEN_MAX_AGE = 60 * 60             # 1 hour to reset password
