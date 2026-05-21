import csv
from datetime import date, datetime
from io import StringIO

from flask import Blueprint, Response, render_template, session

from db import get_db
from helpers import login_required, today_iso


dashboard_bp = Blueprint("dashboard", __name__)


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def score_task(task, today):
    score = 0
    reasons = []

    priority_points = {"high": 40, "medium": 25, "low": 10}
    points = priority_points.get(task["priority"], 0)
    score += points
    reasons.append(f"{task['priority']} priority adds {points} points")

    due_date = parse_date(task["due_date"])
    if due_date is None:
        reasons.append("no due date, so no deadline urgency added")
    else:
        days_left = (due_date - today).days
        if days_left < 0:
            score += 50
            reasons.append("overdue tasks add 50 points")
        elif days_left == 0:
            score += 40
            reasons.append("due today adds 40 points")
        elif days_left <= 3:
            score += 25
            reasons.append("due in the next 3 days adds 25 points")
        elif days_left <= 7:
            score += 15
            reasons.append("due this week adds 15 points")
        else:
            reasons.append("deadline is not urgent yet")

    if task["status"] == "in_progress":
        score += 15
        reasons.append("already in progress adds 15 points")
    elif task["status"] == "todo":
        score += 5
        reasons.append("not started adds 5 points")

    estimate = task["estimated_minutes"] or 0
    if 0 < estimate <= 30:
        score += 10
        reasons.append("quick task adds 10 points")
    elif estimate >= 180:
        score -= 5
        reasons.append("large task subtracts 5 points so it can be planned carefully")

    return {
        "task": task,
        "score": score,
        "reasons": reasons,
    }


