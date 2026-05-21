# FocusBoard

FocusBoard is a polished full-stack task and project management web application built with Flask, SQLite, Jinja templates, CSS, and vanilla JavaScript. It is designed as a stronger portfolio version of a CS50-style final project: simple enough to explain clearly, but complete enough to demonstrate real full-stack development skills.

The application lets users register, log in, create projects, add tasks, track deadlines, organize work through a Kanban board, apply labels, filter tasks, review activity history, and export tasks as CSV. Each user's data is separated by account, and passwords are stored using Werkzeug password hashing.

## Features

- User registration, login, logout, and session protection
- Project CRUD with descriptions, deadlines, colors, and archive support
- Task CRUD with status, priority, due date, notes, estimated minutes, and completion date
- Kanban board with `To Do`, `In Progress`, and `Done` columns
- Smart planner that ranks next tasks using rule-based scoring
- Dashboard metrics for total, completed, active, overdue, and due-today tasks
- Project progress calculated automatically from completed tasks
- Calendar/deadline view grouped into overdue, today, upcoming, and no deadline
- Labels with many-to-many task assignment
- Activity log for project and task events
- CSV export for tasks
- Responsive layout with sidebar navigation
- Pytest smoke tests for authentication and core workflows

## Technology

```text
Python
Flask
SQLite
Jinja
HTML
CSS
Vanilla JavaScript
Pytest
```

## Project Structure

```text
focusboard/
├── app.py
├── db.py
├── helpers.py
├── schema.sql
├── requirements.txt
├── routes/
│   ├── auth.py
│   ├── dashboard.py
│   ├── projects.py
│   └── tasks.py
├── templates/
│   ├── layout.html
│   ├── auth/
│   ├── dashboard/
│   ├── projects/
│   └── tasks/
├── static/
│   ├── styles.css
│   └── app.js
└── tests/
    └── test_app.py
```

## Design Notes

The backend uses Flask blueprints to separate responsibilities. Authentication routes live in `routes/auth.py`, dashboard and export routes live in `routes/dashboard.py`, project routes live in `routes/projects.py`, and task/label routes live in `routes/tasks.py`. This keeps `app.py` focused on creating and configuring the application.

The database schema uses six tables: `users`, `projects`, `tasks`, `labels`, `task_labels`, and `activity_log`. Projects and tasks both store a `user_id`, which keeps each user's workspace private. Labels use a many-to-many relationship through `task_labels`, so a task can have multiple labels and each label can be used on many tasks.

Project progress is not stored as a separate database value. It is calculated from task status whenever the project is displayed. This avoids inconsistent data: if a task is marked done, the project percentage changes automatically.

The frontend avoids a heavy framework so the project remains understandable and easy to present. Jinja templates render the pages, CSS handles the layout and responsive UI, and a small JavaScript file handles delete confirmations and quick status changes.

The smart planner is intentionally rule-based rather than hidden behind a black-box model. Each unfinished task receives a score based on priority, deadline urgency, current status, and estimated effort. High, medium, and low priority tasks add 40, 25, and 10 points. Overdue tasks add 50 points, tasks due today add 40 points, tasks due in the next three days add 25 points, and tasks due this week add 15 points. Tasks already in progress add 15 points, while not-started tasks add 5 points. Very quick tasks add 10 points, while very large tasks subtract 5 points so they can be planned more carefully. The app also shows the reasons behind each score, which makes the recommendation system explainable and useful even when a user has not created enough historical data for machine learning.

## Running Locally

Create a virtual environment:

```bash
python3 -m venv venv
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialize the database:

```bash
flask --app app init-db
```

Run the app:

```bash
flask --app app run
```

Open:

```text
http://127.0.0.1:5000
```

## Running Tests

```bash
pytest
```

## Resume Summary

Built a full-stack Flask task management application with authentication, SQLite relational database design, project/task CRUD workflows, Kanban board, dashboard analytics, deadline tracking, labels, CSV export, responsive UI, pytest coverage, and a rule-based smart planning engine for prioritizing tasks by urgency, priority, status, and estimated workload.

## Future AI Extension

A future version could add an optional AI assistant using an external API to break large goals into subtasks or summarize project risk. The current version keeps the core planning feature local and explainable, which makes it reliable without requiring an API key, internet access, or billing setup.
