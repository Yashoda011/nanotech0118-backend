"""Course catalogue, pricing and the limited free offer."""

from datetime import datetime, timezone

from .config import settings

# price in cents (USD). 0 = always free.
COURSES = [
    {"id": "nano-basics", "price_cents": 1900},
    {"id": "nano-char", "price_cents": 2900},
    {"id": "nano-safety", "price_cents": 3900},
    {"id": "nano-ai", "price_cents": 2900},
]

PRICE_BY_COURSE = {c["id"]: c["price_cents"] for c in COURSES}


def offer_ends_at() -> datetime:
    try:
        dt = datetime.fromisoformat(settings.FREE_OFFER_ENDS_AT)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime(2026, 10, 31, tzinfo=timezone.utc)


def offer_active(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now < offer_ends_at()


def price_for(course_id: str) -> int:
    return PRICE_BY_COURSE.get(course_id, 2900)
