import logging
from app.models import User
from app import db

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def register(email, password, role="regular"):
        """Registers a new user with email and hashed password"""
        if User.query.filter_by(email=email).first():
            return False, "That email is already registered, please log in."
        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        logger.debug(f"User added to DB: {email}")
        return True, None

    @staticmethod
    def authenticate(email, password):
        """Authenticates a user by email and password"""
        user = User.query.filter_by(email=email).first()
        logger.warning(f"Login- user found with email: {user.email}")
        if user and user.check_password(password):
            return user
        return None
