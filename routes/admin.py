import random
import string
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from models import (
    db, User, Grade, Subject, SubSection, Lesson,
    LibraryFile, WazariFile,
    RedemptionKey, UserAccess, user_has_access,
    Quiz, Question, Choice,
)
from utils.decorators import admin_required
from utils.github_upload import upload_file_to_github  # يحتاج ملف جديد — نسويه بعدين

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def generate_code(length=10):
    chars = string.ascii_uppercase + string.digits
    chunk = "".join(random.choices(chars, k=length))
    return f"MASAR-{chunk}"


def _get_content(content_type, content_id):
    if content_type == "subsection":
        return SubSection.query.get(content_id)
    if content_type == "library":
        return LibraryFile.query.get(content_id)
    return None


# ============ GRADES ============

@admin_bp.route("/grades", methods=["GET"])
@admin_required
def list_grades():
    grades = Grade.query.order_by(Grade.order).all()
    return jsonify({"success": True, "grades": [g.to_dict() for g in grades]})


@admin_bp.route("/grades", methods=["POST"])
@admin_required
def create_grade():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return error("اسم الصف مطلوب")
    if Grade.query.filter_by(name=name).first():
        return error("هذا الصف موجود أصلاً")

    max_order = db.session.query(db.func.max(Grade.order)).scalar() or 0
    grade = Grade(name=name, order=max_order + 1)
    db.session.add(grade)
    db.session.commit()
    return jsonify({"success": True, "grade": grade.to_dict()}), 201


@admin_bp.route("/grades/<int:grade_id>", methods=["PATCH"])
@admin_required
def update_grade(grade_id):
    grade = Grade.query.get(grade_id)
    if not grade:
        return error("الصف غير موجود", status=404)

    data = request.get_json(silent=True) or {}
    if "name" in data:
        grade.name = data["name"].strip()
    if "order" in data:
        grade.order = data["order"]

    db.session.commit()
    return jsonify({"success": True, "grade": grade.to_dict()})


@admin_bp.route("/grades/<int:grade_id>", methods=["DELETE"])
@admin_required
def delete_grade(grade_id):
    grade = Grade.query.get(grade_id)
    if not grade:
        return error("الصف غير موجود", status=404)
    db.session.delete(grade)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف الصف"})


# ============ SUBJECTS ============

@admin_bp.route("/subjects", methods=["GET"])
@admin_required
def list_all_subjects():
    grade_id = request.args.get("grade_id", type=int)
    query = Subject.query
    if grade_id:
        query = query.filter_by(grade_id=grade_id)
    subjects = query.order_by(Subject.grade_id, Subject.order).all()
    return jsonify({"success": True, "subjects": [s.to_dict(include_subsections=True) for s in subjects]})


@admin_bp.route("/subjects", methods=["POST"])
@admin_required
def create_subject():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    grade_id = data.get("grade_id")
    icon = data.get("icon") or "📘"

    grade = Grade.query.get(grade_id) if grade_id else None
    if not name:
        return error("اسم المادة مطلوب")
    if not grade:
        return error("اختر صف دراسي صحيح")

    max_order = db.session.query(db.func.max(Subject.order)).filter_by(grade_id=grade.id).scalar() or 0
    subject = Subject(name=name, grade_id=grade.id, icon=icon, order=max_order + 1)
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
    if "grade_id" in data:
        grade = Grade.query.get(data["grade_id"])
        if not grade:
            return error("الصف غير صحيح")
        subject.grade_id = grade.id

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


# ============ SUBSECTIONS ============

@admin_bp.route("/subsections", methods=["POST"])
@admin_required
def create_subsection():
    data = request.get_json(silent=True) or {}
    subject_id = data.get("subject_id")
    name = (data.get("name") or "").strip()
    is_paid = bool(data.get("is_paid", False))

    subject = Subject.query.get(subject_id) if subject_id else None
    if not subject:
        return error("المادة غير موجودة")
    if not name:
        return error("اسم القسم الفرعي مطلوب")

    if is_paid:
        price = data.get("price")
        if not isinstance(price, int) or price < 0:
            return error("حدد سعر صحيح للقسم المدفوع")

    max_order = db.session.query(db.func.max(SubSection.order)).filter_by(subject_id=subject.id).scalar() or 0
    subsection = SubSection(
        subject_id=subject.id,
        name=name,
        description=data.get("description"),
        icon=data.get("icon") or "📂",
        is_paid=is_paid,
        price=data.get("price") if is_paid else None,
        duration_days=data.get("duration_days") if is_paid else None,
        order=max_order + 1,
    )
    db.session.add(subsection)
    db.session.commit()
    return jsonify({"success": True, "subsection": subsection.to_dict()}), 201


