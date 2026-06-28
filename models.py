from __future__ import annotations

from datetime import date

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Child(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    avatar = db.Column(db.String(120), nullable=False)
    completions = db.relationship("Completion", back_populates="child")


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    stars = db.Column(db.Integer, nullable=False, default=1)
    assigned_to = db.Column(db.String(20), nullable=False, default="Both")
    active = db.Column(db.Boolean, nullable=False, default=True)
    completions = db.relationship(
        "Completion", back_populates="task", cascade="all, delete-orphan"
    )


class Completion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    completed = db.Column(db.Boolean, nullable=False, default=True)
    task = db.relationship("Task", back_populates="completions")
    child = db.relationship("Child", back_populates="completions")

    __table_args__ = (
        db.UniqueConstraint("task_id", "child_id", "date", name="one_completion_per_day"),
    )


class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    required_stars = db.Column(db.Integer, nullable=False)
