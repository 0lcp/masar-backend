from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request

from models import (
    db, User, Grade, Subject, SubSection, Lesson, Progress,
    LibraryFile, WazariFile, user_has_access,
    Quiz, Choice, QuizAttempt,
)

content_bp = Blueprint("content", __name__, url_prefix="/api/content")


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def _current_user_optional():
    """يرجع user لو فيه توكن صالح، وإلا None."""
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            return User.query.get(user_id)
    except Exception:
        pass
    return None


# ============ GRADES ============

@content_bp.route("/grades", methods=["GET"])
def list_grades():
    grades = Grade.query.order_by(Grade.order).all()
    return jsonify({"success": True, "grades": [g.to_dict() for g in grades]})


# ============ SUBJECTS ============

@content_bp.route("/subjects", methods=["GET"])
def list_subjects():
    """
    يرجع مواد صف معيّن. الصف يجي من ?grade_id=...، أو من صف
    المستخدم المسجّل دخوله لو ما انبعث grade_id (auth اختياري).
    """
    grade_id = request.args.get("grade_id", type=int)
    user = _current_user_optional()

    if not grade_id and user:
        grade_id = user.grade_id

    if not grade_id:
        return error("لازم تحدد الصف (grade_id)", status=400)

    subjects = Subject.query.filter_by(grade_id=grade_id).order_by(Subject.order).all()
    return jsonify({
        "success": True,
        "subjects": [s.to_dict() for s in subjects],
    })


@content_bp.route("/subjects/<int:subject_id>", methods=["GET"])
def get_subject(subject_id):
    """يرجع المادة مع أقسامها الفرعية، كل قسم فرعي فيه unlocked حسب وصول المستخدم."""
    subject = Subject.query.get(subject_id)
    if not subject:
        return error("المادة غير موجودة", status=404)

    user = _current_user_optional()
    user_id = user.id if user else None

    return jsonify({
        "success": True,
        "subject": subject.to_dict(include_subsections=True, user_id=user_id),
    })


# ============ SUBSECTIONS ============

@content_bp.route("/subsections/<int:subsection_id>", methods=["GET"])
def get_subsection(subsection_id):
    """يرجع القسم الفرعي مع دروسه لو كان مفتوح (مجاني أو عند المستخدم وصول فعّال)."""
    subsection = SubSection.query.get(subsection_id)
    if not subsection:
        return error("القسم غير موجود", status=404)

    user = _current_user_optional()
    user_id = user.id if user else None

    data = subsection.to_dict(include_lessons=True, user_id=user_id)

    if not data["unlocked"]:
        return jsonify({
            "success": True,
            "subsection": data,
            "locked": True,
            "message": "هذا القسم مدفوع — فعّل اشتراكك لتقدر توصل لدروسه",
        })

    if user:
        completed_ids = {
            p.lesson_id for p in Progress.query.filter_by(user_id=user.id, completed=True).all()
        }
        for lesson_dict in data["lessons"]:
            lesson_dict["completed"] = lesson_dict["id"] in completed_ids

    return jsonify({"success": True, "subsection": data})


# ============ LESSONS ============

@content_bp.route("/lessons/<int:lesson_id>", methods=["GET"])
def get_lesson(lesson_id):
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

    subsection = lesson.subsection
    if subsection.is_paid:
        user = _current_user_optional()
        if not user or not user_has_access(user.id, "subsection", subsection.id):
            return error("هذا الدرس بقسم مدفوع — فعّل اشتراكك أول", status=402)

    return jsonify({"success": True, "lesson": lesson.to_dict()})


@content_bp.route("/lessons/<int:lesson_id>/complete", methods=["POST"])
@jwt_required()
def complete_lesson(lesson_id):
    user_id = get_jwt_identity()
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

    subsection = lesson.subsection
    if subsection.is_paid and not user_has_access(user_id, "subsection", subsection.id):
        return error("هذا الدرس بقسم مدفوع — فعّل اشتراكك أول", status=402)

    progress = Progress.query.filter_by(user_id=user_id, lesson_id=lesson_id).first()
    if not progress:
        progress = Progress(user_id=user_id, lesson_id=lesson_id)
        db.session.add(progress)

    progress.completed = True
    progress.completed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"success": True, "message": "تسجّل الدرس كمكتمل", "progress": progress.to_dict()})


# ============ PROGRESS SUMMARY ============

