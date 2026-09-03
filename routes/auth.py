from flask import Blueprint, request, jsonify

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/send-otp', methods=['POST'])
def send_otp():
    try:
        data = request.get_json() or {}
        email = data.get('email')

        if not email:
            return jsonify({'error': 'البريد الإلكتروني مطلوب'}), 400

        # كود معالجة OTP هنا مباشرة
        
        return jsonify({'message': 'تم إرسال رمز التحقق بنجاح، تحقق من بريدك الإلكتروني.'}), 200

    except Exception as e:
        print(f"Error sending OTP: {e}")
        return jsonify({'error': 'حدث خطأ أثناء إرسال الرمز'}), 500
