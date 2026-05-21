import sqlite3
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import get_db
from helpers import (
    PRIORITIES,
    PROJECT_COLORS,
    STATUSES,
    clean_text,
    current_user_id,
    get_project,
    get_task,
    log_activity,
    login_required,
)


tasks_bp = Blueprint("tasks", __name__)


def task_form_options():
    labels = get_db().execute(
        "SELECT * FROM labels WHERE user_id = ? ORDER BY name",
        (current_user_id(),),
    ).fetchall()
    return {"statuses": STATUSES, "priorities": PRIORITIES, "labels": labels}


def selected_label_ids():
    ids = []
    for value in request.form.getlist("labels"):
        try:
            ids.append(int(value))
        except ValueError:
            pass
    return ids


def sync_task_labels(task_id, label_ids):
    get_db().execute("DELETE FROM task_labels WHERE task_id = ?", (task_id,))
    for label_id in label_ids:
        owned = get_db().execute(
            "SELECT id FROM labels WHERE id = ? AND user_id = ?",
            (label_id, current_user_id()),
        ).fetchone()
        if owned:
            get_db().execute(
                "INSERT INTO task_labels (task_id, label_id) VALUES (?, ?)",
                (task_id, label_id),
            )


def parse_estimate(value):
    if not value:
        return None
    try:
        estimate = int(value)
    except ValueError:
        return -1
    return estimate if estimate >= 0 else -1


@tasks_bp.route("/projects/<int:project_id>/tasks/new", methods=("GET", "POST"))
@login_required
def create(project_id):
    project = get_project(project_id)
    if project is None:
        flash("Project not found.", "danger")
        return redirect(url_for("projects.list_projects"))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        notes = clean_text(request.form.get("notes"))
        status = request.form.get("status") or "todo"
        priority = request.form.get("priority") or "medium"
        due_date = clean_text(request.form.get("due_date"))
        estimate = request.form.get("estimated_minutes") or None

        if not title:
            flash("Task title is required.", "danger")
        elif status not in STATUSES or priority not in PRIORITIES:
            flash("Choose a valid status and priority.", "danger")
        else:
            estimate_value = parse_estimate(estimate)
            if estimate_value == -1:
                flash("Estimate must be a positive number of minutes.", "danger")
                return render_template(
                    "tasks/form.html",
                    task=None,
                    project=project,
                    selected_labels=set(),
                    **task_form_options(),
                )
            completed_at = date.today().isoformat() if status == "done" else None
            cursor = get_db().execute(
                """
                INSERT INTO tasks
                    (project_id, user_id, title, notes, status, priority,
                     due_date, estimated_minutes, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    current_user_id(),
                    title,
                    notes,
                    status,
                    priority,
                    due_date,
                    estimate_value,
                    completed_at,
                ),
            )
            sync_task_labels(cursor.lastrowid, selected_label_ids())
            get_db().execute(
                "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (project_id,),
            )
            log_activity(f"Created task: {title}", project_id=project_id, task_id=cursor.lastrowid)
            get_db().commit()
            flash("Task created.", "success")
            return redirect(url_for("projects.detail", project_id=project_id))

    return render_template(
        "tasks/form.html",
        task=None,
        project=project,
        selected_labels=set(),
        **task_form_options(),
    )


@tasks_bp.route("/tasks/<int:task_id>/edit", methods=("GET", "POST"))
@login_required
def edit(task_id):
    task = get_task(task_id)
    if task is None:
        flash("Task not found.", "danger")
        return redirect(url_for("dashboard.home"))

    project = get_project(task["project_id"])
    existing_labels = get_db().execute(
        "SELECT label_id FROM task_labels WHERE task_id = ?", (task_id,)
    ).fetchall()
    existing_label_ids = {row["label_id"] for row in existing_labels}

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        notes = clean_text(request.form.get("notes"))
        status = request.form.get("status") or "todo"
        priority = request.form.get("priority") or "medium"
        due_date = clean_text(request.form.get("due_date"))
        estimate = request.form.get("estimated_minutes") or None

        if not title:
            flash("Task title is required.", "danger")
        elif status not in STATUSES or priority not in PRIORITIES:
            flash("Choose a valid status and priority.", "danger")
        else:
            estimate_value = parse_estimate(estimate)
            if estimate_value == -1:
                flash("Estimate must be a positive number of minutes.", "danger")
                return render_template(
                    "tasks/form.html",
                    task=task,
                    project=project,
                    selected_labels=existing_label_ids,
                    **task_form_options(),
                )
            completed_at = task["completed_at"]
            if status == "done" and completed_at is None:
                completed_at = date.today().isoformat()
            if status != "done":
                completed_at = None

            get_db().execute(
                """
                UPDATE tasks
                SET title = ?, notes = ?, status = ?, priority = ?, due_date = ?,
                    estimated_minutes = ?, completed_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                (
                    title,
                    notes,
                    status,
                    priority,
                    due_date,
                    estimate_value,
                    completed_at,
                    task_id,
                    current_user_id(),
                ),
            )
            sync_task_labels(task_id, selected_label_ids())
            get_db().execute(
                "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (task["project_id"],),
            )
            log_activity(f"Updated task: {title}", project_id=task["project_id"], task_id=task_id)
            get_db().commit()
            flash("Task updated.", "success")
            return redirect(url_for("projects.detail", project_id=task["project_id"]))

    return render_template(
        "tasks/form.html",
        task=task,
        project=project,
        selected_labels=existing_label_ids,
        **task_form_options(),
    )