@dashboard_bp.route("/dashboard")
@login_required
def home():
    db = get_db()
    today = today_iso()
    summary = db.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
            SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS active,
            SUM(CASE WHEN status != 'done' AND due_date < ? THEN 1 ELSE 0 END) AS overdue,
            SUM(CASE WHEN status != 'done' AND due_date = ? THEN 1 ELSE 0 END) AS due_today,
            SUM(COALESCE(estimated_minutes, 0)) AS estimated_minutes
        FROM tasks
        WHERE user_id = ?
        """,
        (today, today, session["user_id"]),
    ).fetchone()

    projects = db.execute(
        """
        SELECT p.*,
            COUNT(t.id) AS task_count,
            SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count
        FROM projects p
        LEFT JOIN tasks t ON t.project_id = p.id
        WHERE p.user_id = ? AND p.archived = 0
        GROUP BY p.id
        ORDER BY
            CASE WHEN p.deadline IS NULL OR p.deadline = '' THEN 1 ELSE 0 END,
            p.deadline ASC,
            p.updated_at DESC
        """,
        (session["user_id"],),
    ).fetchall()

    upcoming = db.execute(
        """
        SELECT t.*, p.name AS project_name, p.color AS project_color
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE t.user_id = ? AND t.status != 'done'
        ORDER BY
            CASE WHEN t.due_date IS NULL OR t.due_date = '' THEN 1 ELSE 0 END,
            t.due_date ASC,
            CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END
        LIMIT 8
        """,
        (session["user_id"],),
    ).fetchall()

    activity = db.execute(
        """
        SELECT action, created_at
        FROM activity_log
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 8
        """,
        (session["user_id"],),
    ).fetchall()

    weekly = db.execute(
        """
        SELECT substr(completed_at, 1, 10) AS day, COUNT(*) AS completed
        FROM tasks
        WHERE user_id = ? AND completed_at IS NOT NULL
        GROUP BY substr(completed_at, 1, 10)
        ORDER BY day DESC
        LIMIT 7
        """,
        (session["user_id"],),
    ).fetchall()

    project_cards = []
    for project in projects:
        item = dict(project)
        total = item["task_count"] or 0
        done = item["done_count"] or 0
        item["progress"] = round(done * 100 / total) if total else 0
        project_cards.append(item)

    return render_template(
        "dashboard/home.html",
        summary=summary,
        projects=project_cards,
        upcoming=upcoming,
        activity=activity,
        weekly=list(reversed(weekly)),
        today=today,
    )


@dashboard_bp.route("/smart-plan")
@login_required
def smart_plan():
    today = date.today()
    today_string = today.isoformat()
    db = get_db()

    tasks = db.execute(
        """
        SELECT t.*, p.name AS project_name, p.color AS project_color
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE t.user_id = ? AND t.status != 'done' AND p.archived = 0
        ORDER BY t.created_at DESC
        """,
        (session["user_id"],),
    ).fetchall()

    recommendations = sorted(
        [score_task(task, today) for task in tasks],
        key=lambda item: item["score"],
        reverse=True,
    )

    project_risks = db.execute(
        """
        SELECT p.id, p.name, p.color, p.deadline,
            COUNT(t.id) AS total_tasks,
            SUM(CASE WHEN t.status != 'done' THEN 1 ELSE 0 END) AS open_tasks,
            SUM(CASE WHEN t.status != 'done' AND t.due_date < ? THEN 1 ELSE 0 END) AS overdue_tasks,
            SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_tasks
        FROM projects p
        LEFT JOIN tasks t ON t.project_id = p.id
        WHERE p.user_id = ? AND p.archived = 0
        GROUP BY p.id
        HAVING open_tasks > 0
        ORDER BY overdue_tasks DESC, open_tasks DESC, p.deadline ASC
        LIMIT 5
        """,
        (today_string, session["user_id"]),
    ).fetchall()

    workload = db.execute(
        """
        SELECT
            COUNT(*) AS task_count,
            SUM(COALESCE(estimated_minutes, 0)) AS estimated_minutes
        FROM tasks
        WHERE user_id = ?
          AND status != 'done'
          AND due_date >= ?
          AND due_date <= date(?, '+7 days')
        """,
        (session["user_id"], today_string, today_string),
    ).fetchone()

    return render_template(
        "dashboard/smart_plan.html",
        recommendations=recommendations[:8],
        project_risks=project_risks,
        workload=workload,
        today=today_string,
    )


@dashboard_bp.route("/calendar")
@login_required
def calendar():
    today = today_iso()
    tasks = get_db().execute(
        """
        SELECT t.*, p.name AS project_name, p.color AS project_color
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE t.user_id = ? AND t.status != 'done'
        ORDER BY
            CASE WHEN t.due_date IS NULL OR t.due_date = '' THEN 1 ELSE 0 END,
            t.due_date ASC,
            CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END
        """,
        (session["user_id"],),
    ).fetchall()

    buckets = {
        "Overdue": [],
        "Today": [],
        "Upcoming": [],
        "No deadline": [],
    }
    for task in tasks:
        if not task["due_date"]:
            buckets["No deadline"].append(task)
        elif task["due_date"] < today:
            buckets["Overdue"].append(task)
        elif task["due_date"] == today:
            buckets["Today"].append(task)
        else:
            buckets["Upcoming"].append(task)

    return render_template("dashboard/calendar.html", buckets=buckets, today=today)


@dashboard_bp.route("/export/tasks.csv")
@login_required
def export_tasks():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["project", "title", "status", "priority", "due_date", "estimated_minutes"])

    rows = get_db().execute(
        """
        SELECT p.name AS project_name, t.title, t.status, t.priority,
            t.due_date, t.estimated_minutes
        FROM tasks t
        JOIN projects p ON p.id = t.project_id
        WHERE t.user_id = ?
        ORDER BY p.name, t.due_date, t.title
        """,
        (session["user_id"],),
    ).fetchall()
    for row in rows:
        writer.writerow(
            [
                row["project_name"],
                row["title"],
                row["status"],
                row["priority"],
                row["due_date"] or "",
                row["estimated_minutes"] or "",
            ]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=focusboard_tasks.csv"},
    )
