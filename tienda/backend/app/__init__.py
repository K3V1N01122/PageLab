"""Fábrica de la aplicación Flask."""
from __future__ import annotations

import logging

from flask import Flask, g, request

from app.config import get_config
from app.core import auth, csrf, ratelimit
from app.core.errors import register_error_handlers
from app.core.headers import apply_security_headers
from app.core.logging_setup import configure_logging


def create_app(env: str | None = None, overrides: dict | None = None) -> Flask:
    config = get_config(env)
    if config.ENV == "production":
        config.validate()
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config)
    if overrides:
        app.config.update(overrides)
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    configure_logging(app.config["LOG_LEVEL"])
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)

    from app import db
    db.init_app(app)

    @app.before_request
    def _before():
        g.user = None
        if request.path.startswith("/api/"):
            auth.load_current_user()
            csrf.verify_csrf()
            if request.method != "OPTIONS":
                ratelimit.check("global", app.config["RATE_LIMIT_DEFAULT"])

    @app.after_request
    def _after(response):
        origin = request.headers.get("Origin")
        if origin and origin in app.config["CORS_ALLOWED_ORIGINS"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token, Authorization, X-Client"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Vary"] = "Origin"
        csrf.ensure_csrf_cookie(response)
        return apply_security_headers(response)

    from app.api.v1 import api_v1
    from app.web.seo import web
    app.register_blueprint(api_v1)
    app.register_blueprint(web)
    register_error_handlers(app)

    if app.config.get("AUTO_MIGRATE") or app.config["TESTING"]:
        with app.app_context():
            from app.db import get_db
            from app.db.migrate import migrate
            migrate(get_db())

    logging.getLogger("app").info("Aplicación iniciada en modo %s", app.config["ENV"])
    return app
