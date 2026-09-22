import os
import sys

from flask import Flask

from .db import close_db, init_db

if getattr(sys, "frozen", False):
    BASE = sys._MEIPASS
    DB_DIR = os.path.join(os.path.expanduser("~"), "sahan_fleet_data")
else:
    BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_DIR = None


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(BASE, "templates"),
        static_folder=os.path.join(BASE, "static"),
    )
    db_dir = DB_DIR or os.path.join(os.path.abspath("."), "instance")
    db_path = os.path.join(db_dir, "sahan_fleet.sqlite")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me-in-production"),
        DATABASE=db_path,
        APP_NAME="Sahan Fleet Transport Management System",
        REQUIRE_LOGIN=os.environ.get("REQUIRE_LOGIN", "1") == "1",
    )
    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

    os.makedirs(db_dir, exist_ok=True)

    app.teardown_appcontext(close_db)

    from .auth import bp as auth_bp
    from .dashboard import bp as dashboard_bp
    from .fleet import bp as fleet_bp
    from .operations import bp as operations_bp
    from .records import bp as records_bp
    from .exports import bp as exports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(fleet_bp)
    app.register_blueprint(operations_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(exports_bp)

    with app.app_context():
        init_db()

    from .db import init_db_command, reset_db_command

    app.cli.add_command(init_db_command)
    app.cli.add_command(reset_db_command)

    @app.before_request
    def _guard_login():
        from flask import g, redirect, request, session, url_for

        if app.config["REQUIRE_LOGIN"] is False:
            return
        g.user = session.get("user_id")
        if request.endpoint and request.endpoint.startswith("auth."):
            return
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))

    app.jinja_env.globals["APP_NAME"] = app.config["APP_NAME"]

    @app.context_processor
    def inject_now():
        from datetime import datetime

        return {"now": datetime.now()}

    return app
