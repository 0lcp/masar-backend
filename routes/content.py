from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, User, Subject, Lesson, Progress

content_bp = Blueprint("content", __name__, url_prefix="/api/content")


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


@content_bp.route("/subjects", methods=["GET"])
def list_subjects():
    """
    Returns subjects for a grade.
    Grade comes from ?grade=... query param, or falls back to the logged-in
    user's grade if a valid token is sent (optional auth).
    """
    grade = request.args.get("grade")

    if not grade:
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity as get_id
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_id()
            if user_id:
                user = User.query.get(user_id)
                if user:
                    grade = user.grade
        except Exception:
            pass

    query = Subject.query
    if grade:
        query = query.filter_by(grade=grade)

    subjects = query.order_by(Subject.order).all()
    return jsonify({"success": True, "subjects": [s.to_dict() for s in subjects]})


@content_bp.route("/subjects/<int:subject_id>", methods=["GET"])
def get_subject(subject_id):
    subject = Subject.query.get(subject_id)
    if not subject:
        return error("المادة غير موجودة", status=404)
    return jsonify({"success": True, "subject": subject.to_dict(include_lessons=True)})


@content_bp.route("/lessons/<int:lesson_id>", methods=["GET"])
def get_lesson(lesson_id):
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)
    return jsonify({"success": True, "lesson": lesson.to_dict()})


@content_bp.route("/lessons/<int:lesson_id>/complete", methods=["POST"])
@jwt_required()
def complete_lesson(lesson_id):
    user_id = get_jwt_identity()
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

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
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return error("المستخدم غير موجود", status=404)

    subjects = Subject.query.filter_by(grade=user.grade).order_by(Subject.order).all()
    completed_ids = {
        p.lesson_id for p in Progress.query.filter_by(user_id=user_id, completed=True).all()
    }

    summary = []
    total_lessons = 0
    total_done = 0
    for subject in subjects:
        lesson_ids = [l.id for l in subject.lessons]
        done = len([lid for lid in lesson_ids if lid in completed_ids])
        total_lessons += len(lesson_ids)
        total_done += done
        pct = round((done / len(lesson_ids)) * 100) if lesson_ids else 0
        summary.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "icon": subject.icon,
            "lessons_done": done,
            "lessons_total": len(lesson_ids),
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
