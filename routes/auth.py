import random
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
import requests
from flask import current_app

# استيراد db من ملف extensions للحد من التداخل والدائريات
from extensions import db
from models import User, Grade


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# مدة صلاحية OTP بالدقائق
OTP_EXPIRE_MINUTES = 10
MAX_OTP_ATTEMPTS = 3

# =========================================================
# Helpers
# =========================================================
def normalize_email(email):
    return email.strip().lower() if email else ""

def generate_otp():
    return str(random.randint(100000, 999999))

def set_user_otp(user, code, purpose):
    """
    تخزين رمز OTP في قاعدة البيانات بدلاً من الذاكرة المؤقتة لضمان استقراره على Render.
    """
    user.otp_code = str(code)
    user.otp_purpose = purpose
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    user.otp_attempts = 0
    db.session.commit()

def verify_user_otp(user, code, purpose):
    """
    التحقق من رمز OTP من قاعدة البيانات مع حماية من هجمات التخمين.
    """
    if not user or not user.otp_code:
        return False, "رمز التحقق غير موجود أو تم استخدامه"

    # حماية ضد التخمين المتكرر
    if user.otp_attempts >= MAX_OTP_ATTEMPTS:
        user.otp_code = None
        user.otp_purpose = None
        user.otp_expires_at = None
        user.otp_attempts = 0
        db.session.commit()
        return False, "تجاوزت الحد المسموح للمحاولات الخاطئة. يرجى طلب رمز جديد."

    if user.otp_purpose != purpose:
        return False, "رمز التحقق غير صالح لهذه العملية"

    now = datetime.now(timezone.utc)
    expires_at = user.otp_expires_at

    # ضمان التعامل مع المناطق الزمنية بشكل صحيح
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if not expires_at or now > expires_at:
        user.otp_code = None
        user.otp_purpose = None
        user.otp_expires_at = None
        user.otp_attempts = 0
        db.session.commit()
        return False, "انتهت صلاحية رمز التحقق"

    if user.otp_code != str(code).strip():
        user.otp_attempts += 1
        db.session.commit()
        remaining = MAX_OTP_ATTEMPTS - user.otp_attempts
        return False, f"رمز التحقق غير صحيح. (المحاولات المتبقية: {remaining})"

    # التفعيل والتحقق ناجح -> مسح البيانات المؤقتة
    user.otp_code = None
    user.otp_purpose = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    db.session.commit()
    return True, None

