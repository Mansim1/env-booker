from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Regexp,
)

from app.auth.validators import no_sql_injection

# Registration form with email, password, confirm password
class RegistrationForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
            Length(max=120, message="Email must be 120 characters or fewer."),
            no_sql_injection,
        ],
        filters=[lambda x: x.strip() if x else None],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters long."),
            Regexp(
                r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@#$%^&+=!])[A-Za-z\d@#$%^&+=!]+$",
                message="Password must include a letter, number, and special character (@#$%^&+=!).",
            ),
        ],
    )

    confirm = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords do not match."),
        ],
    )

    submit = SubmitField("Sign Up")

# Login form with email and password
class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Email is required."),
            Email(message="Enter a valid email address."),
            Length(max=120, message="Email must be 120 characters or fewer."),
            no_sql_injection,
        ],
        filters=[lambda x: x.strip() if x else None],
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters."),
        ],
    )

    submit = SubmitField("Log In")
