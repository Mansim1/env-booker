from app.models import User
from app import db
from werkzeug.security import generate_password_hash


class AuthService:
    @staticmethod
    def register(email, password):
        if User.query.filter_by(email=email).first():
            return False, "That email is already registered, please log in."
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return True, None

    @staticmethod
    def authenticate(email, password):
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            return user
        return None
