from __future__ import annotations

import csv
import re
import secrets
from datetime import date, datetime, timedelta
from functools import wraps
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
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash

from models import (
    MAX_KIDS_PER_USER,
    Completion,
    Invitation,
    Kid,
    Reward,
    Task,
    Transaction,
    User,
    db,
)
from task_icons import (
    DEFAULT_TASK_ICON,
    resolve_task_icon,
    suggest_task_icon,
    suggest_task_icons,
)
from stats_service import build_dashboard_payload, totals_for_kids

main = Blueprint("main", __name__)

AVATAR_CHOICES = [
    "fa-solid fa-user-astronaut",
    "fa-solid fa-wand-magic-sparkles",
    "fa-solid fa-dragon",
    "fa-solid fa-cat",
    "fa-solid fa-dog",
    "fa-solid fa-star",
    "fa-solid fa-rocket",
    "fa-solid fa-heart",
]


def today() -> date:
    return date.today()


def week_start(day: date | None = None) -> date:
    day = day or today()
    return day - timedelta(days=day.weekday())


def month_start(day: date | None = None) -> date:
    day = day or today()
    return day.replace(day=1)


def user_kids(user: User | None = None) -> list[Kid]:
    user = user or current_user
    return Kid.query.filter_by(user_id=user.id).order_by(Kid.id).all()


def get_user_kid(kid_id: int, user: User | None = None) -> Kid:
    user = user or current_user
    return Kid.query.filter_by(id=kid_id, user_id=user.id).first_or_404()


def total_stars(kid: Kid) -> int:
    return (
        db.session.query(func.coalesce(func.sum(Transaction.stars), 0))
        .filter_by(kid_id=kid.id)
        .scalar()
        or 0
    )


def stars_for_period(kid: Kid, start: date, end: date | None = None) -> int:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = (
        datetime.combine(end + timedelta(days=1), datetime.min.time())
        if end
        else None
    )
    query = db.session.query(func.coalesce(func.sum(Transaction.stars), 0)).filter(
        Transaction.kid_id == kid.id,
        Transaction.stars > 0,
        Transaction.created_at >= start_dt,
    )
    if end_dt:
        query = query.filter(Transaction.created_at < end_dt)
    return query.scalar() or 0


