import re
import random
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from models import db, User, GRADES
from utils.email_utils import send_verification_email, send_reset_email, verify_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# ذاكرة مؤقتة لتخزين الرموز
RESET_CODES = {}
REGISTER_CODES = {}


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


@auth_bp.route("/send-register-otp", methods=["POST"])
def send_register_otp():
    from app import mail

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not EMAIL_RE.match(email):
        return error("البريد الإلكتروني غير صحيح")

    if User.query.filter_by(email=email).first():
        return error("هذا البريد مسجل من قبل", status=409)

    # توليد رمز OTP لإنشاء الحساب
    code = str(random.randint(100000, 999999))
    REGISTER_CODES[email] = code

    try:
        # استخدام دالة الإرسال المتوفرة
        send_reset_email(mail, email, "مستخدم جديد", code)
    except Exception as exc:
        current_app.logger.error(f"Could not send register OTP: {exc}")
        return error("حدث خطأ أثناء إرسال رمز التوثيق", status=500)

    return jsonify({
        "success": True,
        "message": "تم إرسال رمز التوثيق إلى بريدك الإلكتروني"
    })


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    grade = data.get("grade") or ""
    code = str(data.get("code") or "").strip()

    # ---- validation ----
    if len(full_name) < 3:
        return error("الاسم الكامل لازم يكون 3 أحرف أو أكثر")
    if not EMAIL_RE.match(email):
        return error("البريد الإلكتروني غير صحيح")
    if len(password) < 8:
        return error("كلمة المرور لازم تكون 8 أحرف أو أكثر")
    if grade not in GRADES:
        return error("اختر صف دراسي صحيح")

    # التحقق من رمز التوثيق
    saved_code = REGISTER_CODES.get(email)
    if not saved_code or saved_code != code:
        return error("رمز التوثيق غير صحيح أو منتهي الصلاحية", status=400)

    if User.query.filter_by(email=email).first():
        return error("هذا البريد مسجل من قبل", status=409)

    user = User(full_name=full_name, email=email, grade=grade)
    user.set_password(password)
    user.is_verified = True
    
    db.session.add(user)
    db.session.commit()

    # مسح الرمز من الذاكرة
    REGISTER_CODES.pop(email, None)

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        "success": True,
        "token": access_token,
        "message": "تم إنشاء الحساب وتأكيده بنجاح.",
        "user": user.to_dict(),
    }), 201


@auth_bp.route("/verify-email", methods=["POST"])
def verify_email():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")

    email = verify_token(token, salt="email-verify", max_age=current_app.config.get("EMAIL_TOKEN_MAX_AGE", 86400))
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

    access_token = create_access_token(identity=str(user.id))
    return jsonify({
        "success": True,
        "token": access_token,
        "access_token": access_token,
        "user": user.to_dict(),
    })


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    from app import mail

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return error("يرجى إدخال البريد الإلكتروني")

    user = User.query.filter_by(email=email).first()
    if user:
        code = str(random.randint(100000, 999999))
        RESET_CODES[email] = code

        try:
            send_reset_email(mail, user.email, user.full_name, code)
        except Exception as exc:
            current_app.logger.error(f"Could not send reset email: {exc}")

    return jsonify({
        "success": True,
        "message": "إذا كان البريد مسجلاً لدينا فستتلقى رمز التوثيق قريباً",
    })


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    code = str(data.get("code") or "").strip()
    new_password = data.get("password") or data.get("newPassword") or ""

    if not email or not code or not new_password:
        return error("جميع الحقول مطلوبة")

    if len(new_password) < 8:
        return error("كلمة المرور لازم تكون 8 أحرف أو أكثر")

    saved_code = RESET_CODES.get(email)
    if not saved_code or saved_code != code:
        return error("رمز التوثيق غير صحيح أو انتهت صلاحيته", status=400)

    user = User.query.filter_by(email=email).first()
    if not user:
        return error("الحساب غير موجود", status=404)

    user.set_password(new_password)
    db.session.commit()

    RESET_CODES.pop(email, None)

    return jsonify({"success": True, "message": "تم تغيير كلمة المرور بنجاح"})


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return error("المستخدم غير موجود", status=404)
    return jsonify({"success": True, "user": user.to_dict()})
