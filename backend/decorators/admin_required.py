"""
Decorator: @admin_required — enforces admin role.

Wraps @login_required, then checks g.current_user.role == 'admin'.
Returns 403 if user is not an admin.
"""
from functools import wraps

from flask import g, jsonify

from decorators.login_required import login_required


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.current_user.role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)

    return decorated
