from flask_wtf import FlaskForm
from wtforms import SelectField, DateTimeField, SubmitField
from wtforms.validators import DataRequired, ValidationError

def parse_datetime(value):
    # WTForms DateTimeField will parse string to datetime
    return value

class BookingForm(FlaskForm):
    environment = SelectField("Environment", coerce=int, validators=[DataRequired()])
    start = DateTimeField(
        "Start", format="%Y-%m-%d %H:%M", validators=[DataRequired()]
    )
    end = DateTimeField(
        "End", format="%Y-%m-%d %H:%M", validators=[DataRequired()]
    )
    submit = SubmitField("Book")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # populate choices
        from app.models import Environment
        self.environment.choices = [
            (e.id, e.name) for e in Environment.query.order_by(Environment.name)
        ]
