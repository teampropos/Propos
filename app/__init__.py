import os
from flask import Flask
from flask_cors import CORS
from .extensions import db, migrate, bcrypt, jwt


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 60 * 60 * 24 * 7  # 7 days

    CORS(app, origins=["http://localhost:3000", "https://getpropos.com"])

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)

    from .auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    from .api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    from .webhooks.routes import webhooks_bp
    app.register_blueprint(webhooks_bp, url_prefix="/webhooks")

    return app
