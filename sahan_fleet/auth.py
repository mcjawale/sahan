import functools

from werkzeug.security import check_password_hash, generate_password_hash

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


def hash_password(password):
    return generate_password_hash(password)


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.get("user_id") is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            target = request.args.get("next") or url_for("dashboard.index")
            if not target.startswith("/"):
                target = url_for("dashboard.index")
            return redirect(target)
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=("GET", "POST"))
@login_required
def profile():
    db = get_db()
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        user = db.execute("SELECT * FROM users WHERE id = ?", (g.user_id,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], current):
            flash("Current password is incorrect.", "error")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "error")
        else:
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(new), g.user_id),
            )
            db.commit()
            flash("Password updated.", "ok")
            return redirect(url_for("auth.profile"))
    return render_template("profile.html")
