from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from datetime import datetime, timezone

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default="regular", nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password,
            method="pbkdf2:sha256",
            salt_length=8
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Environment(db.Model):
    __tablename__ = "environments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    owner_squad = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),  nullable=False)
    created_by_email = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f"<Environment {self.name} by {self.created_by_email}>"
    

class Booking(db.Model):
    __tablename__ = "bookings"
    id = db.Column(db.Integer, primary_key=True)
    environment_id = db.Column(
        db.Integer, db.ForeignKey("environments.id"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime, nullable=False)

    environment = db.relationship("Environment", backref="bookings")
    user = db.relationship("User", backref="bookings")


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    actor = db.relationship("User", backref="audit_entries")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # Optional extra information (e.g. environment name, IP, etc.)
    details = db.Column(db.Text, nullable=True)