@content_bp.route("/progress", methods=["GET"])
@jwt_required()
def my_progress():
    """
    ملخص تقدم الطالب: نسبة الإنجاز لكل قسم فرعي ضمن كل مادة بصفه،
    بالإضافة لإجمالي الدروس المكتملة عبر كل الأقسام المفتوحة.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return error("المستخدم غير موجود", status=404)

    if not user.grade_id:
        return jsonify({
            "success": True,
            "overall_percent": 0,
            "lessons_done": 0,
            "lessons_total": 0,
            "subjects": [],
        })

    subjects = Subject.query.filter_by(grade_id=user.grade_id).order_by(Subject.order).all()
    completed_ids = {
        p.lesson_id for p in Progress.query.filter_by(user_id=user_id, completed=True).all()
    }

    subjects_summary = []
    total_lessons = 0
    total_done = 0

    for subject in subjects:
        subsections_summary = []
        subj_lessons_total = 0
        subj_lessons_done = 0

        for sub in subject.subsections:
            locked = sub.is_paid and not user_has_access(user_id, "subsection", sub.id)
            lesson_ids = [l.id for l in sub.lessons]
            done = len([lid for lid in lesson_ids if lid in completed_ids])

            if not locked:
                total_lessons += len(lesson_ids)
                total_done += done
                subj_lessons_total += len(lesson_ids)
                subj_lessons_done += done

            pct = round((done / len(lesson_ids)) * 100) if lesson_ids and not locked else 0
            subsections_summary.append({
                "subsection_id": sub.id,
                "subsection_name": sub.name,
                "is_paid": sub.is_paid,
                "locked": locked,
                "lessons_done": done if not locked else 0,
                "lessons_total": len(lesson_ids),
                "percent": pct,
            })

        subjects_summary.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "icon": subject.icon,
            "lessons_done": subj_lessons_done,
            "lessons_total": subj_lessons_total,
            "percent": round((subj_lessons_done / subj_lessons_total) * 100) if subj_lessons_total else 0,
            "subsections": subsections_summary,
        })

    overall_pct = round((total_done / total_lessons) * 100) if total_lessons else 0

    return jsonify({
        "success": True,
        "overall_percent": overall_pct,
        "lessons_done": total_done,
        "lessons_total": total_lessons,
        "subjects": subjects_summary,
    })


# ============ QUIZZES (student-facing) ============

@content_bp.route("/lessons/<int:lesson_id>/quiz", methods=["GET"])
def get_lesson_quiz(lesson_id):
    """يرجع أسئلة الاختبار بدون كشف الجواب الصحيح."""
    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return error("الدرس غير موجود", status=404)

    subsection = lesson.subsection
    if subsection.is_paid:
        user = _current_user_optional()
        if not user or not user_has_access(user.id, "subsection", subsection.id):
            return error("هذا الاختبار بقسم مدفوع — فعّل اشتراكك أول", status=402)

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

    subsection = quiz.lesson.subsection
    if subsection.is_paid and not user_has_access(user_id, "subsection", subsection.id):
        return error("هذا الاختبار بقسم مدفوع — فعّل اشتراكك أول", status=402)

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


# ============ LIBRARY (الملازم والكتب) ============

@content_bp.route("/library", methods=["GET"])
def list_library_files():
    """
    يرجع ملفات المكتبة مفلترة حسب ?grade_id=...&subject_id=... (subject_id اختياري).
    كل ملف يرجع unlocked حسب وصول المستخدم إذا كان مدفوع.
    """
    grade_id = request.args.get("grade_id", type=int)
    subject_id = request.args.get("subject_id", type=int)

    if not grade_id:
        return error("لازم تحدد الصف (grade_id)", status=400)

    query = LibraryFile.query.filter_by(grade_id=grade_id)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)

    files = query.order_by(LibraryFile.uploaded_at.desc()).all()

    user = _current_user_optional()
    user_id = user.id if user else None

    return jsonify({
        "success": True,
        "files": [f.to_dict(user_id=user_id) for f in files],
    })


@content_bp.route("/library/<int:file_id>", methods=["GET"])
def get_library_file(file_id):
    file = LibraryFile.query.get(file_id)
    if not file:
        return error("الملف غير موجود", status=404)

    user = _current_user_optional()
    user_id = user.id if user else None
    data = file.to_dict(user_id=user_id)

    if not data["unlocked"]:
        return jsonify({
            "success": True,
            "file": data,
            "locked": True,
            "message": "هذا الملف مدفوع — فعّل اشتراكك لتقدر تفتحه",
        })

    return jsonify({"success": True, "file": data})


# ============ WAZARIYAT (الوزاريات) ============

@content_bp.route("/wazari", methods=["GET"])
def list_wazari_files():
    """
    يرجع أسئلة وزارية مفلترة حسب ?grade_id=...&subject_id=...&year=... (الأخيرين اختياريين).
    مجانية بالكامل حالياً.
    """
    grade_id = request.args.get("grade_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    year = request.args.get("year", type=int)

    if not grade_id:
        return error("لازم تحدد الصف (grade_id)", status=400)

    query = WazariFile.query.filter_by(grade_id=grade_id)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if year:
        query = query.filter_by(year=year)

    files = query.order_by(WazariFile.year.desc()).all()
    return jsonify({"success": True, "files": [f.to_dict() for f in files]})
