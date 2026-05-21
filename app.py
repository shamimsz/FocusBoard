from flask import Flask, g, redirect, session, url_for

from db import close_db, get_db, init_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.projects import projects_bp
from routes.tasks import tasks_bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev-secret-change-me",
        DATABASE="focusboard.sqlite",
    )

    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = None
        if user_id is not None:
            g.user = get_db().execute(
                "SELECT id, username, email FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

    @app.cli.command("init-db")
    def init_db_command():
        init_db()
        print("Initialized the FocusBoard database.")

    @app.route("/")
    def index():
        if session.get("user_id") is None:
            return redirect(url_for("auth.login"))
        return redirect(url_for("dashboard.home"))

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)
    return app


app = create_app()


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
