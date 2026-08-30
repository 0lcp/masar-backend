from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request

from models import db, User, Subject, Lesson, Progress, user_has_active_subscription, Quiz, Choice, QuizAttempt

content_bp = Blueprint("content", __name__, url_prefix="/api/content")


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def _current_user_optional():
    """يرجع (user, has_subscription) لو فيه توكن صالح، وإلا (None, False)."""
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            user = User.query.get(user_id)
            if user:
                return user, user_has_active_subscription(user_id)
    except Exception:
        pass
    return None, False


@content_bp.route("/subjects", methods=["GET"])
def list_subjects():
    """
    Returns subjects for a grade.
    Grade comes from ?grade=... query param, or falls back to the logged-in
    user's grade if a valid token is sent (optional auth).
    Paid subjects are marked "unlocked": true/false depending on whether
    the requesting user has an active subscription.
    """
    grade = request.args.get("grade")
    user, has_sub = _current_user_optional()

    if not grade and user:
        grade = user.grade

    query = Subject.query
    if grade:
        query = query.filter_by(grade=grade)

    subjects = query.order_by(Subject.order).all()
    return jsonify({
        "success": True,
        "subjects": [s.to_dict(unlocked=has_sub) for s in subjects],
    })


@content_bp.route("/subjects/<int:subject_id>", methods=["GET"])
def get_subject(subject_id):
    subject = Subject.query.get(subject_id)
    if not subject:
        return error("المادة غير موجودة", status=404)

    user, has_sub = _current_user_optional()

    if subject.is_paid and not has_sub:
        return jsonify({
            "success": True,
            "subject": subject.to_dict(include_lessons=False, unlocked=False),
            "locked": True,
            "message": "هذي مادة مدفوعة — فعّل اشتراكك لتقدر توصل للدروس",
        })

    subject_dict = subject.to_dict(include_lessons=True, unlocked=True)

    if user:
        completed_ids = {
            p.lesson_id for p in Progress.query.filter_by(user_id=user.id, completed=True).all()
        }
        for lesson_dict in subject_dict["lessons"]:
            lesson_dict["completed"] = lesson_dict["id"] in completed_ids

    return jsonify({"success": True, "subject": subject_dict})


@content_bp.route("/lessons/<int:lesson_id>", methods=["GET"])
def get_lesson(lesson_id):
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

    if lesson.subject.is_paid:
        _, has_sub = _current_user_optional()
        if not has_sub:
            return error("هذا الدرس بمادة مدفوعة — فعّل اشتراكك أول", status=402)

    return jsonify({"success": True, "lesson": lesson.to_dict()})


@content_bp.route("/lessons/<int:lesson_id>/complete", methods=["POST"])
@jwt_required()
def complete_lesson(lesson_id):
    user_id = get_jwt_identity()
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

    if lesson.subject.is_paid and not user_has_active_subscription(user_id):
        return error("هذا الدرس بمادة مدفوعة — فعّل اشتراكك أول", status=402)

    progress = Progress.query.filter_by(user_id=user_id, lesson_id=lesson_id).first()
    if not progress:
        progress = Progress(user_id=user_id, lesson_id=lesson_id)
        db.session.add(progress)

    progress.completed = True
    progress.completed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"success": True, "message": "تسجّل الدرس كمكتمل", "progress": progress.to_dict()})


@content_bp.route("/progress", methods=["GET"])
@jwt_required()
def my_progress():
    """
    Returns overall progress summary for the logged-in student:
    completion % per subject, plus total lessons done.
    Locked (paid, not subscribed) subjects are included but marked locked,
    with lessons_total hidden as 0 done / not counted toward the overall %.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return error("المستخدم غير موجود", status=404)

    has_sub = user_has_active_subscription(user_id)
    subjects = Subject.query.filter_by(grade=user.grade).order_by(Subject.order).all()
    completed_ids = {
        p.lesson_id for p in Progress.query.filter_by(user_id=user_id, completed=True).all()
    }

    summary = []
    total_lessons = 0
    total_done = 0
    for subject in subjects:
        locked = subject.is_paid and not has_sub
        lesson_ids = [l.id for l in subject.lessons]
        done = len([lid for lid in lesson_ids if lid in completed_ids])

        if not locked:
            total_lessons += len(lesson_ids)
            total_done += done

        pct = round((done / len(lesson_ids)) * 100) if lesson_ids and not locked else 0
        summary.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "icon": subject.icon,
            "is_paid": subject.is_paid,
            "locked": locked,
            "lessons_done": done if not locked else 0,
            "lessons_total": len(lesson_ids) if not locked else len(lesson_ids),
            "percent": pct,
        })

    overall_pct = round((total_done / total_lessons) * 100) if total_lessons else 0

    return jsonify({
        "success": True,
        "overall_percent": overall_pct,
        "lessons_done": total_done,
        "lessons_total": total_lessons,
        "subjects": summary,
    })


# ============ QUIZZES (student-facing) ============

@content_bp.route("/lessons/<int:lesson_id>/quiz", methods=["GET"])
def get_lesson_quiz(lesson_id):
    """يرجع أسئلة الاختبار بدون كشف الجواب الصحيح."""
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

    if lesson.subject.is_paid:
        _, has_sub = _current_user_optional()
        if not has_sub:
            return error("هذا الاختبار بمادة مدفوعة — فعّل اشتراكك أول", status=402)

    quiz = Quiz.query.filter_by(lesson_id=lesson_id).first()
    if not quiz:
        return jsonify({"success": True, "quiz": None})

    return jsonify({"success": True, "quiz": quiz.to_dict(include_answers=False)})


@content_bp.route("/quizzes/<int:quiz_id>/submit", methods=["POST"])
@jwt_required()
def submit_quiz(quiz_id):
    """
    body: { "answers": [{"question_id": 1, "choice_id": 5}, ...] }
    يصحح تلقائياً ويرجع النتيجة + الأجوبة الصحيحة لكل سؤال.
    """
    user_id = get_jwt_identity()
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return error("الاختبار غير موجود", status=404)

    if quiz.lesson.subject.is_paid and not user_has_active_subscription(user_id):
        return error("هذا الاختبار بمادة مدفوعة — فعّل اشتراكك أول", status=402)

    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or []
    answer_map = {a.get("question_id"): a.get("choice_id") for a in answers}

    score = 0
    breakdown = []
    for question in quiz.questions:
        correct_choice = next((c for c in question.choices if c.is_correct), None)
        chosen_id = answer_map.get(question.id)
        is_right = correct_choice and chosen_id == correct_choice.id
        if is_right:
            score += 1
        breakdown.append({
            "question_id": question.id,
            "chosen_choice_id": chosen_id,
            "correct_choice_id": correct_choice.id if correct_choice else None,
            "is_correct": bool(is_right),
        })

    total = len(quiz.questions)
    attempt = QuizAttempt(user_id=user_id, quiz_id=quiz.id, score=score, total=total)
    db.session.add(attempt)
    db.session.commit()

    return jsonify({
        "success": True,
        "attempt": attempt.to_dict(),
        "breakdown": breakdown,
    })
