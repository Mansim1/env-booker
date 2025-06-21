import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()
login = LoginManager()
login.login_view = "auth.login"
login.login_message_category = "warning"

config_map = {
    "development": "config.DevelopmentConfig",
    "testing":     "config.TestingConfig",
    "production":  "config.ProductionConfig",
}

def create_app(_config_name=None):
    app = Flask(__name__, instance_relative_config=False)

    cfg_key = _config_name or os.getenv("FLASK_CONFIG", "development")
    app.config.from_object(config_map.get(cfg_key, config_map["development"]))

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set")

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    db.init_app(app)
    login.init_app(app)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)

    from app.models import User

    @login.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        print("Initialized the database.")

    @app.cli.command("drop-db")
    def drop_db():
        db.drop_all()
        print("Dropped the database.")

    from app.main.routes        import main_bp
    from app.auth.routes        import auth_bp
    from app.environment.routes import env_bp
    from app.bookings.routes    import bookings_bp
    from app.audit.routes       import audit_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(env_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(audit_bp)

    logging.basicConfig(
        level=logging.INFO if cfg_key == "production" else logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    return app
