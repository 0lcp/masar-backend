from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config import Config
from extensions import db, mail
from models import bcrypt


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---- Extensions ----
    db.init_app(app)
    bcrypt.init_app(app)
    JWTManager(app)
    mail.init_app(app)

    # تهيئة CORS — origins محددة من config.py (لازم credentials مع origin محدد، مو "*")
    CORS(
        app,
        resources={r"/*": {"origins": Config.ALLOWED_ORIGINS}},
        supports_credentials=True,
    )

    # ---- Blueprints ----
    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.content import content_bp
    from routes.subscription import subscription_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(subscription_bp)

    # ---- Health check & Root ----
    @app.route("/", methods=["GET"])
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "masar-backend"})

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
