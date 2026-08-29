import re
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from models import db, User, GRADES
from utils.email_utils import send_verification_email, send_reset_email, verify_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


@auth_bp.route("/register", methods=["POST"])
def register():
    from app import mail  # local import avoids circular import

    data = request.get_json(silent=True) or {}
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    grade = data.get("grade") or ""

    # ---- validation ----
    if len(full_name) < 3:
        return error("الاسم الكامل لازم يكون 3 أحرف أو أكثر")
    if not EMAIL_RE.match(email):
        return error("البريد الإلكتروني غير صحيح")
    if len(password) < 8:
        return error("كلمة المرور لازم تكون 8 أحرف أو أكثر")
    if grade not in GRADES:
        return error("اختر صف دراسي صحيح")

    if User.query.filter_by(email=email).first():
        return error("هذا البريد مسجل من قبل", status=409)

    user = User(full_name=full_name, email=email, grade=grade)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Email sending fails silently if MAIL_USERNAME isn't configured yet (dev mode)
    try:
        send_verification_email(mail, email, full_name)
    except Exception as exc:
        current_app.logger.warning(f"Could not send verification email: {exc}")

    return jsonify({
        "success": True,
        "message": "تم إنشاء الحساب. تحقق من إيميلك لتفعيله.",
        "user": user.to_dict(),
    }), 201


@auth_bp.route("/verify-email", methods=["POST"])
def verify_email():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")

    email = verify_token(token, salt="email-verify", max_age=current_app.config["EMAIL_TOKEN_MAX_AGE"])
    if not email:
        return error("رابط التفعيل غير صحيح أو منتهي", status=400)

    user = User.query.filter_by(email=email).first()
    if not user:
        return error("الحساب غير موجود", status=404)

    user.is_verified = True
    db.session.commit()
    return jsonify({"success": True, "message": "تم تفعيل حسابك بنجاح"})


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return error("البريد أو كلمة المرور غير صحيحة", status=401)

    if not user.is_verified:
        return error("لازم تفعّل بريدك الإلكتروني أول", status=403)

    access_token = create_access_token(identity=user.id)
    return jsonify({
        "success": True,
        "access_token": access_token,
        "user": user.to_dict(),
    })


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    from app import mail

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    user = User.query.filter_by(email=email).first()
    # We respond the same whether the user exists or not — avoids leaking which emails are registered.
    if user:
        try:
            send_reset_email(mail, user.email, user.full_name)
        except Exception as exc:
            current_app.logger.warning(f"Could not send reset email: {exc}")

    return jsonify({
        "success": True,
        "message": "إذا كان الإيميل مسجل عندنا، بيوصلك رابط استعادة كلمة المرور",
    })


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    new_password = data.get("password") or ""

    if len(new_password) < 8:
        return error("كلمة المرور لازم تكون 8 أحرف أو أكثر")

    email = verify_token(token, salt="password-reset", max_age=current_app.config["RESET_TOKEN_MAX_AGE"])
    if not email:
        return error("رابط الاستعادة غير صحيح أو منتهي", status=400)

    user = User.query.filter_by(email=email).first()
    if not user:
        return error("الحساب غير موجود", status=404)

    user.set_password(new_password)
    db.session.commit()
    return jsonify({"success": True, "message": "تم تغيير كلمة المرور بنجاح"})


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return error("المستخدم غير موجود", status=404)
    return jsonify({"success": True, "user": user.to_dict()})
