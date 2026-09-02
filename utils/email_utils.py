from flask import current_app, render_template
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(email: str, salt: str) -> str:
    return _serializer().dumps(email, salt=salt)


def verify_token(token: str, salt: str, max_age: int):
    """Returns the email if valid, or None if invalid/expired."""
    try:
        return _serializer().loads(token, salt=salt, max_age=max_age)
    except Exception:
        return None


def send_email(mail, subject: str, recipient: str, html_body: str):
    msg = Message(subject=subject, recipients=[recipient], html=html_body)
    mail.send(msg)


def send_verification_email(mail, user_email: str, full_name: str):
    token = generate_token(user_email, salt="email-verify")
    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:5500')
    link = f"{frontend_url}/verify?token={token}"

    html = f"""
    <div style="font-family: sans-serif; text-align:right; direction: rtl; padding: 20px; background-color: #241B3D; color: #F7F3FF; border-radius: 12px;">
      <h2 style="color: #FF6F5E;">هلا {full_name} 👋</h2>
      <p>خطوة وحدة وتفعّل حسابك بمنصة مسار.</p>
      <p><a href="{link}" style="background:#FF6F5E;color:#1A1030;padding:12px 24px;
         border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block;margin:10px 0;">فعّل حسابك</a></p>
      <p style="color:#A79FC7;font-size:13px;">الرابط صالح لمدة 24 ساعة.</p>
    </div>
    """
    send_email(mail, "فعّل حسابك بمسار", user_email, html)


def send_reset_email(mail, user_email: str, full_name: str, code: str):
    html = f"""
    <div style="direction: rtl; text-align: right; font-family: sans-serif; padding: 25px; background-color: #241B3D; color: #F7F3FF; border-radius: 12px; border: 1px solid rgba(247,243,255,0.1);">
      <h2 style="color: #FF6F5E; margin-top: 0;">أهلاً {full_name} 👋</h2>
      <p style="font-size: 15px; color: #F7F3FF;">وصلنا طلب لإعادة تعيين كلمة المرور الخاصة بحسابك في <b>منصة مسار</b>.</p>
      <p style="font-size: 14px; color: #A79FC7; margin-bottom: 8px;">رمز التوثيق الخاص بك هو:</p>
      
      <div style="background-color: #2E2350; padding: 18px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #FF9587; border-radius: 10px; border: 1px dashed #FF6F5E; margin: 15px 0;">
        {code}
      </div>
      
      <p style="font-size: 13px; color: #A79FC7; margin-top: 15px;">استخدم هذا الرمز في صفحة التوثيق لإكمال عملية تعيين كلمة المرور الجديدة.</p>
      <p style="font-size: 12px; color: #888; margin-top: 20px; border-top: 1px solid rgba(247,243,255,0.08); padding-top: 12px;">إذا لم تطلب هذا الرمز، يمكنك تجاهل هذا البريد الإلكتروني بأمان.</p>
    </div>
    """
    send_email(mail, "رمز توثيق استعادة كلمة المرور — مسار", user_email, html)


def send_register_otp_email(mail, user_email: str, full_name: str, code: str):
    html = f"""
    <div style="direction: rtl; text-align: right; font-family: sans-serif; padding: 25px; background-color: #241B3D; color: #F7F3FF; border-radius: 12px; border: 1px solid rgba(247,243,255,0.1);">
      <h2 style="color: #FF6F5E; margin-top: 0;">أهلاً بك 👋</h2>
      <p style="font-size: 15px; color: #F7F3FF;">شكراً لانضمامك إلى <b>منصة مسار</b>. أكمل إنشاء حسابك باستخدام رمز التوثيق التالي:</p>
      
      <div style="background-color: #2E2350; padding: 18px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #FF9587; border-radius: 10px; border: 1px dashed #FF6F5E; margin: 15px 0;">
        {code}
      </div>
      
      <p style="font-size: 13px; color: #A79FC7; margin-top: 15px;">أدخل هذا الرمز في صفحة التسجيل لتأكيد حسابك.</p>
      <p style="font-size: 12px; color: #888; margin-top: 20px; border-top: 1px solid rgba(247,243,255,0.08); padding-top: 12px;">إذا لم تقم بإنشاء حساب، يمكنك تجاهل هذا البريد الإلكتروني.</p>
    </div>
    """
    send_email(mail, "رمز توثيق إنشاء الحساب — مسار", user_email, html)
