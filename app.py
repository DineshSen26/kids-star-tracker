from __future__ import annotations

import os
from datetime import datetime, timedelta

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from models import Completion, Kid, Reward, Task, Transaction, User, db
from routes import main, today


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


def create_app() -> Flask:
    app = Flask(__name__)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-secret-change-me-for-production"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri(app.root_path)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "")
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    app.config["GOOGLE_REDIRECT_URI"] = os.environ.get("GOOGLE_REDIRECT_URI", "")
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

    with app.app_context():
        db.create_all()
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
