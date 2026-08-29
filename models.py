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
    role = db.Column(db.String(20), default="student", nullable=False)  # 'student' or 'admin'
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
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(60), nullable=False, index=True)
    icon = db.Column(db.String(10), default="📘")   # simple emoji icon, no external assets needed
    order = db.Column(db.Integer, default=0)
    is_paid = db.Column(db.Boolean, default=False, nullable=False)  # ماده مجانية أو مدفوعة

    lessons = db.relationship("Lesson", backref="subject", cascade="all, delete-orphan",
                               order_by="Lesson.order")

    def to_dict(self, include_lessons=False, unlocked=True):
        data = {
            "id": self.id,
            "name": self.name,
            "grade": self.grade,
            "icon": self.icon,
            "lesson_count": len(self.lessons),
            "is_paid": self.is_paid,
            "unlocked": unlocked or not self.is_paid,
        }
        if include_lessons:
            data["lessons"] = [l.to_dict() for l in self.lessons] if (unlocked or not self.is_paid) else []
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


class SubscriptionPlan(db.Model):
    """
    خطة اشتراك (مثلاً: شهري، فصل دراسي، سنوي).
    السعر يتحكم فيه الأدمن من لوحة التحكم — يرفعه أو يخفضه أي وقت
    بدون أي تعديل بالكود.
    """
    __tablename__ = "subscription_plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)  # مدة الاشتراك باليوم
    price = db.Column(db.Integer, nullable=False)           # السعر (دينار عراقي مثلاً)
    currency = db.Column(db.String(10), default="IQD")
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # الخطة معروضة أو مخفية
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "duration_days": self.duration_days,
            "price": self.price,
            "currency": self.currency,
            "is_active": self.is_active,
        }


class RedemptionKey(db.Model):
    """
    مفتاح تفعيل يولّده الأدمن ويعطيه للطالب بعد ما يستلم الدفع
    (كاش، تحويل، إلخ). الطالب يدخل الكود بالتطبيق ليفعّل اشتراكه.
    """
    __tablename__ = "redemption_keys"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.id"), nullable=False)

    is_used = db.Column(db.Boolean, default=False, nullable=False)
    used_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship("SubscriptionPlan")
    used_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "plan_id": self.plan_id,
            "plan_name": self.plan.name if self.plan else None,
            "is_used": self.is_used,
            "used_by_email": self.used_by.email if self.used_by else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "created_at": self.created_at.isoformat(),
        }


class UserSubscription(db.Model):
    """اشتراك فعّال أو منتهي لطالب معيّن."""
    __tablename__ = "user_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.id"), nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)

    plan = db.relationship("SubscriptionPlan")

    @property
    def is_active(self):
        return datetime.utcnow() <= self.end_date

    def to_dict(self):
        return {
            "id": self.id,
            "plan_name": self.plan.name if self.plan else None,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "is_active": self.is_active,
        }


def user_has_active_subscription(user_id: int) -> bool:
    """يتحقق هل عند المستخدم أي اشتراك فعّال حالياً (تاريخ الانتهاء لسه ما وصل)."""
    sub = (
        UserSubscription.query
        .filter_by(user_id=user_id)
        .filter(UserSubscription.end_date >= datetime.utcnow())
        .first()
    )
    return sub is not None
