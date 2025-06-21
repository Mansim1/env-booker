import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_user, logout_user, login_required
from app import db
from app.auth.service import AuthService
from app.models import User
from .forms import RegistrationForm, LoginForm

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

logger = logging.getLogger(__name__)

@auth_bp.before_request
def redirect_if_logged_in():
    """Handles already logged in user"""
    if current_user.is_authenticated and request.endpoint in ["auth.login", "auth.register"]:
        return redirect(url_for("main.dashboard"))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handles user registration for regualr users"""
    form = RegistrationForm()
    if form.validate_on_submit():
        success, error = AuthService.register(form.email.data, form.password.data)
        if not success:
            flash(error, "danger")
            logger.warning(f"Registration failed for {form.email.data}: {error}")
        else:
            logout_user()
            flash("Registration complete! Please log in.", "success")
            logger.info(f"User registered successfully: {form.email.data}")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)

@auth_bp.route("/register-admin", methods=["GET", "POST"])
def registerAdmin():
    """Handles user registration for ADMIN"""
    form = RegistrationForm()
    if form.validate_on_submit():
        success, error = AuthService.register(form.email.data, form.password.data, "admin")
        if not success:
            flash(error, "danger")
            logger.warning(f"Registration failed for {form.email.data}: {error}")
        else:
            logout_user()
            flash("Registration complete! Please log in.", "success")
            logger.info(f"User registered successfully: {form.email.data}")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login"""
    form = LoginForm()
    if form.validate_on_submit():
        user = AuthService.authenticate(form.email.data, form.password.data)
        if user:
            login_user(user)
            flash(f"Welcome, {user.email}", "success")
            logger.info(f"User logged in: {user.email}")
            return redirect(url_for("main.dashboard"))
        flash("Invalid email or password.", "danger")
        logger.warning(f"Failed login attempt for: {form.email.data}")
    return render_template("auth/login.html", form=form)

@auth_bp.route("/logout")
@login_required
def logout():
    """Logs out the current user"""
    user_email = getattr(request, 'user_email', 'Unknown')
    logout_user()
    flash("You have been logged out.", "info")
    logger.info(f"User logged out")
    return redirect(url_for("auth.login"))
