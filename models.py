from __future__ import annotations

from datetime import date, datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

MAX_KIDS_PER_USER = 5


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    google_sub = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    kids = db.relationship("Kid", back_populates="user", cascade="all, delete-orphan")
    tasks = db.relationship("Task", back_populates="user", cascade="all, delete-orphan")
    rewards = db.relationship(
        "Reward", back_populates="user", cascade="all, delete-orphan"
    )


class Kid(db.Model):
    __tablename__ = "kids"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    avatar = db.Column(db.String(120), nullable=False, default="fa-solid fa-star")
    child_login_enabled = db.Column(db.Boolean, nullable=False, default=False)
    child_pin_hash = db.Column(db.String(255), nullable=True)
    settings = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="kids")
    tasks = db.relationship("Task", back_populates="kid", cascade="all, delete-orphan")
    completions = db.relationship(
        "Completion", back_populates="kid", cascade="all, delete-orphan"
    )
    transactions = db.relationship(
        "Transaction", back_populates="kid", cascade="all, delete-orphan"
    )
    rewards = db.relationship(
        "Reward", back_populates="kid", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="unique_kid_name_per_user"),
    )


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kid_id = db.Column(db.Integer, db.ForeignKey("kids.id"), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    icon = db.Column(db.String(120), nullable=False, default="fa-solid fa-star")
    stars = db.Column(db.Integer, nullable=False, default=1)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="tasks")
    kid = db.relationship("Kid", back_populates="tasks")
    completions = db.relationship(
        "Completion", back_populates="task", cascade="all, delete-orphan"
    )


class Completion(db.Model):
    __tablename__ = "completions"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    kid_id = db.Column(db.Integer, db.ForeignKey("kids.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    completed = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    task = db.relationship("Task", back_populates="completions")
    kid = db.relationship("Kid", back_populates="completions")

    __table_args__ = (
        db.UniqueConstraint(
            "task_id", "kid_id", "date", name="uq_completions_task_kid_date"
        ),
    )


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    kid_id = db.Column(db.Integer, db.ForeignKey("kids.id"), nullable=False)
    stars = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    reference_type = db.Column(db.String(40), nullable=False)
    reference_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    kid = db.relationship("Kid", back_populates="transactions")


class Reward(db.Model):
    __tablename__ = "rewards"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kid_id = db.Column(db.Integer, db.ForeignKey("kids.id"), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    required_stars = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="rewards")
    kid = db.relationship("Kid", back_populates="rewards")


class Invitation(db.Model):
    __tablename__ = "invitations"

    id = db.Column(db.Integer, primary_key=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    inviter = db.relationship("User")


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User")
