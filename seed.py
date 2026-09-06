"""
سكريبت لتعبئة قاعدة البيانات بحساب أدمن جاهز + صفوف ومواد وأقسام فرعية ودروس تجريبية.
شغّله بعد تصفير قاعدة البيانات (أو حتى لو فيها بيانات جزئية — كل قسم يتفحص لحاله):

    python seed.py
"""

from app import create_app
from models import db, User, Grade, Subject, SubSection, Lesson

app = create_app()

# غيّر هذي القيم قبل التشغيل على بيئة إنتاج حقيقية —
# هذا الإيميل والباسورد هما اللي راح تسجل فيهم دخول للوحة الأدمن أول مرة.
ADMIN_EMAIL = "cnmvbn5@gmail.com"
ADMIN_PASSWORD = "ChangeThis123"
ADMIN_NAME = "أدمن مسار"

# كل صف فيه قائمة مواد، كل مادة فيها قائمة أقسام فرعية،
# كل قسم فرعي إله is_paid/price/duration_days خاص فيه لحاله.
SAMPLE_DATA = {
    "السادس إعدادي": [
        {
            "name": "الرياضيات", "icon": "📐",
            "subsections": [
                {
                    "name": "شرح المنهج", "icon": "📂", "is_paid": False,
                    "lessons": [
                        ("المعادلات التربيعية", "حل المعادلة بطريقة القانون العام", 18),
                        ("الدوال التربيعية", "رسم وتحليل الدالة التربيعية", 22),
                        ("المتباينات", "حل المتباينات من الدرجة الثانية", 15),
                    ],
                },
            ],
        },
        {
            "name": "الكيمياء", "icon": "🧪",
            "subsections": [
                {
                    "name": "شرح المنهج", "icon": "📂", "is_paid": False,
                    "lessons": [
                        ("التفاعلات الكيميائية", "أنواع التفاعلات وموازنة المعادلات", 20),
                        ("التفاعلات المزدوجة", "تفاعلات الإحلال المزدوج", 17),
                        ("الحسابات الكيميائية", "المول والكتلة المولية", 25),
                    ],
                },
            ],
        },
        {
            "name": "اللغة العربية", "icon": "📖",
            "subsections": [
                {
                    "name": "شرح المنهج", "icon": "📂", "is_paid": False,
                    "lessons": [
                        ("النحو — الإعراب", "إعراب الجمل الاسمية والفعلية", 14),
                        ("البلاغة", "التشبيه والاستعارة والكناية", 16),
                        ("مراجعة نهائية", "مراجعة شاملة لكل الوحدات", 30),
                    ],
                },
            ],
        },
        {
            # مثال على مادة فيها قسمين فرعيين مختلفين — وحد مجاني ووحد مدفوع،
            # كل وحد بسعر وتفعيل مستقل عن الثاني تماماً
            "name": "الفيزياء", "icon": "⚛️",
            "subsections": [
                {
                    "name": "قسم المراجعة العامة", "icon": "📂", "is_paid": False,
                    "lessons": [
                        ("مقدمة بالحركة", "مفاهيم أساسية بالحركة والسرعة", 12),
                    ],
                },
                {
                    "name": "قسم الأستاذ محمد جاسم", "icon": "👨‍🏫", "is_paid": True,
                    "price": 15000, "duration_days": 30,
                    "lessons": [
                        ("قوانين نيوتن", "القانون الأول والثاني والثالث للحركة", 19),
                        ("الطاقة والشغل", "مبدأ حفظ الطاقة", 21),
                    ],
                },
            ],
        },
    ],
}


def seed_admin():
    if User.query.filter_by(role="admin").first():
        print("⚠️  فيه حساب أدمن موجود أصلاً — تجاوزت هذا الجزء.")
        return

    admin = User(
        full_name=ADMIN_NAME,
        email=ADMIN_EMAIL,
        role="admin",
        is_verified=True,  # الأدمن ما يحتاج يمر بخطوة توثيق OTP
        grade_id=None,
    )
    admin.set_password(ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.commit()
    print(f"✅ تم إنشاء حساب الأدمن — الإيميل: {ADMIN_EMAIL} — الباسورد: {ADMIN_PASSWORD}")
    print("   لا تنسى تغيّر هذا الباسورد بعد أول تسجيل دخول.")


def seed_content():
    if Grade.query.first():
        print("⚠️  فيه صفوف/مواد موجودة أصلاً — تجاوزت هذا الجزء.")
        return

    for g_order, (grade_name, subjects) in enumerate(SAMPLE_DATA.items()):
        grade = Grade(name=grade_name, order=g_order)
        db.session.add(grade)
        db.session.flush()  # يحصل grade.id قبل الحفظ النهائي

        for s_order, s in enumerate(subjects):
            subject = Subject(
                grade_id=grade.id, name=s["name"], icon=s["icon"], order=s_order,
            )
            db.session.add(subject)
            db.session.flush()

            for sub_order, sub in enumerate(s["subsections"]):
                subsection = SubSection(
                    subject_id=subject.id,
                    name=sub["name"],
                    icon=sub.get("icon", "📂"),
                    is_paid=sub.get("is_paid", False),
                    price=sub.get("price"),
                    duration_days=sub.get("duration_days"),
                    order=sub_order,
                )
                db.session.add(subsection)
                db.session.flush()

                for l_order, (title, desc, minutes) in enumerate(sub["lessons"]):
                    lesson = Lesson(
                        subsection_id=subsection.id,
                        title=title,
                        description=desc,
                        duration_minutes=minutes,
                        order=l_order,
                        video_url=None,  # حط رابط فيديو حقيقي هنا لاحقاً
                    )
                    db.session.add(lesson)

    db.session.commit()
    print("✅ تم إدخال الصفوف والمواد والأقسام الفرعية والدروس التجريبية بنجاح")


def seed():
    with app.app_context():
        seed_admin()
        seed_content()


if __name__ == "__main__":
    seed()
