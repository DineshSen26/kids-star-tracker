from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from models import Completion, Kid, Task, Transaction, db


def today() -> date:
    return date.today()


def week_start(day: date | None = None) -> date:
    day = day or today()
    return day - timedelta(days=day.weekday())


def month_start(day: date | None = None) -> date:
    day = day or today()
    return day.replace(day=1)


def _streak_from_dates(completed_days: set[date]) -> int:
    streak = 0
    cursor = today()
    while cursor in completed_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _best_streak_from_dates(days: list[date]) -> int:
    best = run = 0
    previous = None
    for day in days:
        run = run + 1 if previous and day == previous + timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


def _badges_from_titles(titles: list[str], total: int) -> list[str]:
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


def build_dashboard_payload(kids: list[Kid]) -> tuple[list[dict], dict]:
    if not kids:
        return [], {}

    kid_ids = [kid.id for kid in kids]
    today_val = today()
    week_val = week_start()
    month_val = month_start()
    chart_days = [today_val - timedelta(days=offset) for offset in range(6, -1, -1)]
    month_dt = datetime.combine(month_val, datetime.min.time())
    week_dt = datetime.combine(week_val, datetime.min.time())
    today_start = datetime.combine(today_val, datetime.min.time())
    today_end = datetime.combine(today_val + timedelta(days=1), datetime.min.time())
    chart_start = datetime.combine(chart_days[0], datetime.min.time())

    totals = {
        kid_id: total
        for kid_id, total in db.session.query(
            Transaction.kid_id,
            func.coalesce(func.sum(Transaction.stars), 0),
        )
        .filter(Transaction.kid_id.in_(kid_ids))
        .group_by(Transaction.kid_id)
        .all()
    }

    assigned_counts = {
        kid_id: count
        for kid_id, count in db.session.query(Task.kid_id, func.count())
        .filter(Task.kid_id.in_(kid_ids), Task.active.is_(True))
        .group_by(Task.kid_id)
        .all()
    }

    completed_today_counts = {
        kid_id: count
        for kid_id, count in db.session.query(Completion.kid_id, func.count())
        .filter(
            Completion.kid_id.in_(kid_ids),
            Completion.date == today_val,
            Completion.completed.is_(True),
        )
        .group_by(Completion.kid_id)
        .all()
    }

    txn_rows = db.session.query(
        Transaction.kid_id,
        Transaction.stars,
        Transaction.created_at,
    ).filter(
        Transaction.kid_id.in_(kid_ids),
        Transaction.stars > 0,
        Transaction.created_at >= chart_start,
    )

    period_totals = {kid_id: {"daily": 0, "weekly": 0, "monthly": 0} for kid_id in kid_ids}
    daily_by_kid = {kid_id: {day: 0 for day in chart_days} for kid_id in kid_ids}

    for kid_id, stars, created_at in txn_rows:
        if created_at >= month_dt:
            period_totals[kid_id]["monthly"] += stars
        if created_at >= week_dt:
            period_totals[kid_id]["weekly"] += stars
        if today_start <= created_at < today_end:
            period_totals[kid_id]["daily"] += stars

        day_key = created_at.date()
        if day_key in daily_by_kid[kid_id]:
            daily_by_kid[kid_id][day_key] += stars

    completion_dates = db.session.query(Completion.kid_id, Completion.date).filter(
        Completion.kid_id.in_(kid_ids),
        Completion.completed.is_(True),
    )
    dates_by_kid: dict[int, set[date]] = {kid_id: set() for kid_id in kid_ids}
    for kid_id, completion_date in completion_dates:
        dates_by_kid[kid_id].add(completion_date)

    first_completion = {
        kid_id: first_date
        for kid_id, first_date in db.session.query(
            Completion.kid_id,
            func.min(Completion.date),
        )
        .filter(Completion.kid_id.in_(kid_ids), Completion.completed.is_(True))
        .group_by(Completion.kid_id)
        .all()
    }

    badge_titles = db.session.query(Completion.kid_id, Task.title).join(Task).filter(
        Completion.kid_id.in_(kid_ids),
        Completion.completed.is_(True),
    )
    titles_by_kid: dict[int, list[str]] = {kid_id: [] for kid_id in kid_ids}
    for kid_id, title in badge_titles:
        titles_by_kid[kid_id].append(title.lower())

    recent_by_kid: dict[int, list[Completion]] = {kid_id: [] for kid_id in kid_ids}
    recent_all = (
        Completion.query.options(joinedload(Completion.task))
        .filter(Completion.kid_id.in_(kid_ids), Completion.completed.is_(True))
        .order_by(Completion.date.desc(), Completion.id.desc())
        .all()
    )
    for completion in recent_all:
        bucket = recent_by_kid[completion.kid_id]
        if len(bucket) < 5:
            bucket.append(completion)

    stats = []
    chart_payload = {}
    for kid in kids:
        kid_id = kid.id
        total = totals.get(kid_id, 0)
        assigned = assigned_counts.get(kid_id, 0)
        completed_today = completed_today_counts.get(kid_id, 0)
        kid_dates = dates_by_kid.get(kid_id, set())
        sorted_dates = sorted(kid_dates)
        first_date = first_completion.get(kid_id)
        average = (
            round(total / max((today_val - first_date).days + 1, 1), 1)
            if first_date
            else 0.0
        )
        daily_series = [daily_by_kid[kid_id][day] for day in chart_days]
        stats.append(
            {
                "kid": kid,
                "total": total,
                "daily": period_totals[kid_id]["daily"],
                "weekly": period_totals[kid_id]["weekly"],
                "monthly": period_totals[kid_id]["monthly"],
                "streak": _streak_from_dates(kid_dates),
                "best_streak": _best_streak_from_dates(sorted_dates),
                "completed_today": completed_today,
                "pending_today": max(assigned - completed_today, 0),
                "completion_percent": int((completed_today / assigned) * 100)
                if assigned
                else 0,
                "average": average,
                "badges": _badges_from_titles(titles_by_kid.get(kid_id, []), total),
                "recent": recent_by_kid.get(kid_id, []),
            }
        )
        chart_payload[kid.name] = {
            "labels": [day.strftime("%a") for day in chart_days],
            "daily": daily_series,
            "weekly": [
                sum(daily_series[max(0, index - 6) : index + 1]) for index in range(7)
            ],
            "monthly": [total] * 7,
        }

    return stats, chart_payload


def totals_for_kids(kids: list[Kid]) -> dict[int, int]:
    if not kids:
        return {}

    kid_ids = [kid.id for kid in kids]
    return {
        kid_id: total
        for kid_id, total in db.session.query(
            Transaction.kid_id,
            func.coalesce(func.sum(Transaction.stars), 0),
        )
        .filter(Transaction.kid_id.in_(kid_ids))
        .group_by(Transaction.kid_id)
        .all()
    }
