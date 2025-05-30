# app/bookings/forms.py
from flask_wtf import FlaskForm
from wtforms import DateTimeLocalField, SelectField, SubmitField
from wtforms.validators import DataRequired

class BookingForm(FlaskForm):
    environment = SelectField("Environment", coerce=int, validators=[DataRequired()])
    start = DateTimeLocalField(
        "Start",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
        render_kw={"type": "datetime-local"}
    )
    end = DateTimeLocalField(
        "End",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
        render_kw={"type": "datetime-local"}
    )
    submit = SubmitField("Book")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import Environment
        self.environment.choices = [
            (e.id, e.name) for e in Environment.query.order_by(Environment.name)
        ]
