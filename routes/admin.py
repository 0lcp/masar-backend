import random
import string
from datetime import datetime

from flask import Blueprint, request, jsonify

from models import db, Subject, Lesson, SubscriptionPlan, RedemptionKey, GRADES, Quiz, Question, Choice
from utils.decorators import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def generate_code(length=10):
    chars = string.ascii_uppercase + string.digits
    chunk = "".join(random.choices(chars, k=length))
    return f"MASAR-{chunk}"


# ============ SUBJECTS ============

@admin_bp.route("/subjects", methods=["GET"])
@admin_required
def list_all_subjects():
    subjects = Subject.query.order_by(Subject.grade, Subject.order).all()
    return jsonify({"success": True, "subjects": [s.to_dict(include_lessons=True) for s in subjects]})


@admin_bp.route("/subjects", methods=["POST"])
@admin_required
def create_subject():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    grade = data.get("grade") or ""
    icon = data.get("icon") or "📘"
    is_paid = bool(data.get("is_paid", False))

    if not name:
        return error("اسم المادة مطلوب")
    if grade not in GRADES:
        return error("اختر صف دراسي صحيح")

    max_order = db.session.query(db.func.max(Subject.order)).filter_by(grade=grade).scalar() or 0
    subject = Subject(name=name, grade=grade, icon=icon, is_paid=is_paid, order=max_order + 1)
    db.session.add(subject)
    db.session.commit()

    return jsonify({"success": True, "subject": subject.to_dict()}), 201


@admin_bp.route("/subjects/<int:subject_id>", methods=["PATCH"])
@admin_required
def update_subject(subject_id):
    subject = Subject.query.get(subject_id)
    if not subject:
        return error("المادة غير موجودة", status=404)

    data = request.get_json(silent=True) or {}
    if "name" in data:
        subject.name = data["name"].strip()
    if "icon" in data:
        subject.icon = data["icon"]
    if "is_paid" in data:
        subject.is_paid = bool(data["is_paid"])
    if "grade" in data and data["grade"] in GRADES:
        subject.grade = data["grade"]

    db.session.commit()
    return jsonify({"success": True, "subject": subject.to_dict()})


@admin_bp.route("/subjects/<int:subject_id>", methods=["DELETE"])
@admin_required
def delete_subject(subject_id):
    subject = Subject.query.get(subject_id)
    if not subject:
        return error("المادة غير موجودة", status=404)
    db.session.delete(subject)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف المادة"})


# ============ LESSONS ============

@admin_bp.route("/lessons", methods=["POST"])
@admin_required
def create_lesson():
    data = request.get_json(silent=True) or {}
    subject_id = data.get("subject_id")
    title = (data.get("title") or "").strip()

    subject = Subject.query.get(subject_id) if subject_id else None
    if not subject:
        return error("المادة غير موجودة")
    if not title:
        return error("عنوان الدرس مطلوب")

    max_order = db.session.query(db.func.max(Lesson.order)).filter_by(subject_id=subject.id).scalar() or 0
    lesson = Lesson(
        subject_id=subject.id,
        title=title,
        description=data.get("description"),
        video_url=data.get("video_url"),
        duration_minutes=data.get("duration_minutes", 10),
        order=max_order + 1,
    )
    db.session.add(lesson)
    db.session.commit()
    return jsonify({"success": True, "lesson": lesson.to_dict()}), 201


@admin_bp.route("/lessons/<int:lesson_id>", methods=["PATCH"])
@admin_required
def update_lesson(lesson_id):
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

    data = request.get_json(silent=True) or {}
    for field in ["title", "description", "video_url", "duration_minutes"]:
        if field in data:
            setattr(lesson, field, data[field])

    db.session.commit()
    return jsonify({"success": True, "lesson": lesson.to_dict()})


@admin_bp.route("/lessons/<int:lesson_id>", methods=["DELETE"])
@admin_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)
    db.session.delete(lesson)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف الدرس"})


# ============ SUBSCRIPTION PLANS ============

@admin_bp.route("/plans", methods=["GET"])
@admin_required
def list_plans():
    plans = SubscriptionPlan.query.order_by(SubscriptionPlan.duration_days).all()
    return jsonify({"success": True, "plans": [p.to_dict() for p in plans]})


@admin_bp.route("/plans", methods=["POST"])
@admin_required
def create_plan():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    duration_days = data.get("duration_days")
    price = data.get("price")

    if not name:
        return error("اسم الخطة مطلوب")
    if not isinstance(duration_days, int) or duration_days <= 0:
        return error("مدة الاشتراك لازم تكون رقم أكبر من صفر (باليوم)")
    if not isinstance(price, int) or price < 0:
        return error("السعر لازم يكون رقم صحيح")

    plan = SubscriptionPlan(name=name, duration_days=duration_days, price=price)
    db.session.add(plan)
    db.session.commit()
    return jsonify({"success": True, "plan": plan.to_dict()}), 201


