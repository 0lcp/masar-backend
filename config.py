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

    # ---- JWT ----
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-this-too")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # ---- Email (Gmail SMTP — free, needs an "App Password") ----
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_USERNAME", "")

    # ---- Frontend URL (used inside email links) ----
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5500")

    # ---- Token expiry ----
    EMAIL_TOKEN_MAX_AGE = 60 * 60 * 24        # 24 hours to verify email
    RESET_TOKEN_MAX_AGE = 60 * 60             # 1 hour to reset password
