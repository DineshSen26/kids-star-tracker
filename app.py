from __future__ import annotations

import os
from datetime import datetime, timedelta

from flask import Flask, request
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import inspect, text
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from models import Completion, Kid, Reward, Task, Transaction, User, db
from routes import main, today
from task_icons import suggest_task_icon


login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message_category = "warning"


def database_uri(app_root_path: str) -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    database_path = os.path.join(app_root_path, "database.db")
    return f"sqlite:///{database_path}"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


LEGACY_TABLES = ("completion", "child", "task", "reward")

PERFORMANCE_INDEXES = (
    ("ix_transactions_kid_created", "transactions", "kid_id, created_at"),
    ("ix_completions_kid_date", "completions", "kid_id, date"),
    ("ix_completions_kid_date_completed", "completions", "kid_id, date, completed"),
    ("ix_tasks_kid_active", "tasks", "kid_id, active"),
    ("ix_tasks_user_id", "tasks", "user_id"),
)


def drop_legacy_schema_if_needed() -> None:
    """Remove pre-multi-user tables that block PostgreSQL schema creation."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    legacy = set(LEGACY_TABLES) & tables
    if not legacy:
        return

    new_schema_ready = "users" in tables and "completions" in tables
    if new_schema_ready:
        return

    for table in LEGACY_TABLES:
        if table in tables:
            db.session.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

    if "completions" not in tables:
        db.session.execute(text("DROP INDEX IF EXISTS one_completion_per_day"))

    db.session.commit()


def ensure_performance_indexes() -> None:
    inspector = inspect(db.engine)
    if "transactions" not in inspector.get_table_names():
        return

    existing = {
        index["name"]
        for index in inspector.get_indexes("transactions")
    }
    for table_name in ("completions", "tasks"):
        if table_name in inspector.get_table_names():
            existing.update(
                index["name"] for index in inspector.get_indexes(table_name)
            )

    for index_name, table_name, columns in PERFORMANCE_INDEXES:
        if index_name in existing:
            continue
        db.session.execute(
            text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})")
        )
    db.session.commit()


def migrate_task_icons_if_needed() -> None:
    inspector = inspect(db.engine)
    if "tasks" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("tasks")}
    if "icon" not in columns:
        db.session.execute(
            text("ALTER TABLE tasks ADD COLUMN icon VARCHAR(120) DEFAULT 'fa-solid fa-star'")
        )
        db.session.commit()

    stale_tasks = Task.query.filter(
        (Task.icon.like("http%"))
        | (Task.icon == "")
        | (Task.icon.is_(None))
        | (~Task.icon.like("fa-%"))
    ).all()
    if not stale_tasks:
        return

    for task in stale_tasks:
        task.icon = suggest_task_icon(task.title)
    db.session.commit()


def prepare_database() -> None:
    drop_legacy_schema_if_needed()
    db.create_all()
    migrate_task_icons_if_needed()
    ensure_performance_indexes()


def create_app() -> Flask:
    app = Flask(__name__)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-secret-change-me-for-production"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri(app.root_path)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    engine_options = {"pool_pre_ping": True}
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        engine_options.update(
            {
                "pool_recycle": 300,
                "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
                "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "2")),
            }
        )
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "")
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    app.config["GOOGLE_REDIRECT_URI"] = os.environ.get("GOOGLE_REDIRECT_URI", "")
    app.config["APP_BASE_URL"] = os.environ.get("APP_BASE_URL", "").rstrip("/")
    app.config["PREFERRED_URL_SCHEME"] = os.environ.get("PREFERRED_URL_SCHEME", "https")

    app.config["SEED_DEMO_DATA"] = os.environ.get("SEED_DEMO_DATA", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    app.config["DEMO_USER_EMAIL"] = os.environ.get(
        "DEMO_USER_EMAIL", "demo@example.com"
    )
    app.config["DEMO_USER_PASSWORD"] = os.environ.get("DEMO_USER_PASSWORD", "demo123")

    db.init_app(app)
    login_manager.init_app(app)
    Migrate(app, db)

    app.register_blueprint(main)

    @app.after_request
    def add_static_cache_headers(response):
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
        return response

    with app.app_context():
        prepare_database()
        if app.config["SEED_DEMO_DATA"]:
            seed_data(app)

    return app


def seed_data(app: Flask) -> None:
    if User.query.count():
        return

    demo_email = app.config["DEMO_USER_EMAIL"]
    demo_password = app.config["DEMO_USER_PASSWORD"]

    user = User(
        email=demo_email,
        password_hash=generate_password_hash(demo_password),
    )
    db.session.add(user)
    db.session.flush()

    atharv = Kid(
        user_id=user.id,
        name="Atharv",
        age=8,
        avatar="fa-solid fa-user-astronaut",
    )
    ishanvi = Kid(
        user_id=user.id,
        name="Ishanvi",
        age=6,
        avatar="fa-solid fa-wand-magic-sparkles",
    )
    db.session.add_all([atharv, ishanvi])
    db.session.flush()

    task_defs = [
        ("Homework", 4),
        ("Reading", 3),
        ("Brush Teeth", 2),
        ("Clean Toys", 2),
        ("Drawing", 3),
        ("Help Mom", 2),
    ]

    kid_task_map = {
        atharv.id: ["Homework", "Reading", "Brush Teeth", "Help Mom"],
        ishanvi.id: ["Reading", "Clean Toys", "Drawing", "Help Mom"],
    }

    tasks_by_kid: dict[int, list[Task]] = {atharv.id: [], ishanvi.id: []}
    for kid_id, titles in kid_task_map.items():
        for title, stars in task_defs:
            if title in titles:
                task = Task(
                    user_id=user.id,
                    kid_id=kid_id,
                    title=title,
                    icon=suggest_task_icon(title),
                    stars=stars,
                )
                db.session.add(task)
                tasks_by_kid[kid_id].append(task)

    db.session.flush()

    reward_defs = [
        ("Ice Cream", 100),
        ("Movie Night", 200),
        ("Toy", 300),
    ]
    for kid in (atharv, ishanvi):
        for title, required in reward_defs:
            db.session.add(
                Reward(
                    user_id=user.id,
                    kid_id=kid.id,
                    title=title,
                    required_stars=required,
                )
            )

    db.session.flush()

    for kid in (atharv, ishanvi):
        assigned_tasks = tasks_by_kid[kid.id]
        for offset, task in enumerate(assigned_tasks[:4]):
            completion_date = today() - timedelta(days=offset)
            completion = Completion(
                task_id=task.id,
                kid_id=kid.id,
                date=completion_date,
            )
            db.session.add(completion)
            db.session.flush()
            db.session.add(
                Transaction(
                    kid_id=kid.id,
                    stars=task.stars,
                    reason=f"Task: {task.title}",
                    reference_type="completion",
                    reference_id=completion.id,
                    created_at=datetime.combine(
                        completion_date, datetime.min.time()
                    ),
                )
            )

    db.session.commit()


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
