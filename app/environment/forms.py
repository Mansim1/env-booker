from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Regexp, ValidationError
from app.auth.validators import no_sql_injection
from app.models import Environment


class EnvironmentForm(FlaskForm):
    env_id = HiddenField()
    name = StringField(
        "Name",
        validators=[
            DataRequired(message="Name cannot be blank."),
            Length(max=100, message="Name must be 100 characters or fewer."),
            no_sql_injection,
        ],
        filters=[lambda x: x.strip() if x else None],
    )
    owner_squad = StringField(
        "Owner Squad",
        validators=[
            DataRequired(message="Owner Squad is required."),
            Length(max=50, message="Owner Squad must be 50 characters or fewer."),
            Regexp(
                r"^[A-Za-z0-9 _-]+$", message="Owner Squad contains invalid characters."
            ),
        ],
        filters=[lambda x: x.strip() if x else None],
    )
    submit = SubmitField("Save")

    def validate_name(self, field):
        existing = Environment.query.filter_by(name=field.data).first()
        # If there is an existing env with that name, but it's not the one we're editing:
        if existing and (not self.env_id.data or int(self.env_id.data) != existing.id):
            field.errors[:] = []
            raise ValidationError("That environment name is already in use.")


class DeleteForm(FlaskForm):
    submit = SubmitField("Delete")