@admin_bp.route("/subsections/<int:subsection_id>", methods=["PATCH"])
@admin_required
def update_subsection(subsection_id):
    """
    هذا الـ endpoint اللي يخلي الأدمن يغيّر سعر أو مدة أو حالة (مجاني/مدفوع)
    أي قسم فرعي أي وقت يريد.
    """
    subsection = SubSection.query.get(subsection_id)
    if not subsection:
        return error("القسم غير موجود", status=404)

    data = request.get_json(silent=True) or {}
    if "name" in data:
        subsection.name = data["name"].strip()
    if "description" in data:
        subsection.description = data["description"]
    if "icon" in data:
        subsection.icon = data["icon"]
    if "is_paid" in data:
        subsection.is_paid = bool(data["is_paid"])
        if not subsection.is_paid:
            subsection.price = None
            subsection.duration_days = None
    if "price" in data:
        subsection.price = data["price"]
    if "duration_days" in data:
        subsection.duration_days = data["duration_days"]

    db.session.commit()
    return jsonify({"success": True, "subsection": subsection.to_dict()})


@admin_bp.route("/subsections/<int:subsection_id>", methods=["DELETE"])
@admin_required
def delete_subsection(subsection_id):
    subsection = SubSection.query.get(subsection_id)
    if not subsection:
        return error("القسم غير موجود", status=404)
    db.session.delete(subsection)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف القسم الفرعي"})


# ============ LESSONS ============

