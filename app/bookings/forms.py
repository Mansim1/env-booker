# app/bookings/forms.py
from flask_wtf import FlaskForm
from wtforms import DateField, DateTimeLocalField, SelectField, SelectMultipleField, SubmitField, TimeField, ValidationError
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

class SeriesBookingForm(FlaskForm):
    environment = SelectField("Environment", coerce=int, validators=[DataRequired()])
    start_dt = DateTimeLocalField(
        "Start (first slot)",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Start Date & Time required.")],
        render_kw={"type": "datetime-local"},
    )
    end_dt = DateTimeLocalField(
        "End (last slot)",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="End Date & Time required.")],
        render_kw={"type": "datetime-local"},
    )
    days_of_week = SelectMultipleField(
        "Days of Week",
        choices=[
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        validators=[DataRequired(message="Select at least one day.")],
    )
    submit = SubmitField("Book Series")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import Environment
        self.environment.choices = [
            (e.id, e.name) for e in Environment.query.order_by(Environment.name)
        ]

    def validate_end_dt(self, field):
        if self.start_dt.data and field.data <= self.start_dt.data:
            raise ValidationError("End must be after Start.")

    def validate_days_of_week(self, field):
        if not field.data:
            raise ValidationError("Select at least one day of week.")