@tasks_bp.route("/tasks/<int:task_id>/status", methods=("POST",))
@login_required
def change_status(task_id):
    task = get_task(task_id)
    if task is None:
        flash("Task not found.", "danger")
        return redirect(url_for("dashboard.home"))

    new_status = request.form.get("status") or "todo"
    if new_status not in STATUSES:
        flash("Invalid status.", "danger")
    else:
        completed_at = date.today().isoformat() if new_status == "done" else None
        get_db().execute(
            """
            UPDATE tasks
            SET status = ?, completed_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (new_status, completed_at, task_id, current_user_id()),
        )
        get_db().execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (task["project_id"],),
        )
        log_activity(
            f"Moved task to {new_status.replace('_', ' ')}: {task['title']}",
            project_id=task["project_id"],
            task_id=task_id,
        )
        get_db().commit()
    return redirect(url_for("projects.detail", project_id=task["project_id"]))


@tasks_bp.route("/tasks/<int:task_id>/delete", methods=("POST",))
@login_required
def delete(task_id):
    task = get_task(task_id)
    if task is not None:
        project_id = task["project_id"]
        title = task["title"]
        get_db().execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, current_user_id()),
        )
        get_db().execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,),
        )
        log_activity(f"Deleted task: {title}", project_id=project_id)
        get_db().commit()
        flash("Task deleted.", "success")
        return redirect(url_for("projects.detail", project_id=project_id))
    return redirect(url_for("dashboard.home"))


@tasks_bp.route("/labels/new", methods=("POST",))
@login_required
def create_label():
    name = (request.form.get("name") or "").strip()
    color = request.form.get("color") or "slate"
    project_id = request.form.get("project_id")

    if not name:
        flash("Label name is required.", "danger")
    elif color not in PROJECT_COLORS:
        flash("Choose a valid label color.", "danger")
    else:
        try:
            get_db().execute(
                "INSERT INTO labels (user_id, name, color) VALUES (?, ?, ?)",
                (current_user_id(), name, color),
            )
            log_activity(f"Created label: {name}")
            get_db().commit()
            flash("Label created.", "success")
        except sqlite3.IntegrityError:
            flash("That label already exists.", "warning")

    if project_id:
        return redirect(url_for("projects.detail", project_id=project_id))
    return redirect(url_for("dashboard.home"))
