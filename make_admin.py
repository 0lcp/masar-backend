"""
سكريبت يرفّع مستخدم مسجل أصلاً لدرجة "أدمن" — يعطيه صلاحية الوصول للوحة التحكم.

الاستخدام:
    python make_admin.py your-email@example.com

⚠️ الطالب لازم يكون سوّى حساب عادي وفعّله (verify) أول قبل لا تشغّل هذا السكريبت.
"""
import sys
from app import create_app
from models import db, User

app = create_app()


def make_admin(email: str):
    with app.app_context():
        user = User.query.filter_by(email=email.strip().lower()).first()
        if not user:
            print(f"❌ ماكو حساب بهذا الإيميل: {email}")
            return

        user.role = "admin"
        db.session.commit()
        print(f"✅ صار {user.full_name} ({user.email}) أدمن الحين.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("الاستخدام: python make_admin.py your-email@example.com")
        sys.exit(1)

    make_admin(sys.argv[1])
