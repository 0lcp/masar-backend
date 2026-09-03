import random
from flask import Blueprint, jsonify, request
from flask_mail import Message

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# ذاكرة مؤقتة لتخزين الرموز (في بيئة الإنتاج يفضل استخدام Redis أو قاعدة البيانات)
otp_store = {}


@auth_bp.route('/send-otp', methods=['POST'])
def send_otp():
    try:
        from app import mail  # استدعاء كائن Mail المتصل بالتطبيق

        data = request.get_json() or {}
        email = data.get('email')

        if not email:
            return jsonify({'error': 'البريد الإلكتروني مطلوب'}), 400

        # 1. توليد رمز OTP مكون من 6 أرقام
        otp_code = str(random.randint(100000, 999999))
        otp_store[email] = otp_code

        # 2. تجهيز الرسالة
        msg = Message(
            subject='رمز التحقق الخاص بك - منصة مسار',
            recipients=[email],
            body=f'رمز التحقق الخاص بك هو: {otp_code}\n\nهذا الرمز صالحة للاستخدام مرة واحدة فقط.',
        )

        # 3. الإرسال الفعلي
        mail.send(msg)

        return (
            jsonify(
                {
                    'message': (
                        'تم إرسال رمز التحقق بنجاح، تحقق من بريدك الإلكتروني.'
                    )
                }
            ),
            200,
        )

    except Exception as e:
        print(f'Error sending email: {e}')
        return (
            jsonify(
                {
                    'error': (
                        'حدث خطأ أثناء إرسال البريد. تأكد من إعدادات SMTP في'
                        ' البيئة.'
                    )
                }
            ),
            500,
        )
