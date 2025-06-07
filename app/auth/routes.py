from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db
from app.auth.service import AuthService
from app.models import User
from .forms import RegistrationForm, LoginForm
from flask_login import login_user, logout_user, login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        success, error = AuthService.register(form.email.data, form.password.data)
        if not success:
            flash(error, "danger")
        else:
            flash("Registration complete! Please log in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = AuthService.authenticate(form.email.data, form.password.data)
        if user:
            login_user(user)
            flash(f"Welcome, {user.email}", "success")
            return redirect(url_for("main.dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
