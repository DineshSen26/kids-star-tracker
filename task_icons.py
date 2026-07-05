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
    # New icons
    "fa-solid fa-pills",          # Medicine
    "fa-solid fa-heart",          # Kindness
    "fa-solid fa-face-smile",     # Good behaviour
    "fa-solid fa-glass-water",    # Drink water
    "fa-solid fa-carrot",         # Vegetables
    "fa-solid fa-cookie-bite",    # Snack/Treat
    "fa-solid fa-clock",          # Be on time
    "fa-solid fa-hand-sparkles",  # Wash hands
    "fa-solid fa-soap",           # Soap
    "fa-solid fa-moon",           # Sleep
    "fa-solid fa-school",         # School
    "fa-solid fa-backpack",       # School bag
    "fa-solid fa-heart-pulse",    # Health
]

TASK_ICON_KEYWORDS: list[tuple[list[str], str]] = [
   (["homework", "school", "study", "math", "spell", "write"], "fa-solid fa-book"),
    (["reading", "read", "story", "library"], "fa-solid fa-book-open-reader"),
    (["practice", "worksheet", "writing"], "fa-solid fa-pencil"),

    (["brush", "teeth", "tooth", "dental"], "fa-solid fa-tooth"),

    (["medicine", "medication", "pill", "vitamin", "tablet", "syrup"], "fa-solid fa-pills"),

    (["wash hands", "hand wash", "sanitize"], "fa-solid fa-hand-sparkles"),

    (["soap"], "fa-solid fa-soap"),

    (["bath", "shower"], "fa-solid fa-shower"),

    (["clean", "tidy", "toys", "room", "organize"], "fa-solid fa-broom"),

    (["draw", "drawing", "paint", "art", "colour", "color"], "fa-solid fa-palette"),

    (["eat", "breakfast", "lunch", "dinner", "food"], "fa-solid fa-utensils"),

    (["fruit", "apple", "banana", "snack"], "fa-solid fa-apple-whole"),

    (["vegetable", "veggie", "carrot", "broccoli"], "fa-solid fa-carrot"),

    (["drink", "water", "hydrate"], "fa-solid fa-glass-water"),

    (["bed", "sleep", "nap"], "fa-solid fa-bed"),

    (["night", "moon", "bedtime"], "fa-solid fa-moon"),

    (["dress", "clothes", "shirt", "uniform"], "fa-solid fa-shirt"),

    (["exercise", "sport", "run", "workout"], "fa-solid fa-person-running"),

    (["bike", "bicycle", "cycle"], "fa-solid fa-bicycle"),

    (["music", "sing", "song", "piano"], "fa-solid fa-music"),

    (["game", "play", "tablet", "video game"], "fa-solid fa-gamepad"),

    (["lego", "blocks", "puzzle"], "fa-solid fa-puzzle-piece"),

    (["dog", "walk dog", "pet"], "fa-solid fa-dog"),

    (["cat", "kitty"], "fa-solid fa-cat"),

    (["garden", "plant", "flower", "water plant"], "fa-solid fa-seedling"),

    (["trash", "garbage", "recycle"], "fa-solid fa-trash"),

    (["dishes", "dishwasher", "sink"], "fa-solid fa-sink"),

    (["help", "mom", "dad", "family", "chores"], "fa-solid fa-hands-helping"),

    (["kind", "sharing", "polite", "good behaviour", "respect"], "fa-solid fa-heart"),

    (["happy", "smile", "good job"], "fa-solid fa-face-smile"),

    (["school bus", "school"], "fa-solid fa-school"),

    (["bag", "backpack"], "fa-solid fa-backpack"),

    (["health", "doctor"], "fa-solid fa-heart-pulse"),

    (["time", "clock", "early"], "fa-solid fa-clock"),
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
