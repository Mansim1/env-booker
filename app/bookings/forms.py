from flask_wtf import FlaskForm
from wtforms import DateTimeLocalField, SelectField, SelectMultipleField, SubmitField, ValidationError
from wtforms.validators import DataRequired
import logging

logger = logging.getLogger(__name__)

# Form for single booking creation
class BookingForm(FlaskForm):
    # Dropdown to select environment (e.g., "Integration A")
    environment = SelectField("Environment", coerce=int, validators=[DataRequired()])
    
    # Start datetime input field
    start = DateTimeLocalField(
        "Start",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
        render_kw={"type": "datetime-local"}  # Ensures HTML5 datetime picker UI
    )
    
    # End datetime input field
    end = DateTimeLocalField(
        "End",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
        render_kw={"type": "datetime-local"}
    )
    
    # Submit button for form
    submit = SubmitField("Book")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically populate environment dropdown from database
        from app.models import Environment
        self.environment.choices = [
            (e.id, e.name) for e in Environment.query.order_by(Environment.name)
        ]
        logger.debug("BookingForm initialized with environment choices: %s", self.environment.choices)


# Form for creating recurring (series) bookings
class SeriesBookingForm(FlaskForm):
    # Dropdown for environment selection
    environment = SelectField("Environment", coerce=int, validators=[DataRequired()])

    # Start datetime for the first recurring slot
    start_dt = DateTimeLocalField(
        "Start (first slot)",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Start Date & Time required.")],
        render_kw={"type": "datetime-local"},
    )

    # End datetime for the last recurring slot
    end_dt = DateTimeLocalField(
        "End (last slot)",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="End Date & Time required.")],
        render_kw={"type": "datetime-local"},
    )

    # Checkbox list to select days of the week for the recurring slots
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

    # Submit button for the recurring booking form
    submit = SubmitField("Book Series")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate environment choices from database
        from app.models import Environment
        self.environment.choices = [
            (e.id, e.name) for e in Environment.query.order_by(Environment.name)
        ]
        logger.debug("SeriesBookingForm initialized with environment choices: %s", self.environment.choices)

    # Custom validator to ensure end time is after start time
    def validate_end_dt(self, field):
        if self.start_dt.data and field.data <= self.start_dt.data:
            logger.warning("End datetime is not after start datetime.")
            raise ValidationError("End must be after Start.")

    # Custom validator to ensure at least one weekday is selected
    def validate_days_of_week(self, field):
        if not field.data:
            logger.warning("No weekdays selected for series booking.")
            raise ValidationError("Select at least one day of week.")
