from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, RedemptionKey, UserAccess, SubSection, LibraryFile

subscription_bp = Blueprint("subscription", __name__, url_prefix="/api/subscription")


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def _get_content(content_type, content_id):
    """يرجع الكائن (SubSection أو LibraryFile) حسب النوع، أو None لو غير معروف."""
    if content_type == "subsection":
        return SubSection.query.get(content_id)
    if content_type == "library":
        return LibraryFile.query.get(content_id)
    return None


@subscription_bp.route("/redeem", methods=["POST"])
@jwt_required()
def redeem_key():
    """
    الطالب يدخل كود المفتاح اللي استلمه بعد الدفع، ويتفعّل وصوله
    على القسم الفرعي أو الملف المرتبط بهذا المفتاح تحديداً — يمدد
    وصوله الحالي على نفس المحتوى لو كان عنده وحد فعّال أصلاً.
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().upper()

    if not code:
        return error("أدخل كود المفتاح")

    key = RedemptionKey.query.filter_by(code=code).first()
    if not key:
        return error("الكود غير صحيح")
    if key.is_used:
        return error("هذا الكود مستخدم من قبل")

    content = _get_content(key.content_type, key.content_id)
    if not content:
        return error("المحتوى المرتبط بهذا المفتاح لم يعد متاحاً، تواصل مع الدعم")

    duration_days = getattr(content, "duration_days", None)
    content_name = getattr(content, "name", None) or getattr(content, "title", None)

    # لو عند الطالب وصول فعّال أصلاً على نفس المحتوى، نمدده بدل ما نبدأ من جديد
    existing = (
        UserAccess.query
        .filter_by(user_id=user_id, content_type=key.content_type, content_id=key.content_id)
        .order_by(UserAccess.end_date.desc())
        .first()
    )

    if existing and existing.is_active and existing.end_date:
        start_from = existing.end_date
    else:
        start_from = datetime.utcnow()

    end_date = (start_from + timedelta(days=duration_days)) if duration_days else None

    if existing:
        existing.end_date = end_date
        access = existing
    else:
        access = UserAccess(
            user_id=user_id,
            content_type=key.content_type,
            content_id=key.content_id,
            end_date=end_date,
        )
        db.session.add(access)

    key.is_used = True
    key.used_by_id = user_id
    key.used_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"تم تفعيل وصولك لـ{content_name} بنجاح 🎉",
        "access": access.to_dict(),
    })


@subscription_bp.route("/status", methods=["GET"])
@jwt_required()
def status():
    """يرجع كل الأقسام/الملفات اللي عند الطالب وصول فعّال عليها حالياً."""
    user_id = get_jwt_identity()

    accesses = UserAccess.query.filter_by(user_id=user_id).all()
    active_accesses = [a for a in accesses if a.is_active]

    result = []
    for a in active_accesses:
        content = _get_content(a.content_type, a.content_id)
        result.append({
            **a.to_dict(),
            "content_name": (getattr(content, "name", None) or getattr(content, "title", None)) if content else None,
        })

    return jsonify({
        "success": True,
        "has_active_access": len(active_accesses) > 0,
        "active_accesses": result,
    })
