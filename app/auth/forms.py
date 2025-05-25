from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, Regexp, ValidationError
)


class RegistrationForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
            Length(max=120, message="Email must be 120 characters or fewer.")
        ],
        filters=[lambda x: x.strip() if x else None],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters long."),
            Regexp(
                r"^[A-Za-z0-9@#$%^&+=!]+$",
                message="Password contains invalid characters."
            )
        ],
    )
    confirm = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords do not match.")
        ],
    )
    submit = SubmitField("Sign Up")

    def validate_email(self, field):
        # SQL-injection check
        forbidden = [";", "--", "/*", "*/", "@@"]
        for token in forbidden:
            if token in (field.data or ""):
                # wipe out earlier errors (e.g. the Email message)
                field.errors[:] = []
                # now raise only your SQL-injection message
                raise ValidationError("Invalid characters in field.")
            
class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
            Length(max=120, message='Email must be 120 characters or fewer.'),
            
        ],
        filters=[lambda x: x.strip() if x else None],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters.")
        ],
    )
    submit = SubmitField("Log In")

    def validate_email(self, field):
        # SQL-injection check
        forbidden = [";", "--", "/*", "*/", "@@"]
        for token in forbidden:
            if token in (field.data or ""):
                # wipe out earlier errors (e.g. the Email message)
                field.errors[:] = []
                # now raise only your SQL-injection message
                raise ValidationError("Invalid characters in field.")