from __future__ import annotations

import csv
import secrets
from datetime import date, timedelta
from io import StringIO
from urllib.parse import urlencode

import requests
from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash

from models import Child, Completion, Reward, Task, db

main = Blueprint("main", __name__)


def today() -> date:
    return date.today()


def week_start(day: date | None = None) -> date:
    day = day or today()
    return day - timedelta(days=day.weekday())


def month_start(day: date | None = None) -> date:
    day = day or today()
    return day.replace(day=1)


def children() -> list[Child]:
    return Child.query.order_by(Child.id).all()


def stars_for(query) -> int:
    return (
        query.join(Task)
        .with_entities(func.coalesce(func.sum(Task.stars), 0))
        .scalar()
        or 0
    )


def tasks_for_child(child: Child):
    return Task.query.filter(
        Task.active.is_(True),
        or_(Task.assigned_to == child.name, Task.assigned_to == "Both"),
    ).order_by(Task.title)


def total_stars(child: Child) -> int:
    return stars_for(Completion.query.filter_by(child_id=child.id, completed=True))


def current_streak(child: Child) -> int:
    completed_days = {
        row[0]
        for row in db.session.query(Completion.date)
        .filter_by(child_id=child.id, completed=True)
        .distinct()
    }
    streak = 0
    cursor = today()
    while cursor in completed_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def best_streak(child: Child) -> int:
    days = [
        row[0]
        for row in db.session.query(Completion.date)
        .filter_by(child_id=child.id, completed=True)
        .distinct()
        .order_by(Completion.date)
    ]
    best = run = 0
    previous = None
    for day in days:
        run = run + 1 if previous and day == previous + timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


def badges_for(child: Child, total: int) -> list[str]:
    task_names = " ".join(c.task.title.lower() for c in child.completions if c.completed)
    badges = []
    if total >= 1:
        badges.append("First Star")
    if total >= 10:
        badges.append("10 Stars")
    if total >= 50:
        badges.append("50 Stars")
    if "homework" in task_names:
        badges.append("Homework Hero")
    if "reading" in task_names:
        badges.append("Reading Champion")
    if "clean" in task_names or "help" in task_names:
        badges.append("Helper")
    return badges


def average_stars(child: Child, total: int) -> float:
    first = (
        Completion.query.filter_by(child_id=child.id, completed=True)
        .order_by(Completion.date)
        .first()
    )
    if not first:
        return 0.0
    return round(total / max((today() - first.date).days + 1, 1), 1)


def recent_completions(child: Child, limit: int = 5) -> list[Completion]:
    return (
        Completion.query.filter_by(child_id=child.id, completed=True)
        .order_by(Completion.date.desc(), Completion.id.desc())
        .limit(limit)
        .all()
    )


def child_stats(child: Child) -> dict:
    completions = Completion.query.filter_by(child_id=child.id, completed=True)
    assigned = tasks_for_child(child).count()
    completed_today = completions.filter(Completion.date == today()).count()
    total = total_stars(child)
    return {
        "child": child,
        "total": total,
        "daily": stars_for(completions.filter(Completion.date == today())),
        "weekly": stars_for(completions.filter(Completion.date >= week_start())),
        "monthly": stars_for(completions.filter(Completion.date >= month_start())),
        "streak": current_streak(child),
        "best_streak": best_streak(child),
        "completed_today": completed_today,
        "pending_today": max(assigned - completed_today, 0),
        "completion_percent": int((completed_today / assigned) * 100) if assigned else 0,
        "average": average_stars(child, total),
        "badges": badges_for(child, total),
        "recent": recent_completions(child),
    }


def chart_data(child: Child) -> dict:
    days = [today() - timedelta(days=i) for i in range(6, -1, -1)]
    daily = [
        stars_for(
            Completion.query.filter_by(child_id=child.id, completed=True).filter(
                Completion.date == day
            )
        )
        for day in days
    ]
    return {
        "labels": [day.strftime("%a") for day in days],
        "daily": daily,
        "weekly": [sum(daily[max(0, index - 6) : index + 1]) for index in range(7)],
        "monthly": [total_stars(child) for _ in days],
    }


def login_required():
    if session.get("parent_logged_in"):
        return None
    flash("Parent login is needed for that page.", "warning")
    return redirect(url_for("main.login"))


def google_login_enabled() -> bool:
    return bool(
        current_app.config["GOOGLE_CLIENT_ID"]
        and current_app.config["GOOGLE_CLIENT_SECRET"]
    )


def oauth_redirect_uri() -> str:
    configured = current_app.config["GOOGLE_REDIRECT_URI"]
    if configured:
        return configured
    return url_for("main.google_callback", _external=True)


@main.context_processor
def layout_data():
    quotes = [
        "Tiny steps make giant stars.",
        "Kind hands earn bright stars.",
        "Today is a great day to shine.",
    ]
    return {
        "current_date": today().strftime("%A, %B %d, %Y"),
        "quote": quotes[today().toordinal() % len(quotes)],
        "google_login_enabled": google_login_enabled(),
    }


@main.route("/")
def dashboard():
    stats = [child_stats(child) for child in children()]
    leaderboard = sorted(stats, key=lambda item: item["total"], reverse=True)
    difference = (
        abs(leaderboard[0]["total"] - leaderboard[1]["total"])
        if len(leaderboard) == 2
        else 0
    )
    return render_template(
        "dashboard.html",
        stats=stats,
        leaderboard=leaderboard,
        difference=difference,
        chart_payload={item["child"].name: chart_data(item["child"]) for item in stats},
    )