@admin_bp.route("/plans/<int:plan_id>", methods=["PATCH"])
@admin_required
def update_plan(plan_id):
    """
    هذا الـ endpoint اللي يخلي الأدمن يرفع أو يخفض السعر أي وقت يريد،
    أو يغيّر مدة الخطة، أو يوقفها مؤقتاً (is_active = false) بدون حذفها.
    """
    plan = SubscriptionPlan.query.get(plan_id)
    if not plan:
        return error("الخطة غير موجودة", status=404)

    data = request.get_json(silent=True) or {}
    if "name" in data:
        plan.name = data["name"].strip()
    if "duration_days" in data:
        plan.duration_days = data["duration_days"]
    if "price" in data:
        plan.price = data["price"]
    if "is_active" in data:
        plan.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify({"success": True, "plan": plan.to_dict()})


@admin_bp.route("/plans/<int:plan_id>", methods=["DELETE"])
@admin_required
def delete_plan(plan_id):
    plan = SubscriptionPlan.query.get(plan_id)
    if not plan:
        return error("الخطة غير موجودة", status=404)
    db.session.delete(plan)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف الخطة"})


# ============ REDEMPTION KEYS ============

@admin_bp.route("/keys", methods=["GET"])
@admin_required
def list_keys():
    keys = RedemptionKey.query.order_by(RedemptionKey.created_at.desc()).limit(200).all()
    return jsonify({"success": True, "keys": [k.to_dict() for k in keys]})


@admin_bp.route("/keys/generate", methods=["POST"])
@admin_required
def generate_keys():
    """يولّد دفعة مفاتيح تفعيل جديدة مرتبطة بخطة معينة."""
    data = request.get_json(silent=True) or {}
    plan_id = data.get("plan_id")
    count = data.get("count", 1)

    plan = SubscriptionPlan.query.get(plan_id) if plan_id else None
    if not plan:
        return error("الخطة غير موجودة")
    if not isinstance(count, int) or not (1 <= count <= 500):
        return error("عدد المفاتيح لازم يكون بين 1 و 500")

    new_keys = []
    for _ in range(count):
        code = generate_code()
        while RedemptionKey.query.filter_by(code=code).first():
            code = generate_code()
        key = RedemptionKey(code=code, plan_id=plan.id)
        db.session.add(key)
        new_keys.append(key)

    db.session.commit()
    return jsonify({
        "success": True,
        "message": f"تولّد {count} مفتاح لخطة {plan.name}",
        "keys": [k.to_dict() for k in new_keys],
    }), 201


@admin_bp.route("/keys/<int:key_id>", methods=["DELETE"])
@admin_required
def delete_key(key_id):
    key = RedemptionKey.query.get(key_id)
    if not key:
        return error("المفتاح غير موجود", status=404)
    if key.is_used:
        return error("ما تكدر تحذف مفتاح مستخدم")
    db.session.delete(key)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف المفتاح"})


# ============ QUIZZES ============

@admin_bp.route("/lessons/<int:lesson_id>/quiz", methods=["GET"])
@admin_required
def get_lesson_quiz(lesson_id):
    quiz = Quiz.query.filter_by(lesson_id=lesson_id).first()
    if not quiz:
        return jsonify({"success": True, "quiz": None})
    return jsonify({"success": True, "quiz": quiz.to_dict(include_answers=True)})


@admin_bp.route("/lessons/<int:lesson_id>/quiz", methods=["POST"])
@admin_required
def create_quiz(lesson_id):
    """
    ينشئ اختبار لدرس معيّن دفعة وحدة — عنوان + قائمة أسئلة، كل سؤال معه
    خياراته وتحديد الجواب الصحيح.
    body: {
      "title": "اختبار الوحدة الأولى",
      "questions": [
        {"text": "...", "choices": [{"text": "...", "is_correct": true}, ...]}
      ]
    }
    """
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

    if Quiz.query.filter_by(lesson_id=lesson_id).first():
        return error("هذا الدرس عنده اختبار أصلاً — عدّله أو احذفه أول", status=409)

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    questions = data.get("questions") or []

    if not title:
        return error("عنوان الاختبار مطلوب")
    if not questions:
        return error("أضيف سؤال وحد على الأقل")

    quiz = Quiz(lesson_id=lesson_id, title=title)
    db.session.add(quiz)
    db.session.flush()

    for q_order, q in enumerate(questions):
        q_text = (q.get("text") or "").strip()
        choices = q.get("choices") or []
        if not q_text or len(choices) < 2:
            db.session.rollback()
            return error(f"السؤال رقم {q_order + 1} ناقص (يحتاج نص وخيارين على الأقل)")
        if not any(c.get("is_correct") for c in choices):
            db.session.rollback()
            return error(f"السؤال رقم {q_order + 1} لازم يكون فيه جواب صحيح وحد محدد")

        question = Question(quiz_id=quiz.id, text=q_text, order=q_order)
        db.session.add(question)
        db.session.flush()

        for c_order, c in enumerate(choices):
            choice = Choice(
                question_id=question.id,
                text=(c.get("text") or "").strip(),
                is_correct=bool(c.get("is_correct")),
                order=c_order,
            )
            db.session.add(choice)

    db.session.commit()
    return jsonify({"success": True, "quiz": quiz.to_dict(include_answers=True)}), 201


