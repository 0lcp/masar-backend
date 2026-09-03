from flask import Flask, jsonify, make_response, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail

from config import Config
from models import bcrypt, db

mail = Mail()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---- Extensions ----
    db.init_app(app)
    bcrypt.init_app(app)
    JWTManager(app)
    mail.init_app(app)

    # تهيئة CORS
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # معالجة طلبات OPTIONS تلقائياً لمنع حظر المتصفح
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = make_response()
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add(
                "Access-Control-Allow-Headers", "Content-Type, Authorization, Accept"
            )
            response.headers.add(
                "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
            )
            return response, 200

    # إضافة ترويسات CORS لجميع الاستجابات
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, Accept"
        )
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        return response

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
