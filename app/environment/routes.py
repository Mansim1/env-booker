from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.auth.decorators import admin_required
from app import db
from app.models import AuditLog, Booking, Environment
from app.environment.forms import EnvironmentForm, DeleteForm
import logging

logger = logging.getLogger(__name__)
env_bp = Blueprint("environment", __name__, url_prefix="/environments")


@env_bp.route("/")
@login_required
@admin_required
def list_environments():
    """Display list of all environments for admin users, with stats."""
    # 1) the full list, alphabetically
    all_envs = Environment.query.order_by(Environment.name).all()

    # 2) stats for the cards
    total_envs     = Environment.query.count()
    total_bookings = Booking.query.count()

    # 3) distinct owner squads for the filter dropdown
    squads = [
        row[0]
        for row in db.session
                       .query(Environment.owner_squad)
                       .distinct()
                       .order_by(Environment.owner_squad)
                       .all()
    ]

    delete_form = DeleteForm()

    return render_template(
        "environment/list.html",
        environments=all_envs,
        delete_form=delete_form,
        total_envs=total_envs,
        total_bookings=total_bookings,
        squads=squads,
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
        msg = (
             f"Created environment “{env.name}”, "
             f"owned by squad “{env.owner_squad}” "
             f"via user {current_user.email}"
             )
        db.session.add(AuditLog(
             action="create_environment",
             actor_id=current_user.id,
             details=msg
         ))
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
        old_name  = env.name
        old_squad = env.owner_squad
        env.name = form.name.data
        env.owner_squad = form.owner_squad.data

        changes = []
        if old_name != env.name:
             changes.append(f"name “{old_name}”→“{env.name}”")
        if old_squad != env.owner_squad:
             changes.append(f"squad “{old_squad}”→“{env.owner_squad}”")
 
        msg = (
             f"Updated environment “{env.name}” (ID {env.id}): "
               "; ".join(changes)
         )
        db.session.add(AuditLog(
             action="update_environment",
             actor_id=current_user.id,
             details=msg
         ))

        db.session.commit()
        logger.info(f"Environment '{env.name}' updated by {current_user.email}")
        flash(f"Environment '{env.name}' updated.", "success")
        return redirect(url_for("environment.list_environments"))

    return render_template("environment/form.html", form=form, edit=True, env=env)


@env_bp.route("/<int:env_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_environment(env_id):
    """Delete an environment after confirmation, only if no bookings exist."""
    env = Environment.query.get_or_404(env_id)

    # 1) check for existing bookings
    count = Booking.query.filter_by(environment_id=env.id).count()
    if count:
        flash(
            f"Cannot delete environment '{env.name}' because there "
            f"{'is' if count==1 else 'are'} {count} existing booking"
            f"{'' if count==1 else 's'}.",
            "danger"
        )
        return redirect(url_for("environment.list_environments"))

    # 2) log and perform deletion
    msg = (
        f"Deleted environment “{env.name}” (ID {env.id}) "
        f"by user {current_user.email}"
    )
    db.session.add(AuditLog(
        action="delete_environment",
        actor_id=current_user.id,
        details=msg
    ))
    db.session.delete(env)
    db.session.commit()

    flash(f"Environment '{env.name}' deleted.", "success")
    logger.warning(f"Environment '{env.name}' deleted by {current_user.email}")
    return redirect(url_for("environment.list_environments"))
