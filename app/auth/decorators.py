from functools import wraps
from flask import abort
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != "admin":
            abort(403, description="You don't have permission to view that page.")
        return f(*args, **kwargs)
    return decorated