def add_transaction(
    kid: Kid,
    stars: int,
    reason: str,
    reference_type: str,
    reference_id: int | None = None,
) -> Transaction:
    txn = Transaction(
        kid_id=kid.id,
        stars=stars,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.session.add(txn)
    return txn


def tasks_for_kid(kid: Kid):
    return Task.query.filter_by(kid_id=kid.id, active=True).order_by(Task.title)


def current_streak(kid: Kid) -> int:
    completed_days = {
        row[0]
        for row in db.session.query(Completion.date)
        .filter_by(kid_id=kid.id, completed=True)
        .distinct()
    }
    streak = 0
    cursor = today()
    while cursor in completed_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def best_streak(kid: Kid) -> int:
    days = [
        row[0]
        for row in db.session.query(Completion.date)
        .filter_by(kid_id=kid.id, completed=True)
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


def badges_for(kid: Kid, total: int) -> list[str]:
    titles = [
        title.lower()
        for title, in db.session.query(Task.title)
        .join(Completion)
        .filter(Completion.kid_id == kid.id, Completion.completed.is_(True))
    ]
    task_names = " ".join(titles)
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


def average_stars(kid: Kid, total: int) -> float:
    first = (
        Completion.query.filter_by(kid_id=kid.id, completed=True)
        .order_by(Completion.date)
        .first()
    )
    if not first:
        return 0.0
    return round(total / max((today() - first.date).days + 1, 1), 1)


def recent_completions(kid: Kid, limit: int = 5) -> list[Completion]:
    return (
        Completion.query.options(joinedload(Completion.task))
        .filter_by(kid_id=kid.id, completed=True)
        .order_by(Completion.date.desc(), Completion.id.desc())
        .limit(limit)
        .all()
    )


def kid_stats(kid: Kid) -> dict:
    assigned = tasks_for_kid(kid).count()
    completed_today = Completion.query.filter_by(
        kid_id=kid.id, date=today(), completed=True
    ).count()
    total = total_stars(kid)
    return {
        "kid": kid,
        "total": total,
        "daily": stars_for_period(kid, today(), today()),
        "weekly": stars_for_period(kid, week_start()),
        "monthly": stars_for_period(kid, month_start()),
        "streak": current_streak(kid),
        "best_streak": best_streak(kid),
        "completed_today": completed_today,
        "pending_today": max(assigned - completed_today, 0),
        "completion_percent": int((completed_today / assigned) * 100) if assigned else 0,
        "average": average_stars(kid, total),
        "badges": badges_for(kid, total),
        "recent": recent_completions(kid),
    }


def google_login_enabled() -> bool:
    return bool(
        current_app.config["GOOGLE_CLIENT_ID"]
        and current_app.config["GOOGLE_CLIENT_SECRET"]
    )


def oauth_redirect_uri() -> str:
    configured = current_app.config.get("GOOGLE_REDIRECT_URI", "").strip()
    if configured:
        return configured

    app_base_url = current_app.config.get("APP_BASE_URL", "").strip().rstrip("/")
    if app_base_url:
        return f"{app_base_url}/auth/google/callback"

    if request.host:
        scheme = current_app.config.get("PREFERRED_URL_SCHEME", "https")
        return f"{scheme}://{request.host}/auth/google/callback"

    return url_for("main.google_callback", _external=True)


def child_session_valid(kid: Kid) -> bool:
    return (
        session.get("child_kid_id") == kid.id
        and session.get("child_user_id") == kid.user_id
    )


def check_child_access(kid_id: int):
    kid = Kid.query.get_or_404(kid_id)
    if not kid.child_login_enabled:
        return None
    if current_user.is_authenticated and current_user.id == kid.user_id:
        return None
    if child_session_valid(kid):
        return None
    return redirect(url_for("main.child_login", kid_id=kid_id))


def child_access_required(f):
    @wraps(f)
    def wrapper(kid_id: int, *args, **kwargs):
        guard = check_child_access(kid_id)
        if guard:
            return guard
        return f(kid_id, *args, **kwargs)

    return wrapper


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


@main.app_template_filter("task_icon")
def task_icon_filter(stored: str | None, title: str = "") -> str:
    return resolve_task_icon(stored, title)


@main.route("/about")
def about():
    return render_template("about.html")


@main.route("/how-to-use")
def how_to_use():
    return render_template("how_to_use.html")


@main.route("/")
@login_required
def dashboard():
    kids_list = user_kids()
    stats, chart_payload = build_dashboard_payload(kids_list)
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
        chart_payload=chart_payload,
    )


@main.route("/child/<int:kid_id>")
@child_access_required
def child_page(kid_id: int):
    kid = Kid.query.get_or_404(kid_id)
    done_ids = {
        row[0]
        for row in db.session.query(Completion.task_id).filter_by(
            kid_id=kid_id, date=today(), completed=True
        )
    }
    return render_template(
        "child.html",
        kid=kid,
        tasks=tasks_for_kid(kid).all(),
        done_ids=done_ids,
        stats=kid_stats(kid),
    )


@main.route("/child/<int:kid_id>/login", methods=["GET", "POST"])
def child_login(kid_id: int):
    kid = Kid.query.get_or_404(kid_id)
    if not kid.child_login_enabled:
        return redirect(url_for("main.child_page", kid_id=kid_id))
    if current_user.is_authenticated and current_user.id == kid.user_id:
        return redirect(url_for("main.child_page", kid_id=kid_id))
    if child_session_valid(kid):
        return redirect(url_for("main.child_page", kid_id=kid_id))

    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        if kid.child_pin_hash and check_password_hash(kid.child_pin_hash, pin):
            session["child_kid_id"] = kid.id
            session["child_user_id"] = kid.user_id
            flash(f"Welcome back, {kid.name}!", "success")
            return redirect(url_for("main.child_page", kid_id=kid_id))
        flash("That PIN did not match. Try again.", "danger")

    return render_template("child_login.html", kid=kid)


@main.route("/child/logout")
def child_logout():
    session.pop("child_kid_id", None)
    session.pop("child_user_id", None)
    flash("Logged out.", "info")
    return redirect(url_for("main.login"))


@main.post("/complete/<int:task_id>/<int:kid_id>")
def complete_task(task_id: int, kid_id: int):
    guard = check_child_access(kid_id)
    if guard:
        return guard
    kid = Kid.query.get_or_404(kid_id)
    task = Task.query.filter_by(id=task_id, kid_id=kid_id).first_or_404()

    existing = Completion.query.filter_by(
        task_id=task_id, kid_id=kid_id, date=today()
    ).first()
    if not existing:
        completion = Completion(task_id=task_id, kid_id=kid_id, date=today())
        db.session.add(completion)
        db.session.flush()
        add_transaction(
            kid,
            task.stars,
            f"Task: {task.title}",
            "completion",
            completion.id,
        )
        db.session.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    flash("Task completed. A bright new star is yours!", "success")
    return redirect(url_for("main.child_page", kid_id=kid_id))


@main.route("/kids", methods=["GET", "POST"])
@login_required
def kids():
    kids_list = user_kids()
    if request.method == "POST":
        if len(kids_list) >= MAX_KIDS_PER_USER:
            flash(
                f"You can manage up to {MAX_KIDS_PER_USER} kids. "
                "Delete one before adding another.",
                "warning",
            )
            return redirect(url_for("main.kids"))

        name = request.form["name"].strip()
        if not name:
            flash("Kid name is required.", "danger")
            return redirect(url_for("main.kids"))

        if Kid.query.filter_by(user_id=current_user.id, name=name).first():
            flash(f"A kid named {name} already exists.", "warning")
            return redirect(url_for("main.kids"))

        age = request.form.get("age", type=int)
        avatar = request.form.get("avatar") or AVATAR_CHOICES[0]
        kid = Kid(user_id=current_user.id, name=name, age=age, avatar=avatar)
        db.session.add(kid)
        db.session.commit()
        flash(f"{name} was added.", "success")
        return redirect(url_for("main.kids"))

    return render_template(
        "kids.html",
        kids=kids_list,
        max_kids=MAX_KIDS_PER_USER,
        avatar_choices=AVATAR_CHOICES,
    )


@main.route("/kids/<int:kid_id>/edit", methods=["GET", "POST"])
@login_required
def edit_kid(kid_id: int):
    kid = get_user_kid(kid_id)
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("Kid name is required.", "danger")
            return redirect(url_for("main.edit_kid", kid_id=kid_id))

        existing = Kid.query.filter(
            Kid.user_id == current_user.id,
            Kid.name == name,
            Kid.id != kid_id,
        ).first()
        if existing:
            flash(f"A kid named {name} already exists.", "warning")
            return redirect(url_for("main.edit_kid", kid_id=kid_id))

        kid.name = name
        kid.age = request.form.get("age", type=int)
        kid.avatar = request.form.get("avatar") or kid.avatar
        kid.child_login_enabled = request.form.get("child_login_enabled") == "on"

        pin = request.form.get("pin", "").strip()
        if pin:
            if not re.fullmatch(r"\d{4,6}", pin):
                flash("PIN must be 4–6 digits.", "danger")
                return redirect(url_for("main.edit_kid", kid_id=kid_id))
            kid.child_pin_hash = generate_password_hash(pin)
        elif kid.child_login_enabled and not kid.child_pin_hash:
            flash("Set a PIN before enabling child login.", "danger")
            return redirect(url_for("main.edit_kid", kid_id=kid_id))

        if not kid.child_login_enabled:
            kid.child_pin_hash = None

        db.session.commit()
        flash(f"{kid.name}'s profile was updated.", "success")
        return redirect(url_for("main.kids"))

    return render_template(
        "edit_kid.html",
        kid=kid,
        avatar_choices=AVATAR_CHOICES,
    )


@main.post("/kids/<int:kid_id>/delete")
@login_required
def delete_kid(kid_id: int):
    kid = get_user_kid(kid_id)
    name = kid.name
    db.session.delete(kid)
    db.session.commit()
    flash(f"{name} was removed.", "info")
    return redirect(url_for("main.kids"))


@main.route("/api/task-icon-suggest")
@login_required
def task_icon_suggest():
    query = request.args.get("q", "").strip()
    icons = suggest_task_icons(query) if query else [DEFAULT_TASK_ICON]
    return jsonify({"icons": icons, "primary": icons[0]})


@main.route("/parent", methods=["GET", "POST"])
@login_required
def parent():
    kids_list = user_kids()
    if request.method == "POST":
        task_id = request.form.get("task_id", type=int)
        title = request.form["title"].strip()
        stars = max(request.form.get("stars", type=int) or 1, 1)
        active = request.form.get("active") == "on"
        selected_kids = request.form.getlist("kid_ids", type=int)
        icon = request.form.get("icon", "").strip() or suggest_task_icon(title)

        if task_id:
            task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
            task.title = title
            task.icon = icon
            task.stars = stars
            task.active = active
            db.session.commit()
            flash("Task saved.", "success")
            return redirect(url_for("main.parent"))

        if not selected_kids:
            flash("Select at least one kid for this task.", "warning")
            return redirect(url_for("main.parent"))

        for kid_id in selected_kids:
            get_user_kid(kid_id)
            db.session.add(
                Task(
                    user_id=current_user.id,
                    kid_id=kid_id,
                    title=title,
                    icon=icon,
                    stars=stars,
                    active=active,
                )
            )
        db.session.commit()
        flash("Task saved for selected kids.", "success")
        return redirect(url_for("main.parent"))

    tasks = (
        Task.query.filter_by(user_id=current_user.id)
        .join(Kid)
        .order_by(Kid.name, Task.title)
        .all()
    )
    return render_template("parent.html", tasks=tasks, kids=kids_list)


@main.post("/task/delete/<int:task_id>")
@login_required
def delete_task(task_id: int):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("main.parent"))


