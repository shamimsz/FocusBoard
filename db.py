import os
import sqlite3

from flask import current_app, g


def database_path():
    configured = current_app.config["DATABASE"]
    if os.path.isabs(configured):
        return configured
    os.makedirs(current_app.instance_path, exist_ok=True)
    return os.path.join(current_app.instance_path, configured)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(database_path())
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as schema:
        db.executescript(schema.read().decode("utf-8"))
    db.commit()
