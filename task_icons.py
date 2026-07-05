from __future__ import annotations

DEFAULT_TASK_ICON = "fa-solid fa-star"

TASK_ICON_CHOICES = [
    "fa-solid fa-star",
    "fa-solid fa-book",
    "fa-solid fa-book-open-reader",
    "fa-solid fa-pencil",
    "fa-solid fa-tooth",
    "fa-solid fa-broom",
    "fa-solid fa-palette",
    "fa-solid fa-hands-helping",
    "fa-solid fa-utensils",
    "fa-solid fa-bed",
    "fa-solid fa-shirt",
    "fa-solid fa-shower",
    "fa-solid fa-dumbbell",
    "fa-solid fa-bicycle",
    "fa-solid fa-music",
    "fa-solid fa-gamepad",
    "fa-solid fa-puzzle-piece",
    "fa-solid fa-dog",
    "fa-solid fa-cat",
    "fa-solid fa-seedling",
    "fa-solid fa-trash",
    "fa-solid fa-sink",
    "fa-solid fa-plate-wheat",
    "fa-solid fa-apple-whole",
    "fa-solid fa-person-running",
]

TASK_ICON_KEYWORDS: list[tuple[list[str], str]] = [
    (["homework", "school", "study", "math", "spell", "write"], "fa-solid fa-book"),
    (["reading", "read", "story", "library"], "fa-solid fa-book-open-reader"),
    (["brush", "teeth", "tooth", "dental"], "fa-solid fa-tooth"),
    (["clean", "tidy", "toys", "room", "organize", "vacuum"], "fa-solid fa-broom"),
    (["draw", "drawing", "art", "paint", "color"], "fa-solid fa-palette"),
    (["help", "mom", "dad", "parent", "family"], "fa-solid fa-hands-helping"),
    (["eat", "breakfast", "lunch", "dinner", "food"], "fa-solid fa-utensils"),
    (["bed", "sleep", "nap"], "fa-solid fa-bed"),
    (["dress", "clothes", "shirt", "outfit"], "fa-solid fa-shirt"),
    (["bath", "shower", "wash"], "fa-solid fa-shower"),
    (["exercise", "sport", "run", "workout"], "fa-solid fa-person-running"),
    (["music", "piano", "sing", "song"], "fa-solid fa-music"),
    (["game", "play", "tablet"], "fa-solid fa-gamepad"),
    (["puzzle", "lego", "blocks"], "fa-solid fa-puzzle-piece"),
    (["dog", "walk dog", "pet"], "fa-solid fa-dog"),
    (["cat", "kitty"], "fa-solid fa-cat"),
    (["garden", "plant", "water", "flower"], "fa-solid fa-seedling"),
    (["trash", "garbage", "recycle"], "fa-solid fa-trash"),
    (["dishes", "sink", "dishwasher"], "fa-solid fa-sink"),
    (["fruit", "apple", "snack", "healthy"], "fa-solid fa-apple-whole"),
    (["bike", "bicycle", "cycle"], "fa-solid fa-bicycle"),
    (["practice", "pencil", "homework"], "fa-solid fa-pencil"),
]


def is_task_icon(value: str | None) -> bool:
    return bool(value and value.startswith("fa-"))


def is_stored_picture(value: str | None) -> bool:
    return bool(value and value.startswith(("http://", "https://")))


def resolve_task_icon(stored: str | None, title: str = "") -> str:
    if is_task_icon(stored):
        return stored
    if is_stored_picture(stored) or not stored:
        return suggest_task_icon(title)
    return stored or DEFAULT_TASK_ICON


def suggest_task_icon(title: str) -> str:
    normalized = title.strip().lower()
    if not normalized:
        return DEFAULT_TASK_ICON

    for keywords, icon in TASK_ICON_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return icon

    return DEFAULT_TASK_ICON


def suggest_task_icons(title: str, limit: int = 5) -> list[str]:
    normalized = title.strip().lower()
    if not normalized:
        return [DEFAULT_TASK_ICON]

    matches: list[str] = []
    for keywords, icon in TASK_ICON_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            if icon not in matches:
                matches.append(icon)

    if not matches:
        matches.append(suggest_task_icon(title))

    for icon in TASK_ICON_CHOICES:
        if icon not in matches:
            matches.append(icon)
        if len(matches) >= limit:
            break

    return matches[:limit]
