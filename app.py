from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask
from werkzeug.security import generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from models import Child, Completion, Reward, Task, db
from routes import main, today


def create_app() -> Flask:
    app = Flask(__name__)
    database_path = os.path.join(app.root_path, "database.db")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-secret-change-me-for-production"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["PARENT_PASSWORD_HASH"] = os.environ.get(
        "PARENT_PASSWORD_HASH", generate_password_hash("parent123")
    )
    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "")
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    app.config["GOOGLE_REDIRECT_URI"] = os.environ.get("GOOGLE_REDIRECT_URI", "")
    app.config["PREFERRED_URL_SCHEME"] = os.environ.get("PREFERRED_URL_SCHEME", "https")
    app.config["PARENT_EMAILS"] = [
        email.strip().lower()
        for email in os.environ.get("PARENT_EMAILS", "").split(",")
        if email.strip()
    ]

    db.init_app(app)
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        seed_data()

    return app


def seed_data() -> None:
    if Child.query.count():
        return

    atharv = Child(name="Atharv", avatar="fa-solid fa-user-astronaut")
    ishanvi = Child(name="Ishanvi", avatar="fa-solid fa-wand-magic-sparkles")
    db.session.add_all([atharv, ishanvi])
    db.session.flush()

    tasks = [
        Task(title="Homework", stars=4, assigned_to="Atharv"),
        Task(title="Reading", stars=3, assigned_to="Both"),
        Task(title="Brush Teeth", stars=2, assigned_to="Atharv"),
        Task(title="Clean Toys", stars=2, assigned_to="Ishanvi"),
        Task(title="Drawing", stars=3, assigned_to="Ishanvi"),
        Task(title="Help Mom", stars=2, assigned_to="Both"),
    ]
    rewards = [
        Reward(title="Ice Cream", required_stars=100),
        Reward(title="Movie Night", required_stars=200),
        Reward(title="Toy", required_stars=300),
    ]
    db.session.add_all(tasks + rewards)
    db.session.flush()

    for child in (atharv, ishanvi):
        assigned_tasks = [task for task in tasks if task.assigned_to in (child.name, "Both")]
        for offset, task in enumerate(assigned_tasks[:4]):
            db.session.add(
                Completion(
                    task_id=task.id,
                    child_id=child.id,
                    date=today() - timedelta(days=offset),
                )
            )

    db.session.commit()


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