@main.route("/child/<int:child_id>")
def child_page(child_id: int):
    child = Child.query.get_or_404(child_id)
    done_ids = {
        row[0]
        for row in db.session.query(Completion.task_id).filter_by(
            child_id=child_id, date=today(), completed=True
        )
    }
    return render_template(
        "child.html",
        child=child,
        tasks=tasks_for_child(child).all(),
        done_ids=done_ids,
        stats=child_stats(child),
    )


@main.post("/complete/<int:task_id>/<int:child_id>")
def complete_task(task_id: int, child_id: int):
    existing = Completion.query.filter_by(
        task_id=task_id, child_id=child_id, date=today()
    ).first()
    if not existing:
        db.session.add(Completion(task_id=task_id, child_id=child_id, date=today()))
        db.session.commit()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    flash("Task completed. A bright new star is yours!", "success")
    return redirect(url_for("main.child_page", child_id=child_id))


@main.route("/tasks")
def tasks():
    return redirect(url_for("main.parent"))


@main.route("/parent", methods=["GET", "POST"])
def parent():
    guard = login_required()
    if guard:
        return guard
    if request.method == "POST":
        task_id = request.form.get("task_id", type=int)
        task = Task.query.get(task_id) if task_id else Task()
        task.title = request.form["title"].strip()
        task.stars = max(request.form.get("stars", type=int) or 1, 1)
        task.assigned_to = request.form["assigned_to"]
        task.active = request.form.get("active") == "on"
        db.session.add(task)
        db.session.commit()
        flash("Task saved.", "success")
        return redirect(url_for("main.parent"))
    return render_template("parent.html", tasks=Task.query.order_by(Task.title).all())


@main.post("/task/delete/<int:task_id>")
def delete_task(task_id: int):
    guard = login_required()
    if guard:
        return guard
    db.session.delete(Task.query.get_or_404(task_id))
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("main.parent"))


@main.route("/rewards", methods=["GET", "POST"])
def rewards():
    guard = login_required()
    if guard:
        return guard
    if request.method == "POST":
        db.session.add(
            Reward(
                title=request.form["title"].strip(),
                required_stars=max(request.form.get("required_stars", type=int) or 1, 1),
            )
        )
        db.session.commit()
        flash("Reward added.", "success")
        return redirect(url_for("main.rewards"))
    return render_template(
        "rewards.html",
        rewards=Reward.query.order_by(Reward.required_stars).all(),
        stats=[child_stats(child) for child in children()],
    )


@main.route("/history")
def history():
    period = request.args.get("period", "today")
    start = {"today": today(), "week": week_start(), "month": month_start()}.get(
        period, today()
    )
    completions = (
        Completion.query.filter(Completion.date >= start, Completion.completed.is_(True))
        .order_by(Completion.date.desc(), Completion.id.desc())
        .all()
    )
    return render_template(
        "history.html",
        completions=completions,
        total=sum(item.task.stars for item in completions),
        selected_period=period,
    )


@main.route("/history/export")
def export_history():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Child", "Task", "Stars"])
    for row in Completion.query.filter_by(completed=True).order_by(Completion.date.desc()):
        writer.writerow([row.date.isoformat(), row.child.name, row.task.title, row.task.stars])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=star-history.csv"},
    )


@main.post("/completion/<int:completion_id>/undo")
def undo_completion(completion_id: int):
    guard = login_required()
    if guard:
        return guard
    completion = Completion.query.get_or_404(completion_id)
    task_title = completion.task.title
    child_name = completion.child.name
    db.session.delete(completion)
    db.session.commit()
    flash(f"{task_title} is now pending again for {child_name}.", "info")
    return redirect(request.referrer or url_for("main.history"))


@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if google_login_enabled():
            flash("Please use Google sign-in for parent access.", "warning")
            return redirect(url_for("main.login"))
        if check_password_hash(
            current_app.config["PARENT_PASSWORD_HASH"], request.form.get("password", "")
        ):
            session["parent_logged_in"] = True
            session["parent_email"] = "local-parent"
            flash("Welcome back, parent captain.", "success")
            return redirect(url_for("main.parent"))
        flash("That password did not match.", "danger")
    return render_template("login.html")


@main.route("/login/google")
def google_login():
    if not google_login_enabled():
        flash("Google login is not configured yet.", "warning")
        return redirect(url_for("main.login"))
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    params = {
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": oauth_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@main.route("/auth/google/callback")
def google_callback():
    if request.args.get("state") != session.pop("oauth_state", None):
        flash("Google login could not be verified. Please try again.", "danger")
        return redirect(url_for("main.login"))
    if request.args.get("error"):
        flash("Google login was cancelled.", "warning")
        return redirect(url_for("main.login"))

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": request.args.get("code"),
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": oauth_redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if not token_response.ok:
        flash("Google login failed while getting access. Please try again.", "danger")
        return redirect(url_for("main.login"))

    access_token = token_response.json().get("access_token")
    profile_response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not profile_response.ok:
        flash("Google login failed while reading your email.", "danger")
        return redirect(url_for("main.login"))

    profile = profile_response.json()
    email = profile.get("email", "").lower()
    allowed_emails = current_app.config["PARENT_EMAILS"]
    if allowed_emails and email not in allowed_emails:
        flash("That Google account is not allowed for parent access.", "danger")
        return redirect(url_for("main.login"))

    session["parent_logged_in"] = True
    session["parent_email"] = email
    flash("Signed in with Google.", "success")
    return redirect(url_for("main.parent"))


@main.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("main.dashboard"))


@main.post("/reset/<period>")
def reset_period(period: str):
    guard = login_required()
    if guard:
        return guard
    start = week_start() if period == "weekly" else month_start()
    Completion.query.filter(Completion.date >= start).delete()
    db.session.commit()
    flash(f"{period.title()} stars reset.", "info")
    return redirect(url_for("main.parent"))
