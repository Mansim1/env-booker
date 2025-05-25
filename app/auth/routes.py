
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db
from app.models import User
from .forms import RegistrationForm, LoginForm
from flask_login import login_user, logout_user, login_required, current_user

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("That email is already registered, please log in.", "danger")
            return render_template("auth/register.html", form=form)
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Registration complete! Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash(f"Welcome, {user.email}", "success")
            return redirect(url_for("main.index"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))