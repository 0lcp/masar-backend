"""
سكريبت لتعبئة قاعدة البيانات بمواد ودروس تجريبية.
شغّله مرة وحدة بعد إعداد المشروع:

    python seed.py
"""

from app import create_app
from models import db, Subject, Lesson

app = create_app()

SAMPLE_DATA = {
    "السادس إعدادي": [
        {
            "name": "الرياضيات", "icon": "📐",
            "lessons": [
                ("المعادلات التربيعية", "حل المعادلة بطريقة القانون العام", 18),
                ("الدوال التربيعية", "رسم وتحليل الدالة التربيعية", 22),
                ("المتباينات", "حل المتباينات من الدرجة الثانية", 15),
            ],
        },
        {
            "name": "الكيمياء", "icon": "🧪",
            "lessons": [
                ("التفاعلات الكيميائية", "أنواع التفاعلات وموازنة المعادلات", 20),
                ("التفاعلات المزدوجة", "تفاعلات الإحلال المزدوج", 17),
                ("الحسابات الكيميائية", "المول والكتلة المولية", 25),
            ],
        },
        {
            "name": "اللغة العربية", "icon": "📖",
            "lessons": [
                ("النحو — الإعراب", "إعراب الجمل الاسمية والفعلية", 14),
                ("البلاغة", "التشبيه والاستعارة والكناية", 16),
                ("مراجعة نهائية", "مراجعة شاملة لكل الوحدات", 30),
            ],
        },
        {
            "name": "الفيزياء", "icon": "⚛️",
            "lessons": [
                ("قوانين نيوتن", "القانون الأول والثاني والثالث للحركة", 19),
                ("الطاقة والشغل", "مبدأ حفظ الطاقة", 21),
            ],
        },
    ],
}


def seed():
    with app.app_context():
        if Subject.query.first():
            print("⚠️  فيه بيانات موجودة أصلاً — احذف قاعدة البيانات (masar.db) إذا تريد تبدأ من جديد.")
            return

        for grade, subjects in SAMPLE_DATA.items():
            for s_order, s in enumerate(subjects):
                subject = Subject(name=s["name"], grade=grade, icon=s["icon"], order=s_order)
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
        print("✅ تم إدخال البيانات التجريبية بنجاح")


if __name__ == "__main__":
    seed()
