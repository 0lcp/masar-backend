from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail

from config import Config
from models import db, bcrypt

mail = Mail()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---- Extensions ----
    db.init_app(app)
    bcrypt.init_app(app)
    JWTManager(app)
    mail.init_app(app)

    # تهيئة CORS بشكل كامل للسماح بالطلبات من أي مصدر وجميع الترويسات
    CORS(
        app,
        resources={r"/*": {"origins": "*"}},
        allow_headers=["Content-Type", "Authorization", "Accept"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    # معالجة طلبات OPTIONS لمتصفحات Safari و iOS لضمان استجابة 200 OK قبل الـ Fetch
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = app.make_default_options_response()
            headers = response.headers
            headers['Access-Control-Allow-Origin'] = '*'
            headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
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

    # ---- Health check ----
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "masar-backend"})

    # ---- Create tables on first run ----
    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