def send_otp_email(email, full_name, code, purpose="register"):
    if purpose == "register":
        subject = "رمز توثيق إنشاء الحساب — مسار"
        title = "أهلاً بك 👋"
        description = (
            "شكراً لانضمامك إلى منصة مسار. "
            "استخدم رمز التوثيق التالي لإكمال إنشاء حسابك:"
        )
    else:
        subject = "رمز توثيق استعادة كلمة المرور — مسار"
        title = "أهلاً بك 👋"
        description = (
            "وصلنا طلب لإعادة تعيين كلمة المرور الخاصة بحسابك "
            "في منصة مسار. استخدم الرمز التالي:"
        )

    html = f"""
    <div style="
        direction:rtl;
        text-align:right;
        font-family:Arial,sans-serif;
        padding:25px;
        background:#241B3D;
        color:#F7F3FF;
        border-radius:12px;
    ">
        <h2 style="color:#FF6F5E;">{title}</h2>
        <p style="font-size:15px;">
            {description}
        </p>
        <div style="
            background:#2E2350;
            padding:18px;
            text-align:center;
            font-size:32px;
            font-weight:bold;
            letter-spacing:8px;
            color:#FF9587;
            border-radius:10px;
            border:1px dashed #FF6F5E;
            margin:15px 0;
        ">
            {code}
        </div>
        <p style="font-size:13px;color:#A79FC7;">
            الرمز صالح لمدة {OTP_EXPIRE_MINUTES} دقائق.
        </p>
        <p style="font-size:12px;color:#888;">
            إذا لم تطلب هذا الرمز، يمكنك تجاهل هذا البريد الإلكتروني.
        </p>
    </div>
    """
    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": current_app.config["BREVO_API_KEY"],
            "Content-Type": "application/json",
        },
        json={
            "sender": {"email": current_app.config["BREVO_FROM_EMAIL"], "name": "مسار"},
            "to": [{"email": email}],
            "subject": subject,
            "htmlContent": html,
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise Exception(f"Brevo API error {response.status_code}: {response.text}")


# =========================================================
# REGISTER
# =========================================================
@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json(silent=True) or {}
        full_name = data.get("full_name", "").strip()
        email = normalize_email(data.get("email"))
        password = data.get("password", "")
        grade_id = data.get("grade_id")

        # -------------------------
        # Validation
        # -------------------------
        if len(full_name) < 3:
            return jsonify({
                "success": False,
                "error": "الاسم الكامل مطلوب ويجب ألا يقل عن 3 أحرف"
            }), 400

        if not email or "@" not in email:
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني غير صحيح"
            }), 400

        if len(password) < 8:
            return jsonify({
                "success": False,
                "error": "كلمة المرور يجب أن تكون 8 أحرف أو أكثر"
            }), 400

        grade = Grade.query.get(grade_id) if grade_id else None
        if not grade:
            return jsonify({
                "success": False,
                "error": "الصف الدراسي غير صحيح"
            }), 400

        # -------------------------
        # Check existing account
        # -------------------------
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.is_verified:
                return jsonify({
                    "success": False,
                    "error": "هذا البريد الإلكتروني مسجل مسبقاً"
                }), 409

            # الحساب موجود لكن غير موثق: توليد رمز جديد وحفظه بالداتا بيز
            code = generate_otp()
            set_user_otp(existing_user, code, "register")
            try:
                send_otp_email(
                    email,
                    existing_user.full_name,
                    code,
                    "register"
                )
            except Exception as mail_error:
                print(f"Error sending registration OTP: {mail_error}")
                return jsonify({
                    "success": False,
                    "error": "تعذر إرسال رمز التحقق. تأكد من إعدادات البريد الإلكتروني."
                }), 500

            return jsonify({
                "success": True,
                "message": "الحساب موجود لكنه غير موثق. تم إرسال رمز تحقق جديد إلى إيميلك."
            }), 200

        # -------------------------
        # Create user
        # -------------------------
        user = User(
            full_name=full_name,
            email=email,
            grade_id=grade.id,
            is_verified=False,
            role="student",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # -------------------------
        # Generate + send OTP
        # -------------------------
        code = generate_otp()
        set_user_otp(user, code, "register")

        try:
            send_otp_email(
                email,
                full_name,
                code,
                "register"
            )
        except Exception as mail_error:
            print(f"Error sending registration OTP: {mail_error}")
            return jsonify({
                "success": False,
                "error": "تم إنشاء الحساب لكن تعذر إرسال رمز التحقق. حاول إعادة الإرسال لاحقاً."
            }), 500

        return jsonify({
            "success": True,
            "message": "تم إنشاء الحساب! تحقق من إيميلك لتفعيله."
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"REGISTER ERROR: {e}")
        return jsonify({
            "success": False,
            "error": "حدث خطأ أثناء إنشاء الحساب."
        }), 500

# =========================================================
# SEND OTP
# =========================================================
@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():
    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get("email"))
        purpose = data.get("purpose", "register")

        if not email:
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني مطلوب"
            }), 400

        user = User.query.filter_by(email=email).first()

        if purpose == "register":
            if not user:
                return jsonify({
                    "success": False,
                    "error": "الحساب غير موجود"
                }), 404
            if user.is_verified:
                return jsonify({
                    "success": False,
                    "error": "هذا الحساب موثق مسبقاً"
                }), 400
        elif purpose == "reset":
            if not user:
                # إخفاء وجود البريد لحماية الخصوصية
                return jsonify({
                    "success": True,
                    "message": "إذا كان البريد مسجلاً، سيصلك رمز التحقق."
                }), 200
        else:
            return jsonify({
                "success": False,
                "error": "نوع العملية غير صحيح"
            }), 400

        code = generate_otp()
        set_user_otp(user, code, purpose)

        try:
            send_otp_email(
                email,
                user.full_name,
                code,
                purpose
            )
        except Exception as mail_error:
            print(f"OTP EMAIL ERROR: {mail_error}")
            return jsonify({
                "success": False,
                "error": "تعذر إرسال البريد. تأكد من إعدادات البريد السحابية."
            }), 500

        return jsonify({
            "success": True,
            "message": "تم إرسال رمز التحقق إلى بريدك الإلكتروني."
        }), 200

    except Exception as e:
        print(f"SEND OTP ERROR: {e}")
        return jsonify({
            "success": False,
            "error": "حدث خطأ أثناء إرسال رمز التحقق."
        }), 500