@admin_bp.route("/quizzes/<int:quiz_id>", methods=["DELETE"])
@admin_required
def delete_quiz(quiz_id):
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return error("الاختبار غير موجود", status=404)
    db.session.delete(quiz)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف الاختبار"})


# ============ STUDENTS ============

@admin_bp.route("/students", methods=["GET"])
@admin_required
def list_students():
    """
    قائمة الطلاب مع إمكانية بحث بالاسم أو الإيميل، وفلترة بالصف.
    ?search=...&grade=...
    """
    from models import User, user_has_active_subscription

    query = User.query.filter_by(role="student")

    search = request.args.get("search", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(User.full_name.ilike(like), User.email.ilike(like)))

    grade = request.args.get("grade", "").strip()
    if grade:
        query = query.filter_by(grade=grade)

    students = query.order_by(User.created_at.desc()).limit(200).all()

    result = []
    for s in students:
        data = s.to_dict()
        data["has_active_subscription"] = user_has_active_subscription(s.id)
        result.append(data)

    return jsonify({"success": True, "students": result})


@admin_bp.route("/students/<int:user_id>", methods=["GET"])
@admin_required
def get_student(user_id):
    from models import User, UserSubscription, user_has_active_subscription

    student = User.query.get(user_id)
    if not student or student.role != "student":
        return error("الطالب غير موجود", status=404)

    subs = UserSubscription.query.filter_by(user_id=user_id).order_by(UserSubscription.end_date.desc()).all()

    data = student.to_dict()
    data["has_active_subscription"] = user_has_active_subscription(user_id)
    data["subscriptions"] = [s.to_dict() for s in subs]
    return jsonify({"success": True, "student": data})


@admin_bp.route("/students/<int:user_id>/grant-subscription", methods=["POST"])
@admin_required
def grant_subscription(user_id):
    """
    يعطي الأدمن صلاحية يفعّل اشتراك لطالب يدوياً بدون مفتاح —
    مفيد لحالات خاصة (منحة، تجربة مجانية، حل مشكلة دفع).
    """
    from models import User, UserSubscription
    from datetime import timedelta

    student = User.query.get(user_id)
    if not student or student.role != "student":
        return error("الطالب غير موجود", status=404)

    data = request.get_json(silent=True) or {}
    plan_id = data.get("plan_id")
    plan = SubscriptionPlan.query.get(plan_id) if plan_id else None
    if not plan:
        return error("اختر خطة صحيحة")

    existing = (
        UserSubscription.query
        .filter_by(user_id=user_id)
        .filter(UserSubscription.end_date >= datetime.utcnow())
        .order_by(UserSubscription.end_date.desc())
        .first()
    )
    start_from = existing.end_date if existing else datetime.utcnow()
    end_date = start_from + timedelta(days=plan.duration_days)

    subscription = UserSubscription(user_id=user_id, plan_id=plan.id, end_date=end_date)
    db.session.add(subscription)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"تم منح {student.full_name} اشتراك {plan.name}",
        "subscription": subscription.to_dict(),
    }), 201


@admin_bp.route("/students/<int:user_id>/role", methods=["PATCH"])
@admin_required
def update_student_role(user_id):
    """يرفّع طالب لأدمن، أو ينزّل أدمن لطالب عادي."""
    from models import User

    target = User.query.get(user_id)
    if not target:
        return error("المستخدم غير موجود", status=404)

    data = request.get_json(silent=True) or {}
    new_role = data.get("role")
    if new_role not in ("student", "admin"):
        return error("الدور لازم يكون student أو admin")

    target.role = new_role
    db.session.commit()
    return jsonify({"success": True, "user": target.to_dict()})


# ============ STATS (overview) ============

@admin_bp.route("/stats", methods=["GET"])
@admin_required
def stats():
    from models import User, UserSubscription
    total_students = User.query.filter_by(role="student").count()
    active_subs = UserSubscription.query.filter(UserSubscription.end_date >= datetime.utcnow()).count()
    total_keys = RedemptionKey.query.count()
    used_keys = RedemptionKey.query.filter_by(is_used=True).count()

    return jsonify({
        "success": True,
        "total_students": total_students,
        "active_subscriptions": active_subs,
        "total_keys": total_keys,
        "used_keys": used_keys,
    })
