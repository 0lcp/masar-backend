from datetime import datetime
from extensions import db  # استيراد db من extensions لمنع التكرار وأخطاء التهيئة
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"), nullable=True)

    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    role = db.Column(db.String(20), default="student", nullable=False)  # 'student' or 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ---- OTP Fields (إضافات الـ OTP وحماية التخمين) ----
    otp_code = db.Column(db.String(6), nullable=True)
    otp_purpose = db.Column(db.String(20), nullable=True)  # 'register' or 'reset'
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    otp_attempts = db.Column(db.Integer, default=0)

    grade = db.relationship("Grade")

    # ---- Password helpers ----
    def set_password(self, plain_password: str):
        self.password_hash = bcrypt.generate_password_hash(plain_password).decode("utf-8")

    def check_password(self, plain_password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, plain_password)

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "grade_id": self.grade_id,
            "grade": self.grade.name if self.grade else None,
            "is_verified": self.is_verified,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


class Grade(db.Model):
    """
    الصف الدراسي (مثلاً: السادس إعدادي). يديره الأدمن بالكامل من لوحة
    التحكم — إضافة/تعديل/حذف بدون أي تعديل بالكود.
    """
    __tablename__ = "grades"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False, unique=True)
    order = db.Column(db.Integer, default=0)

    subjects = db.relationship("Subject", backref="grade", cascade="all, delete-orphan",
                                order_by="Subject.order")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "order": self.order,
        }


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), default="📘")   # simple emoji icon, no external assets needed
    order = db.Column(db.Integer, default=0)

    subsections = db.relationship("SubSection", backref="subject", cascade="all, delete-orphan",
                                   order_by="SubSection.order")

    def to_dict(self, include_subsections=False, user_id=None):
        data = {
            "id": self.id,
            "grade_id": self.grade_id,
            "name": self.name,
            "icon": self.icon,
            "subsection_count": len(self.subsections),
        }
        if include_subsections:
            data["subsections"] = [s.to_dict(user_id=user_id) for s in self.subsections]
        return data


class SubSection(db.Model):
    """
    قسم فرعي داخل المادة (مثلاً: "قسم الأستاذ فلان" أو "قسم المراجعة").
    كل قسم فرعي مستقل بالكامل بالتسعير والتفعيل عن باقي الأقسام الفرعية،
    حتى لو كانت تحت نفس المادة.
    """
    __tablename__ = "subsections"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(10), default="📂")
    order = db.Column(db.Integer, default=0)

    is_paid = db.Column(db.Boolean, default=False, nullable=False)
    price = db.Column(db.Integer, nullable=True)            # دينار عراقي مثلاً — يتحكم فيه الأدمن
    currency = db.Column(db.String(10), default="IQD")
    duration_days = db.Column(db.Integer, nullable=True)     # مدة صلاحية الاشتراك باليوم

    lessons = db.relationship("Lesson", backref="subsection", cascade="all, delete-orphan",
                               order_by="Lesson.order")

    def to_dict(self, include_lessons=False, user_id=None):
        unlocked = (not self.is_paid) or (user_id and user_has_access(user_id, "subsection", self.id))
        data = {
            "id": self.id,
            "subject_id": self.subject_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "lesson_count": len(self.lessons),
            "is_paid": self.is_paid,
            "price": self.price,
            "currency": self.currency,
            "duration_days": self.duration_days,
            "unlocked": unlocked,
        }
        if include_lessons:
            data["lessons"] = [l.to_dict() for l in self.lessons] if unlocked else []
        return data


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    subsection_id = db.Column(db.Integer, db.ForeignKey("subsections.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    video_url = db.Column(db.String(300), nullable=True)
    duration_minutes = db.Column(db.Integer, default=10)
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "subsection_id": self.subsection_id,
            "title": self.title,
            "description": self.description,
            "video_url": self.video_url,
            "duration_minutes": self.duration_minutes,
            "order": self.order,
        }


class Progress(db.Model):
    """Tracks whether a given user has completed a given lesson."""
    __tablename__ = "progress"
    __table_args__ = (db.UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    lesson = db.relationship("Lesson")

    def to_dict(self):
        return {
            "lesson_id": self.lesson_id,
            "completed": self.completed,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class LibraryFile(db.Model):
    """
    قسم الملازم والكتب — ملفات PDF مصنّفة حسب الصف والمادة.
    ممكن تكون مجانية أو مدفوعة (مستقلة عن اشتراكات الأقسام الفرعية).
    """
    __tablename__ = "library_files"

    id = db.Column(db.Integer, primary_key=True)
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)   # رابط GitHub المباشر للملف
    file_size_kb = db.Column(db.Integer, nullable=True)

    is_paid = db.Column(db.Boolean, default=False, nullable=False)
    price = db.Column(db.Integer, nullable=True)
    currency = db.Column(db.String(10), default="IQD")
    duration_days = db.Column(db.Integer, nullable=True)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    grade = db.relationship("Grade")
    subject = db.relationship("Subject")

    def to_dict(self, user_id=None):
        unlocked = (not self.is_paid) or (user_id and user_has_access(user_id, "library", self.id))
        return {
            "id": self.id,
            "grade_id": self.grade_id,
            "grade": self.grade.name if self.grade else None,
            "subject_id": self.subject_id,
            "subject": self.subject.name if self.subject else None,
            "title": self.title,
            "file_url": self.file_url if unlocked else None,
            "file_size_kb": self.file_size_kb,
            "is_paid": self.is_paid,
            "price": self.price,
            "currency": self.currency,
            "unlocked": unlocked,
            "uploaded_at": self.uploaded_at.isoformat(),
        }


class WazariFile(db.Model):
    """
    قسم الوزاريات — نسخ أسئلة امتحانات وزارية سابقة، مصنّفة حسب
    الصف والمادة والسنة. مجانية بالكامل حالياً.
    """
    __tablename__ = "wazari_files"

    id = db.Column(db.Integer, primary_key=True)
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)
    file_size_kb = db.Column(db.Integer, nullable=True)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    grade = db.relationship("Grade")
    subject = db.relationship("Subject")

    def to_dict(self):
        return {
            "id": self.id,
            "grade_id": self.grade_id,
            "grade": self.grade.name if self.grade else None,
            "subject_id": self.subject_id,
            "subject": self.subject.name if self.subject else None,
            "year": self.year,
            "title": self.title,
            "file_url": self.file_url,
            "file_size_kb": self.file_size_kb,
            "uploaded_at": self.uploaded_at.isoformat(),
        }


class RedemptionKey(db.Model):
    """
    مفتاح تفعيل يولّده الأدمن ويعطيه للطالب بعد استلام الدفع.
    صار عام (polymorphic) — يشتغل على أي محتوى مدفوع: قسم فرعي
    (content_type='subsection') أو ملف مكتبة (content_type='library').
    """
    __tablename__ = "redemption_keys"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)

    content_type = db.Column(db.String(20), nullable=False)  # 'subsection' | 'library'
    content_id = db.Column(db.Integer, nullable=False)

    is_used = db.Column(db.Boolean, default=False, nullable=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    used_by = db.relationship("User")

    def _content_obj(self):
        if self.content_type == "subsection":
            return SubSection.query.get(self.content_id)
        if self.content_type == "library":
            return LibraryFile.query.get(self.content_id)
        return None

    def to_dict(self):
        content = self._content_obj()
        return {
            "id": self.id,
            "code": self.code,
            "content_type": self.content_type,
            "content_id": self.content_id,
            "content_name": getattr(content, "name", None) or getattr(content, "title", None),
            "is_used": self.is_used,
            "used_by_email": self.used_by.email if self.used_by else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "created_at": self.created_at.isoformat(),
        }


class UserAccess(db.Model):
    """وصول فعّال أو منتهي لطالب معيّن على محتوى مدفوع معيّن (قسم فرعي أو ملف مكتبة)."""
    __tablename__ = "user_access"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # 'subsection' | 'library'
    content_id = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True)  # null = وصول دائم (بدون انتهاء)

    @property
    def is_active(self):
        return self.end_date is None or datetime.utcnow() <= self.end_date

    def to_dict(self):
        return {
            "id": self.id,
            "content_type": self.content_type,
            "content_id": self.content_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
        }


