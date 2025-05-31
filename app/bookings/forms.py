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
    start_date = DateField(
        "Start Date",
        format="%Y-%m-%d",
        validators=[DataRequired(message="Start Date is required.")],
        render_kw={"type": "date"},
    )
    end_date = DateField(
        "End Date",
        format="%Y-%m-%d",
        validators=[DataRequired(message="End Date is required.")],
        render_kw={"type": "date"},
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
        validators=[DataRequired(message="Select at least one day of week.")],
    )
    start_time = TimeField(
        "Start Time",
        format="%H:%M",
        validators=[DataRequired(message="Start Time is required.")],
        render_kw={"type": "time"},
    )
    end_time = TimeField(
        "End Time",
        format="%H:%M",
        validators=[DataRequired(message="End Time is required.")],
        render_kw={"type": "time"},
    )
    submit = SubmitField("Book Series")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import Environment
        self.environment.choices = [
            (e.id, e.name) for e in Environment.query.order_by(Environment.name)
        ]

    def validate_end_date(self, field):
        if self.start_date.data and field.data < self.start_date.data:
            raise ValidationError("End Date must be on or after Start Date.")

    def validate_end_time(self, field):
        if self.start_time.data and field.data <= self.start_time.data:
            raise ValidationError("End Time must be after Start Time.")