@main.route("/rewards", methods=["GET", "POST"])
@login_required
def rewards():
    kids_list = user_kids()
    if request.method == "POST":
        reward_id = request.form.get("reward_id", type=int)
        title = request.form["title"].strip()
        required_stars = max(request.form.get("required_stars", type=int) or 1, 1)
        selected_kids = request.form.getlist("kid_ids", type=int)

        if reward_id:
            reward = Reward.query.filter_by(
                id=reward_id, user_id=current_user.id
            ).first_or_404()
            reward.title = title
            reward.required_stars = required_stars
            db.session.commit()
            flash("Reward saved.", "success")
            return redirect(url_for("main.rewards"))

        if not selected_kids:
            flash("Select at least one kid for this reward.", "warning")
            return redirect(url_for("main.rewards"))

        for kid_id in selected_kids:
            get_user_kid(kid_id)
            db.session.add(
                Reward(
                    user_id=current_user.id,
                    kid_id=kid_id,
                    title=title,
                    required_stars=required_stars,
                )
            )
        db.session.commit()
        flash("Reward saved for selected kids.", "success")
        return redirect(url_for("main.rewards"))

    rewards_list = (
        Reward.query.filter_by(user_id=current_user.id)
        .join(Kid)
        .order_by(Kid.name, Reward.required_stars)
        .all()
    )
    totals = totals_for_kids(kids_list)
    stats_by_kid = {kid.id: {"total": totals.get(kid.id, 0)} for kid in kids_list}
    return render_template(
        "rewards.html",
        rewards=rewards_list,
        kids=kids_list,
        stats_by_kid=stats_by_kid,
    )


