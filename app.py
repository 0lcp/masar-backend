import socket
socket.setdefaulttimeout(10)

# --- إجبار الاتصالات على IPv4 بس (حل مشكلة Errno 101 على Render) ---
_orig_getaddrinfo = socket.getaddrinfo
def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _getaddrinfo_ipv4
# --------------------------------------------------------------

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from sqlalchemy import text, inspect

from config import Config
from extensions import db, mail
from models import bcrypt

# ... باقي الكود يضل نفسه بدون تغيير


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---- Extensions ----
    db.init_app(app)
    bcrypt.init_app(app)
    JWTManager(app)
    mail.init_app(app)

    CORS(
        app,
        resources={r"/*": {"origins": Config.ALLOWED_ORIGINS}},
        supports_credentials=True,
    )

    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.content import content_bp
    from routes.subscription import subscription_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(subscription_bp)

    @app.route("/", methods=["GET"])
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "masar-backend"})

    with app.app_context():
        db.create_all()

        # ---- ترحيل آمن: يضيف أعمدة ناقصة لجدول users إذا مو موجودة ----
        inspector = inspect(db.engine)
        existing_columns = [col["name"] for col in inspector.get_columns("users")]

        missing_columns = {
            "otp_code": "VARCHAR(6)",
            "otp_purpose": "VARCHAR(20)",
            "otp_expires_at": "TIMESTAMP",
            "otp_attempts": "INTEGER DEFAULT 0",
        }

        for col_name, col_type in missing_columns.items():
            if col_name not in existing_columns:
                try:
                    db.session.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Migration warning ({col_name}): {e}")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
