from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Regexp, ValidationError
from app.auth.validators import no_sql_injection
from app.models import Environment


def strip_filter(val):
    """Trim leading/trailing whitespace if value exists."""
    return val.strip() if val else None


class EnvironmentForm(FlaskForm):
    """Form to create or edit an Environment record."""
    env_id = HiddenField()

    name = StringField(
        "Name",
        validators=[
            DataRequired(message="Name cannot be blank."),
            Length(max=100, message="Name must be 100 characters or fewer."),
            no_sql_injection,
        ],
        filters=[strip_filter],
    )

    owner_squad = StringField(
        "Owner Squad",
        validators=[
            DataRequired(message="Owner Squad is required."),
            Length(max=50, message="Owner Squad must be 50 characters or fewer."),
            Regexp(
                r"^[A-Za-z0-9 _-]+$",
                message="Owner Squad contains invalid characters."
            ),
        ],
        filters=[strip_filter],
    )

    submit = SubmitField("Save")

    def validate_name(self, field):
        """Ensure environment name is unique (except for current edit)."""
        existing = Environment.query.filter_by(name=field.data).first()
        if existing and (not self.env_id.data or int(self.env_id.data) != existing.id):
            field.errors[:] = []  # Clear default WTForms error
            raise ValidationError("That environment name is already in use.")


class DeleteForm(FlaskForm):
    """Simple confirmation form for deleting an environment."""
    submit = SubmitField("Delete")
