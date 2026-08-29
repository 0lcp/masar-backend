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
    link = f"{current_app.config['FRONTEND_URL']}/verify?token={token}"

    html = f"""
    <div style="font-family: sans-serif; text-align:right; direction: rtl;">
      <h2>هلا {full_name} 👋</h2>
      <p>خطوة وحدة وتفعّل حسابك بمسار.</p>
      <p><a href="{link}" style="background:#FF6F5E;color:#1A1030;padding:12px 24px;
         border-radius:8px;text-decoration:none;font-weight:bold;">فعّل حسابك</a></p>
      <p style="color:#888;font-size:13px;">الرابط صالح لمدة 24 ساعة.</p>
    </div>
    """
    send_email(mail, "فعّل حسابك بمسار", user_email, html)


def send_reset_email(mail, user_email: str, full_name: str):
    token = generate_token(user_email, salt="password-reset")
    link = f"{current_app.config['FRONTEND_URL']}/reset-password?token={token}"

    html = f"""
    <div style="font-family: sans-serif; text-align:right; direction: rtl;">
      <h2>استعادة كلمة المرور</h2>
      <p>وصلنا طلب لاستعادة كلمة مرور حسابك ({user_email}).</p>
      <p><a href="{link}" style="background:#FF6F5E;color:#1A1030;padding:12px 24px;
         border-radius:8px;text-decoration:none;font-weight:bold;">تعيين كلمة مرور جديدة</a></p>
      <p style="color:#888;font-size:13px;">الرابط صالح لمدة ساعة وحدة. إذا ماطلبت هذا، تجاهل الإيميل.</p>
    </div>
    """
    send_email(mail, "استعادة كلمة المرور — مسار", user_email, html)
