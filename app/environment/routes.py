from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.auth.decorators import admin_required
from app import db
from app.models import Environment
from app.environment.forms import EnvironmentForm, DeleteForm
import logging

logger = logging.getLogger(__name__)
env_bp = Blueprint("environment", __name__, url_prefix="/environments")


@env_bp.route("/")
@login_required
@admin_required
def list_environments():
    """Display list of all environments for admin users"""
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
    """Allow admin to create a new environment"""
    form = EnvironmentForm()
    if form.validate_on_submit():
        env = Environment(
            name=form.name.data,
            owner_squad=form.owner_squad.data,
            created_by_email=current_user.email
        )
        db.session.add(env)
        db.session.commit()
        logger.info(f"Environment '{env.name}' created by {current_user.email}")
        flash(f"Environment '{env.name}' created by {current_user.email}.", "success")
        return redirect(url_for("environment.list_environments"))
    return render_template("environment/form.html", form=form)


@env_bp.route("/<int:env_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_environment(env_id):
    """Edit an existing environment"""
    env = Environment.query.get_or_404(env_id)
    form = EnvironmentForm(obj=env)
    form.env_id.data = str(env.id)  # Needed for uniqueness validation

    if form.validate_on_submit():
        env.name = form.name.data
        env.owner_squad = form.owner_squad.data
        db.session.commit()
        logger.info(f"Environment '{env.name}' updated by {current_user.email}")
        flash(f"Environment '{env.name}' updated.", "success")
        return redirect(url_for("environment.list_environments"))

    return render_template("environment/form.html", form=form, edit=True, env=env)


@env_bp.route("/<int:env_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_environment(env_id):
    """Delete an environment after confirmation"""
    env = Environment.query.get_or_404(env_id)
    db.session.delete(env)
    db.session.commit()
    logger.warning(f"Environment '{env.name}' deleted by {current_user.email}")
    flash(f"Environment '{env.name}' deleted.", "success")
    return redirect(url_for("environment.list_environments"))