@main.post("/reward/delete/<int:reward_id>")
@login_required
def delete_reward(reward_id: int):
    reward = Reward.query.filter_by(id=reward_id, user_id=current_user.id).first_or_404()
    db.session.delete(reward)
    db.session.commit()
    flash("Reward deleted.", "info")
    return redirect(url_for("main.rewards"))


@main.post("/reward/redeem/<int:reward_id>")
@login_required
def redeem_reward(reward_id: int):
    reward = Reward.query.filter_by(id=reward_id, user_id=current_user.id).first_or_404()
    kid = reward.kid
    balance = total_stars(kid)
    if balance < reward.required_stars:
        flash(
            f"{kid.name} needs {reward.required_stars} stars but has {balance}.",
            "warning",
        )
        return redirect(url_for("main.rewards"))

    add_transaction(
        kid,
        -reward.required_stars,
        f"Reward: {reward.title}",
        "redemption",
        reward.id,
    )
    db.session.commit()
    flash(f"{reward.title} redeemed for {kid.name}!", "success")
    return redirect(url_for("main.rewards"))


@main.route("/history")
@login_required
def history():
    period = request.args.get("period", "today")
    start = {"today": today(), "week": week_start(), "month": month_start()}.get(
        period, today()
    )
    kid_ids = [kid.id for kid in user_kids()]
    completions = (
        Completion.query.options(
            joinedload(Completion.task),
            joinedload(Completion.kid),
        )
        .filter(
            Completion.kid_id.in_(kid_ids),
            Completion.date >= start,
            Completion.completed.is_(True),
        )
        .order_by(Completion.date.desc(), Completion.id.desc())
        .all()
    )
    transactions = (
        Transaction.query.options(joinedload(Transaction.kid))
        .filter(
            Transaction.kid_id.in_(kid_ids),
            Transaction.created_at >= datetime.combine(start, datetime.min.time()),
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return render_template(
        "history.html",
        completions=completions,
        transactions=transactions,
        total=sum(item.task.stars for item in completions),
        selected_period=period,
    )


@main.route("/history/export")
@login_required
def export_history():
    kid_ids = [kid.id for kid in user_kids()]
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Kid", "Type", "Description", "Stars"])
    for row in (
        Transaction.query.options(joinedload(Transaction.kid))
        .filter(Transaction.kid_id.in_(kid_ids))
        .order_by(Transaction.created_at.desc())
        .all()
    ):
        writer.writerow(
            [
                row.created_at.date().isoformat(),
                row.kid.name,
                row.reference_type,
                row.reason,
                row.stars,
            ]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=star-history.csv"},
    )


@main.post("/completion/<int:completion_id>/undo")
@login_required
def undo_completion(completion_id: int):
    completion = Completion.query.get_or_404(completion_id)
    get_user_kid(completion.kid_id)
    task = completion.task
    kid = completion.kid
    task_title = task.title
    kid_name = kid.name
    add_transaction(
        kid,
        -task.stars,
        f"Undo: {task_title}",
        "undo",
        completion.id,
    )
    db.session.delete(completion)
    db.session.commit()
    flash(f"{task_title} is now pending again for {kid_name}.", "info")
    return redirect(request.referrer or url_for("main.history"))


@main.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not email or "@" not in email:
            flash("Enter a valid email address.", "danger")
            return redirect(url_for("main.register"))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("main.register"))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("main.register"))
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "warning")
            return redirect(url_for("main.login"))

        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome! Your account is ready.", "success")
        return redirect(url_for("main.kids"))

    return render_template("register.html")


