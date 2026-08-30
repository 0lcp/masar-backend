"""
سكريبت لتعبئة قاعدة البيانات بمواد ودروس تجريبية.
شغّله مرة وحدة بعد إعداد المشروع:

    python seed.py
"""

from app import create_app
from models import db, Subject, Lesson, SubscriptionPlan

app = create_app()

SAMPLE_DATA = {
    "السادس إعدادي": [
        {
            "name": "الرياضيات", "icon": "📐", "is_paid": False,
            "lessons": [
                ("المعادلات التربيعية", "حل المعادلة بطريقة القانون العام", 18),
                ("الدوال التربيعية", "رسم وتحليل الدالة التربيعية", 22),
                ("المتباينات", "حل المتباينات من الدرجة الثانية", 15),
            ],
        },
        {
            "name": "الكيمياء", "icon": "🧪", "is_paid": False,
            "lessons": [
                ("التفاعلات الكيميائية", "أنواع التفاعلات وموازنة المعادلات", 20),
                ("التفاعلات المزدوجة", "تفاعلات الإحلال المزدوج", 17),
                ("الحسابات الكيميائية", "المول والكتلة المولية", 25),
            ],
        },
        {
            "name": "اللغة العربية", "icon": "📖", "is_paid": False,
            "lessons": [
                ("النحو — الإعراب", "إعراب الجمل الاسمية والفعلية", 14),
                ("البلاغة", "التشبيه والاستعارة والكناية", 16),
                ("مراجعة نهائية", "مراجعة شاملة لكل الوحدات", 30),
            ],
        },
        {
            # مثال على مادة مدفوعة — غيّرها أو أضيف غيرها من لوحة الأدمن أي وقت
            "name": "الفيزياء المكثف", "icon": "⚛️", "is_paid": True,
            "lessons": [
                ("قوانين نيوتن", "القانون الأول والثاني والثالث للحركة", 19),
                ("الطاقة والشغل", "مبدأ حفظ الطاقة", 21),
            ],
        },
    ],
}

SAMPLE_PLANS = [
    {"name": "اشتراك شهري", "duration_days": 30, "price": 15000},
    {"name": "اشتراك فصل دراسي", "duration_days": 120, "price": 45000},
    {"name": "اشتراك سنوي", "duration_days": 365, "price": 120000},
]


def seed():
    with app.app_context():
        if Subject.query.first():
            print("⚠️  فيه بيانات موجودة أصلاً — احذف قاعدة البيانات (masar.db) إذا تريد تبدأ من جديد.")
        else:
            for grade, subjects in SAMPLE_DATA.items():
                for s_order, s in enumerate(subjects):
                    subject = Subject(
                        name=s["name"], grade=grade, icon=s["icon"],
                        is_paid=s.get("is_paid", False), order=s_order,
                    )
                    db.session.add(subject)
                    db.session.flush()  # يحصل subject.id قبل الحفظ النهائي

                    for l_order, (title, desc, minutes) in enumerate(s["lessons"]):
                        lesson = Lesson(
                            subject_id=subject.id,
                            title=title,
                            description=desc,
                            duration_minutes=minutes,
                            order=l_order,
                            video_url=None,  # حط رابط فيديو حقيقي هنا لاحقاً
                        )
                        db.session.add(lesson)

            db.session.commit()
            print("✅ تم إدخال المواد والدروس التجريبية بنجاح")

        if SubscriptionPlan.query.first():
            print("⚠️  فيه خطط اشتراك موجودة أصلاً — تجاوزناها.")
        else:
            for p in SAMPLE_PLANS:
                db.session.add(SubscriptionPlan(**p))
            db.session.commit()
            print("✅ تم إدخال خطط الاشتراك التجريبية (تكدرين تغيّرين أسعارها من لوحة الأدمن)")


if __name__ == "__main__":
    seed()
