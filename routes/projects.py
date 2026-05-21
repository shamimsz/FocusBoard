from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from db import get_db
from helpers import (
    PROJECT_COLORS,
    clean_text,
    current_user_id,
    get_project,
    log_activity,
    login_required,
    project_progress,
    today_iso,
)


projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


@projects_bp.route("/")
@login_required
def list_projects():
    show_archived = request.args.get("archived") == "1"
    projects = get_db().execute(
        """
        SELECT p.*,
            COUNT(t.id) AS task_count,
            SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count
        FROM projects p
        LEFT JOIN tasks t ON t.project_id = p.id
        WHERE p.user_id = ? AND p.archived = ?
        GROUP BY p.id
        ORDER BY p.updated_at DESC
        """,
        (current_user_id(), 1 if show_archived else 0),
    ).fetchall()
    cards = []
    for project in projects:
        item = dict(project)
        total = item["task_count"] or 0
        done = item["done_count"] or 0
        item["progress"] = round(done * 100 / total) if total else 0
        cards.append(item)
    return render_template(
        "projects/list.html",
        projects=cards,
        show_archived=show_archived,
        today=today_iso(),
    )


@projects_bp.route("/new", methods=("GET", "POST"))
@login_required
def create_project():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = clean_text(request.form.get("description"))
        deadline = clean_text(request.form.get("deadline"))
        color = request.form.get("color") or "blue"

        if not name:
            flash("Project name is required.", "danger")
        elif color not in PROJECT_COLORS:
            flash("Choose a valid project color.", "danger")
        else:
            cursor = get_db().execute(
                """
                INSERT INTO projects (user_id, name, description, color, deadline)
                VALUES (?, ?, ?, ?, ?)
                """,
                (current_user_id(), name, description, color, deadline),
            )
            log_activity(f"Created project: {name}", project_id=cursor.lastrowid)
            get_db().commit()
            flash("Project created.", "success")
            return redirect(url_for("projects.detail", project_id=cursor.lastrowid))

    return render_template("projects/form.html", project=None, colors=PROJECT_COLORS)


@projects_bp.route("/<int:project_id>")
@login_required
def detail(project_id):
    project = get_project(project_id)
    if project is None:
        flash("Project not found.", "danger")
        return redirect(url_for("projects.list_projects"))

    status = request.args.get("status") or ""
    priority = request.args.get("priority") or ""
    search = (request.args.get("q") or "").strip()

    conditions = ["t.project_id = ?", "t.user_id = ?"]
    params = [project_id, current_user_id()]
    if status:
        conditions.append("t.status = ?")
        params.append(status)
    if priority:
        conditions.append("t.priority = ?")
        params.append(priority)
    if search:
        conditions.append("(t.title LIKE ? OR t.notes LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    tasks = get_db().execute(
        f"""
        SELECT t.*,
            GROUP_CONCAT(l.name, ', ') AS labels
        FROM tasks t
        LEFT JOIN task_labels tl ON tl.task_id = t.id
        LEFT JOIN labels l ON l.id = tl.label_id
        WHERE {" AND ".join(conditions)}
        GROUP BY t.id
        ORDER BY
            CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            CASE WHEN t.due_date IS NULL OR t.due_date = '' THEN 1 ELSE 0 END,
            t.due_date ASC,
            t.created_at DESC
        """,
        params,
    ).fetchall()

    labels = get_db().execute(
        "SELECT * FROM labels WHERE user_id = ? ORDER BY name",
        (current_user_id(),),
    ).fetchall()

    columns = {"todo": [], "in_progress": [], "done": []}
    for task in tasks:
        columns[task["status"]].append(task)

    return render_template(
        "projects/detail.html",
        project=project,
        columns=columns,
        stats=project_progress(project_id),
        labels=labels,
        filters={"status": status, "priority": priority, "q": search},
        today=today_iso(),
    )


@projects_bp.route("/<int:project_id>/edit", methods=("GET", "POST"))
@login_required
def edit(project_id):
    project = get_project(project_id)
    if project is None:
        flash("Project not found.", "danger")
        return redirect(url_for("projects.list_projects"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = clean_text(request.form.get("description"))
        deadline = clean_text(request.form.get("deadline"))
        color = request.form.get("color") or "blue"

        if not name:
            flash("Project name is required.", "danger")
        elif color not in PROJECT_COLORS:
            flash("Choose a valid project color.", "danger")
        else:
            get_db().execute(
                """
                UPDATE projects
                SET name = ?, description = ?, deadline = ?, color = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                (name, description, deadline, color, project_id, current_user_id()),
            )
            log_activity(f"Updated project: {name}", project_id=project_id)
            get_db().commit()
            flash("Project updated.", "success")
            return redirect(url_for("projects.detail", project_id=project_id))

    return render_template("projects/form.html", project=project, colors=PROJECT_COLORS)


@projects_bp.route("/<int:project_id>/archive", methods=("POST",))
@login_required
def archive(project_id):
    project = get_project(project_id)
    if project is not None:
        archived = 0 if project["archived"] else 1
        get_db().execute(
            """
            UPDATE projects
            SET archived = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (archived, project_id, current_user_id()),
        )
        log_activity(
            f"{'Restored' if archived == 0 else 'Archived'} project: {project['name']}",
            project_id=project_id,
        )
        get_db().commit()
        flash("Project status changed.", "success")
    return redirect(url_for("projects.list_projects"))
