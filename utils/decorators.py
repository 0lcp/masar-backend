from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from models import User


def admin_required(fn):
    """
    Decorator that only allows access to users with role == 'admin'.
    Use it stacked under @jwt_required-equivalent behavior (it verifies
    the JWT itself, so you don't need to add @jwt_required() separately).
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or user.role != "admin":
            return jsonify({"success": False, "error": "هذا القسم للأدمن بس"}), 403
        return fn(*args, **kwargs)
    return wrapper