@admin_bp.route("/lessons", methods=["POST"])
@admin_required
def create_lesson():
    data = request.get_json(silent=True) or {}
    subsection_id = data.get("subsection_id")
    title = (data.get("title") or "").strip()

    subsection = SubSection.query.get(subsection_id) if subsection_id else None
    if not subsection:
        return error("القسم الفرعي غير موجود")
    if not title:
        return error("عنوان الدرس مطلوب")

    max_order = db.session.query(db.func.max(Lesson.order)).filter_by(subsection_id=subsection.id).scalar() or 0
    lesson = Lesson(
        subsection_id=subsection.id,
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


# ============ LIBRARY (الملازم والكتب) ============

@admin_bp.route("/library", methods=["GET"])
@admin_required
def list_library_files():
    grade_id = request.args.get("grade_id", type=int)
    query = LibraryFile.query
    if grade_id:
        query = query.filter_by(grade_id=grade_id)
    files = query.order_by(LibraryFile.uploaded_at.desc()).all()
    return jsonify({"success": True, "files": [f.to_dict() for f in files]})


@admin_bp.route("/library/upload", methods=["POST"])
@admin_required
def upload_library_file():
    """
    يستقبل الملف (multipart/form-data) + بياناته، يرفعه لـ GitHub،
    ويخزّن الرابط بقاعدة البيانات.
    form fields: file, grade_id, subject_id (اختياري), title, is_paid, price, duration_days
    """
    if "file" not in request.files:
        return error("لازم ترفع ملف")

    file = request.files["file"]
    grade_id = request.form.get("grade_id", type=int)
    subject_id = request.form.get("subject_id", type=int)
    title = (request.form.get("title") or "").strip()
    is_paid = request.form.get("is_paid", "false").lower() == "true"

    grade = Grade.query.get(grade_id) if grade_id else None
    if not grade:
        return error("اختر صف دراسي صحيح")
    if not title:
        return error("عنوان الملف مطلوب")
    if file.filename == "":
        return error("الملف فاضي")

    try:
        file_bytes = file.read()
        file_url, size_kb = upload_file_to_github(file_bytes, file.filename, folder="library")
    except Exception as e:
        return error(f"فشل رفع الملف: {e}", status=500)

    library_file = LibraryFile(
        grade_id=grade.id,
        subject_id=subject_id,
        title=title,
        file_url=file_url,
        file_size_kb=size_kb,
        is_paid=is_paid,
        price=request.form.get("price", type=int) if is_paid else None,
        duration_days=request.form.get("duration_days", type=int) if is_paid else None,
    )
    db.session.add(library_file)
    db.session.commit()

    return jsonify({"success": True, "file": library_file.to_dict()}), 201


@admin_bp.route("/library/<int:file_id>", methods=["PATCH"])
@admin_required
def update_library_file(file_id):
    """تعديل بيانات الملف بدون إعادة رفعه (عنوان، سعر، مجاني/مدفوع)."""
    file = LibraryFile.query.get(file_id)
    if not file:
        return error("الملف غير موجود", status=404)

    data = request.get_json(silent=True) or {}
    if "title" in data:
        file.title = data["title"].strip()
    if "subject_id" in data:
        file.subject_id = data["subject_id"]
    if "is_paid" in data:
        file.is_paid = bool(data["is_paid"])
        if not file.is_paid:
            file.price = None
            file.duration_days = None
    if "price" in data:
        file.price = data["price"]
    if "duration_days" in data:
        file.duration_days = data["duration_days"]

    db.session.commit()
    return jsonify({"success": True, "file": file.to_dict()})


@admin_bp.route("/library/<int:file_id>", methods=["DELETE"])
@admin_required
def delete_library_file(file_id):
    file = LibraryFile.query.get(file_id)
    if not file:
        return error("الملف غير موجود", status=404)
    db.session.delete(file)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف الملف"})


# ============ WAZARIYAT (الوزاريات) ============

@admin_bp.route("/wazari", methods=["GET"])
@admin_required
def list_wazari_files():
    grade_id = request.args.get("grade_id", type=int)
    query = WazariFile.query
    if grade_id:
        query = query.filter_by(grade_id=grade_id)
    files = query.order_by(WazariFile.year.desc()).all()
    return jsonify({"success": True, "files": [f.to_dict() for f in files]})


@admin_bp.route("/wazari/upload", methods=["POST"])
@admin_required
def upload_wazari_file():
    """
    form fields: file, grade_id, subject_id (اختياري), year, title
    مجانية بالكامل حالياً.
    """
    if "file" not in request.files:
        return error("لازم ترفع ملف")

    file = request.files["file"]
    grade_id = request.form.get("grade_id", type=int)
    subject_id = request.form.get("subject_id", type=int)
    year = request.form.get("year", type=int)
    title = (request.form.get("title") or "").strip()

    grade = Grade.query.get(grade_id) if grade_id else None
    if not grade:
        return error("اختر صف دراسي صحيح")
    if not year:
        return error("حدد السنة")
    if not title:
        return error("عنوان الملف مطلوب")
    if file.filename == "":
        return error("الملف فاضي")

    try:
        file_bytes = file.read()
        file_url, size_kb = upload_file_to_github(file_bytes, file.filename, folder="wazari")
    except Exception as e:
        return error(f"فشل رفع الملف: {e}", status=500)

    wazari_file = WazariFile(
        grade_id=grade.id,
        subject_id=subject_id,
        year=year,
        title=title,
        file_url=file_url,
        file_size_kb=size_kb,
    )
    db.session.add(wazari_file)
    db.session.commit()

    return jsonify({"success": True, "file": wazari_file.to_dict()}), 201


@admin_bp.route("/wazari/<int:file_id>", methods=["PATCH"])
@admin_required
def update_wazari_file(file_id):
    file = WazariFile.query.get(file_id)
    if not file:
        return error("الملف غير موجود", status=404)

    data = request.get_json(silent=True) or {}
    if "title" in data:
        file.title = data["title"].strip()
    if "subject_id" in data:
        file.subject_id = data["subject_id"]
    if "year" in data:
        file.year = data["year"]

    db.session.commit()
    return jsonify({"success": True, "file": file.to_dict()})


@admin_bp.route("/wazari/<int:file_id>", methods=["DELETE"])
@admin_required
def delete_wazari_file(file_id):
    file = WazariFile.query.get(file_id)
    if not file:
        return error("الملف غير موجود", status=404)
    db.session.delete(file)
    db.session.commit()
    return jsonify({"success": True, "message": "تم حذف الملف"})


# ============ REDEMPTION KEYS ============

@admin_bp.route("/keys", methods=["GET"])
@admin_required
def list_keys():
    keys = RedemptionKey.query.order_by(RedemptionKey.created_at.desc()).limit(200).all()
    return jsonify({"success": True, "keys": [k.to_dict() for k in keys]})


@admin_bp.route("/keys/generate", methods=["POST"])
@admin_required
def generate_keys():
    """
    يولّد دفعة مفاتيح تفعيل جديدة مرتبطة بمحتوى معيّن —
    قسم فرعي (content_type='subsection') أو ملف مكتبة (content_type='library').
    body: { "content_type": "subsection", "content_id": 5, "count": 10 }
    """
    data = request.get_json(silent=True) or {}
    content_type = data.get("content_type")
    content_id = data.get("content_id")
    count = data.get("count", 1)

    if content_type not in ("subsection", "library"):
        return error("نوع المحتوى لازم يكون subsection أو library")

    content = _get_content(content_type, content_id)
    if not content:
        return error("المحتوى المحدد غير موجود")
    if not content.is_paid:
        return error("هذا المحتوى مجاني أصلاً — ما يحتاج مفتاح تفعيل")

    if not isinstance(count, int) or not (1 <= count <= 500):
        return error("عدد المفاتيح لازم يكون بين 1 و 500")

    new_keys = []
    for _ in range(count):
        code = generate_code()
        while RedemptionKey.query.filter_by(code=code).first():
            code = generate_code()
        key = RedemptionKey(code=code, content_type=content_type, content_id=content.id)
        db.session.add(key)
        new_keys.append(key)

    db.session.commit()
    content_name = getattr(content, "name", None) or getattr(content, "title", None)
    return jsonify({
        "success": True,
        "message": f"تولّد {count} مفتاح لـ{content_name}",
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
    ?search=...&grade_id=...
    """
    query = User.query.filter_by(role="student")

    search = request.args.get("search", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(User.full_name.ilike(like), User.email.ilike(like)))

    grade_id = request.args.get("grade_id", type=int)
    if grade_id:
        query = query.filter_by(grade_id=grade_id)

    students = query.order_by(User.created_at.desc()).limit(200).all()

    result = []
    for s in students:
        data = s.to_dict()
        active_accesses = [a for a in UserAccess.query.filter_by(user_id=s.id).all() if a.is_active]
        data["active_access_count"] = len(active_accesses)
        result.append(data)

    return jsonify({"success": True, "students": result})


@admin_bp.route("/students/<int:user_id>", methods=["GET"])
@admin_required
def get_student(user_id):
    student = User.query.get(user_id)
    if not student or student.role != "student":
        return error("الطالب غير موجود", status=404)

    accesses = UserAccess.query.filter_by(user_id=user_id).order_by(UserAccess.start_date.desc()).all()

    result = []
    for a in accesses:
        content = _get_content(a.content_type, a.content_id)
        result.append({
            **a.to_dict(),
            "content_name": (getattr(content, "name", None) or getattr(content, "title", None)) if content else None,
        })

    data = student.to_dict()
    data["access_list"] = result
    return jsonify({"success": True, "student": data})


@admin_bp.route("/students/<int:user_id>/grant-access", methods=["POST"])
@admin_required
def grant_access(user_id):
    """
    يعطي الأدمن صلاحية يفتح محتوى مدفوع لطالب يدوياً بدون مفتاح —
    مفيد لحالات خاصة (منحة، تجربة مجانية، حل مشكلة دفع).
    body: { "content_type": "subsection", "content_id": 5 }
    """
    student = User.query.get(user_id)
    if not student or student.role != "student":
        return error("الطالب غير موجود", status=404)

    data = request.get_json(silent=True) or {}
    content_type = data.get("content_type")
    content_id = data.get("content_id")

    content = _get_content(content_type, content_id)
    if not content:
        return error("المحتوى المحدد غير موجود")

    duration_days = getattr(content, "duration_days", None)

    existing = (
        UserAccess.query
        .filter_by(user_id=user_id, content_type=content_type, content_id=content_id)
        .first()
    )
    start_from = existing.end_date if (existing and existing.is_active and existing.end_date) else datetime.utcnow()
    end_date = (start_from + timedelta(days=duration_days)) if duration_days else None

    if existing:
        existing.end_date = end_date
        access = existing
    else:
        access = UserAccess(user_id=user_id, content_type=content_type, content_id=content_id, end_date=end_date)
        db.session.add(access)

    db.session.commit()

    content_name = getattr(content, "name", None) or getattr(content, "title", None)
    return jsonify({
        "success": True,
        "message": f"تم منح {student.full_name} وصول لـ{content_name}",
        "access": access.to_dict(),
    }), 201


@admin_bp.route("/students/<int:user_id>/role", methods=["PATCH"])
@admin_required
def update_student_role(user_id):
    """يرفّع طالب لأدمن، أو ينزّل أدمن لطالب عادي."""
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
    total_students = User.query.filter_by(role="student").count()
    active_access = len([a for a in UserAccess.query.all() if a.is_active])
    total_keys = RedemptionKey.query.count()
    used_keys = RedemptionKey.query.filter_by(is_used=True).count()

    return jsonify({
        "success": True,
        "total_students": total_students,
        "active_access": active_access,
        "total_keys": total_keys,
        "used_keys": used_keys,
    })
