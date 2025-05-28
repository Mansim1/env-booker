from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.auth.decorators import admin_required
from app import db
from app.models import Environment
from app.environment.forms import EnvironmentForm
from flask_login import current_user
from app.environment.forms import DeleteForm

env_bp = Blueprint("environment", __name__, url_prefix="/environments")

@env_bp.route("/")
@login_required
@admin_required
def list_environments():
    all_envs = Environment.query.order_by(Environment.name).all()
    delete_form = DeleteForm()
    return render_template(
        "environment/list.html",
        environments=all_envs,
        delete_form=delete_form
    )

@env_bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_environment():
    form = EnvironmentForm()
    if form.validate_on_submit():
        env = Environment(
            name=form.name.data,
            owner_squad=form.owner_squad.data,
            created_by_email=current_user.email
        )
        db.session.add(env)
        db.session.commit()
        flash(f"Environment '{env.name}' created by {env.created_by_email}.", "success")
        return redirect(url_for("environment.list_environments"))
    return render_template("environment/form.html", form=form)

@env_bp.route("/<int:env_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_environment(env_id):
    env = db.session.get(Environment, env_id)
    if env is None:
        abort(404)
    form = EnvironmentForm(obj=env)
    form.env_id.data = str(env.id)
    if form.validate_on_submit():
        env.name = form.name.data
        env.owner_squad = form.owner_squad.data
        db.session.commit()
        flash(f"Environment '{env.name}' updated.", "success")
        return redirect(url_for("environment.list_environments"))
    return render_template("environment/form.html", form=form, edit=True, env=env)

@env_bp.route("/<int:env_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_environment(env_id):
    env = db.session.get(Environment, env_id)
    if env is None:
        abort(404)
    db.session.delete(env)
    db.session.commit()
    flash(f"Environment '{env.name}' deleted.", "success")
    return redirect(url_for("environment.list_environments"))

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort
)