# =========================================================
# VERIFY EMAIL
# =========================================================
@auth_bp.route("/verify-email", methods=["POST"])
def verify_email():
    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get("email"))
        code = str(data.get("code", "")).strip()

        if not email or not code:
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني ورمز التحقق مطلوبان"
            }), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({
                "success": False,
                "error": "الحساب غير موجود"
            }), 404

        valid, error = verify_user_otp(user, code, "register")
        if not valid:
            return jsonify({
                "success": False,
                "error": error
            }), 400

        user.is_verified = True
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "تم تفعيل حسابك بنجاح.",
            "user": user.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"VERIFY EMAIL ERROR: {e}")
        return jsonify({
            "success": False,
            "error": "حدث خطأ أثناء تفعيل الحساب."
        }), 500

# =========================================================
# LOGIN
# =========================================================
@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get("email"))
        password = data.get("password", "")

        if not email or not password:
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني وكلمة المرور مطلوبان"
            }), 400

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني أو كلمة المرور غير صحيحة"
            }), 401

        if not user.is_verified:
            return jsonify({
                "success": False,
                "error": "الحساب غير موثق. تحقق من بريدك الإلكتروني أولاً."
            }), 403

        access_token = create_access_token(identity=str(user.id))

        return jsonify({
            "success": True,
            "message": "تم تسجيل الدخول بنجاح",
            "access_token": access_token,
            "user": user.to_dict()
        }), 200

    except Exception as e:
        print(f"LOGIN ERROR: {e}")
        return jsonify({
            "success": False,
            "error": "حدث خطأ أثناء تسجيل الدخول."
        }), 500

# =========================================================
# ME
# =========================================================
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    try:
        user_id = get_jwt_identity()
        user = db.session.get(User, int(user_id))
        if not user:
            return jsonify({
                "success": False,
                "error": "المستخدم غير موجود"
            }), 404

        return jsonify({
            "success": True,
            "user": user.to_dict()
        }), 200

    except Exception as e:
        print(f"ME ERROR: {e}")
        return jsonify({
            "success": False,
            "error": "تعذر جلب بيانات المستخدم."
        }), 500

# =========================================================
# FORGOT PASSWORD
# =========================================================
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get("email"))

        if not email:
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني مطلوب"
            }), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            # رد موحد لحماية الخصوصية
            return jsonify({
                "success": True,
                "message": "إذا كان الإيميل مسجلاً، راح يوصلك رمز الاستعادة."
            }), 200

        code = generate_otp()
        set_user_otp(user, code, "reset")

        try:
            send_otp_email(
                email,
                user.full_name,
                code,
                "reset"
            )
        except Exception as mail_error:
            print(f"RESET EMAIL ERROR: {mail_error}")
            return jsonify({
                "success": False,
                "error": "تعذر إرسال البريد. تأكد من إعدادات SMTP."
            }), 500

        return jsonify({
            "success": True,
            "message": "تم إرسال رمز استعادة كلمة المرور إلى بريدك."
        }), 200

    except Exception as e:
        print(f"FORGOT PASSWORD ERROR: {e}")
        return jsonify({
            "success": False,
            "error": "حدث خطأ أثناء طلب استعادة كلمة المرور."
        }), 500

# =========================================================
# RESET PASSWORD
# =========================================================
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get("email"))
        code = str(data.get("code", "")).strip()
        new_password = data.get("password", "")

        if not email or not code or not new_password:
            return jsonify({
                "success": False,
                "error": "البريد والرمز وكلمة المرور الجديدة مطلوبة"
            }), 400

        if len(new_password) < 8:
            return jsonify({
                "success": False,
                "error": "كلمة المرور لازم تكون 8 أحرف أو أكثر"
            }), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({
                "success": False,
                "error": "المستخدم غير موجود"
            }), 404

        valid, error = verify_user_otp(user, code, "reset")
        if not valid:
            return jsonify({
                "success": False,
                "error": error
            }), 400

        user.set_password(new_password)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "تم تغيير كلمة المرور بنجاح."
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"RESET PASSWORD ERROR: {e}")
        return jsonify({
            "success": False,
            "error": "حدث خطأ أثناء تغيير كلمة المرور."
        }), 500