@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Welcome back!", "success")
            return redirect(url_for("main.dashboard"))

        flash("Invalid email or password.", "danger")

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
    google_sub = profile.get("id")

    user = User.query.filter(
        (User.email == email) | (User.google_sub == google_sub)
    ).first()
    if not user:
        user = User(email=email, google_sub=google_sub)
        db.session.add(user)
        db.session.commit()
    else:
        if not user.google_sub:
            user.google_sub = google_sub
        if not user.email:
            user.email = email
        db.session.commit()

    login_user(user)
    flash("Signed in with Google.", "success")
    return redirect(url_for("main.dashboard"))


@main.route("/logout")
def logout():
    logout_user()
    session.pop("child_kid_id", None)
    session.pop("child_user_id", None)
    flash("Logged out.", "info")
    return redirect(url_for("main.login"))


@main.post("/reset/<period>")
@login_required
def reset_period(period: str):
    start = week_start() if period == "weekly" else month_start()
    kid_ids = [kid.id for kid in user_kids()]
    Completion.query.filter(
        Completion.kid_id.in_(kid_ids), Completion.date >= start
    ).delete(synchronize_session=False)
    db.session.commit()
    flash(
        f"{period.title()} completion records reset. "
        "Star balances are unchanged (use manual adjustments if needed).",
        "info",
    )
    return redirect(url_for("main.parent"))
