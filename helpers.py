from functools import wraps
from datetime import date

from flask import flash, redirect, session, url_for

from db import get_db


STATUSES = ("todo", "in_progress", "done")
PRIORITIES = ("low", "medium", "high")
PROJECT_COLORS = ("blue", "green", "orange", "purple", "pink", "slate")


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view


def clean_text(value):
    value = (value or "").strip()
    return value if value else None


def current_user_id():
    return session["user_id"]


def get_project(project_id):
    return get_db().execute(
        "SELECT * FROM projects WHERE id = ? AND user_id = ?",
        (project_id, current_user_id()),
    ).fetchone()


def get_task(task_id):
    return get_db().execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, current_user_id()),
    ).fetchone()


def project_progress(project_id):
    stats = get_db().execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
            SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS active
        FROM tasks
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    total = stats["total"] or 0
    done = stats["done"] or 0
    return {
        "total": total,
        "done": done,
        "active": stats["active"] or 0,
        "progress": round(done * 100 / total) if total else 0,
    }


def log_activity(action, project_id=None, task_id=None):
    get_db().execute(
        """
        INSERT INTO activity_log (user_id, project_id, task_id, action)
        VALUES (?, ?, ?, ?)
        """,
        (current_user_id(), project_id, task_id, action),
    )


def today_iso():
    return date.today().isoformat()
