from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import logging

db = SQLAlchemy()
login = LoginManager()
login.login_view = "auth.login"

config_map = {
    "development": "config.DevelopmentConfig",
    "testing":     "config.TestingConfig",
    "production":  "config.ProductionConfig",
}

def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=False)

    # 1. Load config
    cfg = config_map.get(config_name, "config.DevelopmentConfig")
    app.config.from_object(cfg)

    # 2. Init extensions
    db.init_app(app)
    login.init_app(app)

    # 3. User loader (needs db & User model available)
    from app.models import User
    @login.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # 4. Register CLI command
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables."""
        db.create_all()
        print("✔️ Initialized the database.")

    @app.cli.command("drop-db")
    def drop_db():
        """Drop all database tables."""
        db.drop_all()
        print("✔️ Dropped the database.")

    # 5. Import and register Blueprints here (after db & login exist)
    from app.main.routes        import main_bp
    from app.auth.routes        import auth_bp
    from app.environment.routes import env_bp
    from app.bookings.routes import bookings_bp
    from app.audit.routes import audit_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(env_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(audit_bp)

    logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    return app
