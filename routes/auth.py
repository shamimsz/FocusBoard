import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from helpers import clean_text


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        email = clean_text(request.form.get("email"))
        password = request.form.get("password") or ""
        confirmation = request.form.get("confirmation") or ""

        if not username:
            flash("Username is required.", "danger")
        elif email and "@" not in email:
            flash("Enter a valid email address or leave it blank.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif password != confirmation:
            flash("Passwords do not match.", "danger")
        else:
            try:
                get_db().execute(
                    """
                    INSERT INTO users (username, email, password_hash)
                    VALUES (?, ?, ?)
                    """,
                    (username, email, generate_password_hash(password)),
                )
                get_db().commit()
                flash("Account created. Please log in.", "success")
                return redirect(url_for("auth.login"))
            except sqlite3.IntegrityError:
                flash("That username or email is already registered.", "danger")

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back.", "success")
            return redirect(url_for("dashboard.home"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
