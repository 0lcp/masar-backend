"""
سكريبت لتعبئة قاعدة البيانات بصفوف ومواد وأقسام فرعية ودروس تجريبية.
شغّله مرة وحدة بعد تصفير قاعدة البيانات:

    python seed.py
"""

from app import create_app
from models import db, Grade, Subject, SubSection, Lesson

app = create_app()

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


def seed():
    with app.app_context():
        if Grade.query.first():
            print("⚠️  فيه بيانات موجودة أصلاً — صفّر قاعدة البيانات إذا تريد تبدأ من جديد.")
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


if __name__ == "__main__":
    seed()
