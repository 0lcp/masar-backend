from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()

GRADES = [
    "السادس ابتدائي",
    "الأول متوسط",
    "الثاني متوسط",
    "الثالث متوسط",
    "الرابع إعدادي",
    "الخامس إعدادي",
    "السادس إعدادي",
]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    grade = db.Column(db.String(60), nullable=True)

    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
            "grade": self.grade,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat(),
        }


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(60), nullable=False, index=True)
    icon = db.Column(db.String(10), default="📘")   # simple emoji icon, no external assets needed
    order = db.Column(db.Integer, default=0)

    lessons = db.relationship("Lesson", backref="subject", cascade="all, delete-orphan",
                               order_by="Lesson.order")

    def to_dict(self, include_lessons=False):
        data = {
            "id": self.id,
            "name": self.name,
            "grade": self.grade,
            "icon": self.icon,
            "lesson_count": len(self.lessons),
        }
        if include_lessons:
            data["lessons"] = [l.to_dict() for l in self.lessons]
        return data


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    video_url = db.Column(db.String(300), nullable=True)
    duration_minutes = db.Column(db.Integer, default=10)
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
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
