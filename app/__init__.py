from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

db = SQLAlchemy()
login = LoginManager()
login.login_view = "auth.login"

config_map = {
    "development": "config.DevelopmentConfig",
    "testing": "config.TestingConfig",
    "production": "config.ProductionConfig",
}


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=False)

    # choose config
    cfg = config_map.get(config_name, "config.DevelopmentConfig")
    app.config.from_object(cfg)

    # initialize extensions
    db.init_app(app)
    login.init_app(app)

    # now import User so it's available for the loader
    from app.models import User

    from app.main.routes import main_bp

    app.register_blueprint(main_bp)

    @login.user_loader
    def load_user(user_id):
        """Given *user_id*, return the associated User object."""
        return db.session.get(User, int(user_id))

    # register blueprints
    from app.auth.routes import auth_bp

    app.register_blueprint(auth_bp)

    @app.cli.command("init-db")
    def init_db():
        """Create all database tables."""
        db.create_all()
        print("✔️ Initialized the database.")

    # (later) register other blueprints: bookings, admin, etc.

    return app
