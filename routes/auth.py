import random
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from flask_mail import Message

from models import db, User, GRADES

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# تخزين مؤقت لرموز OTP
# ملاحظة: على Render المجاني قد يضيع هذا التخزين عند إعادة تشغيل السيرفر.
otp_store = {}

# مدة صلاحية OTP
OTP_EXPIRE_MINUTES = 10


# =========================================================
# Helpers
# =========================================================

def normalize_email(email):
    return email.strip().lower() if email else ""


def generate_otp():
    return str(random.randint(100000, 999999))


def store_otp(email, code, purpose):
    otp_store[email] = {
        "code": code,
        "purpose": purpose,
        "expires_at": datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    }


def verify_otp(email, code, purpose):
    item = otp_store.get(email)

    if not item:
        return False, "رمز التحقق غير موجود أو انتهت صلاحيته"

    if item["purpose"] != purpose:
        return False, "رمز التحقق غير صالح لهذه العملية"

    if datetime.utcnow() > item["expires_at"]:
        otp_store.pop(email, None)
        return False, "انتهت صلاحية رمز التحقق"

    if str(item["code"]) != str(code).strip():
        return False, "رمز التحقق غير صحيح"

    otp_store.pop(email, None)
    return True, None


def send_otp_email(email, full_name, code, purpose="register"):
    """
    إرسال OTP باستخدام Flask-Mail الموجود أصلاً في app.py.
    """

    from app import mail

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

    msg = Message(
        subject=subject,
        recipients=[email],
        html=html,
    )

    mail.send(msg)


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
        grade = data.get("grade", "").strip()

        # -------------------------
        # Validation
        # -------------------------

        if len(full_name) < 3:
            return jsonify({
                "success": False,
                "error": "الاسم الكامل مطلوب"
            }), 400

        if not email or "@" not in email:
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني غير صحيح"
            }), 400

        if len(password) < 8:
            return jsonify({
                "success": False,
                "error": "كلمة المرور لازم تكون 8 أحرف أو أكثر"
            }), 400

        if grade not in GRADES:
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

            # الحساب موجود لكن غير موثق:
            # نرسل OTP جديد
            code = generate_otp()
            store_otp(email, code, "register")

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
                    "error": "تعذر إرسال رمز التحقق. تأكد من إعدادات البريد في Render."
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
            grade=grade,
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
        store_otp(email, code, "register")

        try:
            send_otp_email(
                email,
                full_name,
                code,
                "register"
            )
        except Exception as mail_error:
            print(f"Error sending registration OTP: {mail_error}")

            # الحساب انحفظ، لكن البريد فشل.
            # لا نحذف الحساب حتى نقدر نعيد إرسال OTP.
            return jsonify({
                "success": False,
                "error": "تم إنشاء الحساب لكن تعذر إرسال رمز التحقق. حاول إعادة الإرسال."
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
                # لا نكشف هل الإيميل مسجل أو لا
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
        store_otp(email, code, purpose)

        try:
            send_otp_email(
                email,
                user.full_name if user else "",
                code,
                "register" if purpose == "register" else "reset"
            )
        except Exception as mail_error:
            print(f"OTP EMAIL ERROR: {mail_error}")

            return jsonify({
                "success": False,
                "error": "تعذر إرسال البريد. تأكد من إعدادات SMTP."
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

        valid, error = verify_otp(
            email,
            code,
            "register"
        )

        if not valid:
            return jsonify({
                "success": False,
                "error": error
            }), 400

        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({
                "success": False,
                "error": "الحساب غير موجود"
            }), 404

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

        if not user:
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني أو كلمة المرور غير صحيحة"
            }), 401

        if not user.check_password(password):
            return jsonify({
                "success": False,
                "error": "البريد الإلكتروني أو كلمة المرور غير صحيحة"
            }), 401

        if not user.is_verified:
            return jsonify({
                "success": False,
                "error": "الحساب غير موثق. تحقق من بريدك الإلكتروني أولاً."
            }), 403

        access_token = create_access_token(
            identity=str(user.id)
        )

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

        # نفس الرد حتى ما نكشف وجود الحساب
        if not user:
            return jsonify({
                "success": True,
                "message": "إذا كان الإيميل مسجل، راح يوصلك رمز الاستعادة."
            }), 200

        code = generate_otp()
        store_otp(email, code, "reset")

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

        valid, error = verify_otp(
            email,
            code,
            "reset"
        )

        if not valid:
            return jsonify({
                "success": False,
                "error": error
            }), 400

        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({
                "success": False,
                "error": "المستخدم غير موجود"
            }), 404

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
