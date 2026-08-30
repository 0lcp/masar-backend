from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, RedemptionKey, UserSubscription, SubscriptionPlan, user_has_active_subscription

subscription_bp = Blueprint("subscription", __name__, url_prefix="/api/subscription")


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


@subscription_bp.route("/plans", methods=["GET"])
def list_public_plans():
    """يشوفها أي زائر — الخطط المتاحة للاشتراك وسعرها الحالي."""
    plans = SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.duration_days).all()
    return jsonify({"success": True, "plans": [p.to_dict() for p in plans]})


@subscription_bp.route("/redeem", methods=["POST"])
@jwt_required()
def redeem_key():
    """
    الطالب يدخل كود المفتاح اللي استلمه بعد الدفع، ويتفعّل اشتراكه
    مباشرة — يمدد الاشتراك الحالي لو عنده وحد فعّال أصلاً.
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

    plan = key.plan
    if not plan or not plan.is_active:
        return error("هذي الخطة غير متاحة حالياً، تواصل مع الدعم")

    # لو عند الطالب اشتراك فعّال أصلاً، نمدده بدل ما نبدأ من جديد
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

    key.is_used = True
    key.used_by_id = user_id
    key.used_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"تم تفعيل اشتراك {plan.name} بنجاح 🎉",
        "subscription": subscription.to_dict(),
    })


@subscription_bp.route("/status", methods=["GET"])
@jwt_required()
def status():
    user_id = get_jwt_identity()
    is_active = user_has_active_subscription(user_id)

    latest = (
        UserSubscription.query
        .filter_by(user_id=user_id)
        .order_by(UserSubscription.end_date.desc())
        .first()
    )

    return jsonify({
        "success": True,
        "has_active_subscription": is_active,
        "subscription": latest.to_dict() if latest else None,
    })
