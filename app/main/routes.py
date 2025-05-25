from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return render_template("main/index.html", user=current_user)