def user_has_access(user_id: int, content_type: str, content_id: int) -> bool:
    """يتحقق هل عند المستخدم وصول فعّال حالياً على محتوى مدفوع معيّن."""
    access = (
        UserAccess.query
        .filter_by(user_id=user_id, content_type=content_type, content_id=content_id)
        .first()
    )
    if not access:
        return False
    return access.is_active


class Quiz(db.Model):
    """اختبار قصير مرتبط بدرس معيّن — درس وحد ممكن يكون عنده اختبار وحد بس."""
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)

    lesson = db.relationship("Lesson")
    questions = db.relationship("Question", backref="quiz", cascade="all, delete-orphan",
                                 order_by="Question.order")

    def to_dict(self, include_answers=False):
        return {
            "id": self.id,
            "lesson_id": self.lesson_id,
            "title": self.title,
            "question_count": len(self.questions),
            "questions": [q.to_dict(include_answers=include_answers) for q in self.questions],
        }


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, default=0)

    choices = db.relationship("Choice", backref="question", cascade="all, delete-orphan",
                               order_by="Choice.order")

    def to_dict(self, include_answers=False):
        return {
            "id": self.id,
            "text": self.text,
            "choices": [c.to_dict(include_answer=include_answers) for c in self.choices],
        }


class Choice(db.Model):
    __tablename__ = "choices"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    text = db.Column(db.String(300), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    order = db.Column(db.Integer, default=0)

    def to_dict(self, include_answer=False):
        data = {"id": self.id, "text": self.text}
        if include_answer:
            data["is_correct"] = self.is_correct
        return data


class QuizAttempt(db.Model):
    """نتيجة محاولة طالب لاختبار معيّن."""
    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)

    quiz = db.relationship("Quiz")

    def to_dict(self):
        pct = round((self.score / self.total) * 100) if self.total else 0
        return {
            "id": self.id,
            "quiz_id": self.quiz_id,
            "score": self.score,
            "total": self.total,
            "percent": pct,
            "taken_at": self.taken_at.isoformat(),
        }
