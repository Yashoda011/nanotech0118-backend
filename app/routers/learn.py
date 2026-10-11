"""Learn endpoints — members-only courses with a limited free offer.

Security model:
- Every route requires a valid JWT (401 otherwise).
- Guests are rejected with 403 (no guest course access).
- Users can only read/write their OWN enrollments/progress/purchases
  (all queries are scoped to owner_id = current user).
- After the free offer ends, enrollment requires a (mock) purchase.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_member
from .. import learn_data
from ..learn_data import COURSES, offer_active, offer_ends_at, price_for
from ..models import Activity, CourseProgress, Enrollment, GlossaryTerm, LessonRow, Purchase, User

router = APIRouter(prefix="/learn", tags=["learn"])


class EnrollIn(BaseModel):
    course_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class ProgressIn(BaseModel):
    course_id: str = Field(min_length=1, max_length=80)
    lesson_id: str = Field(min_length=1, max_length=80)
    done: bool = True
    score: int = Field(default=0, ge=0, le=100)


class CheckoutIn(BaseModel):
    course_id: str = Field(min_length=1, max_length=80)
    # Mock card fields — validated for shape only, never charged/stored.
    card_last4: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


def _iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _catalog_for(user: User, db: Session) -> list[dict]:
    active = offer_active()
    ends = offer_ends_at()
    enrolled_ids = {e.course_id for e in db.query(Enrollment).filter(Enrollment.owner_id == user.id).all()}
    purchased_ids = {p.course_id for p in db.query(Purchase).filter(Purchase.owner_id == user.id).all()}
    out = []
    for c in COURSES:
        price = price_for(c["id"])
        free_now = active or price == 0
        out.append({
            "id": c["id"],
            "price_cents": price,
            "free_now": free_now,
            "offer_ends_at": _iso(ends),
            "offer_active": active,
            "enrolled": c["id"] in enrolled_ids,
            "purchased": c["id"] in purchased_ids,
        })
    return out


@router.get("/courses")
def list_courses(user: User = Depends(require_member), db: Session = Depends(get_db)):
    return {"courses": _catalog_for(user, db)}


@router.get("/enrollments")
def my_enrollments(user: User = Depends(require_member), db: Session = Depends(get_db)):
    rows = db.query(Enrollment).filter(Enrollment.owner_id == user.id).order_by(Enrollment.created_at.desc()).all()
    return {"enrollments": [
        {"course_id": e.course_id, "name": e.name, "email": e.email, "at": _iso(e.created_at)} for e in rows
    ]}


@router.post("/enroll", status_code=201)
def enroll(body: EnrollIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if body.course_id not in {c["id"] for c in COURSES}:
        raise HTTPException(status_code=404, detail="Course not found")
    existing = db.query(Enrollment).filter(
        Enrollment.owner_id == user.id, Enrollment.course_id == body.course_id).first()
    if existing:
        return {"course_id": existing.course_id, "name": existing.name, "email": existing.email, "at": _iso(existing.created_at)}
    price = price_for(body.course_id)
    if not offer_active() and price > 0:
        purchased = db.query(Purchase).filter(
            Purchase.owner_id == user.id, Purchase.course_id == body.course_id).first()
        if not purchased:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED,
                                detail=f"Free offer ended — purchase this course for ${price / 100:.2f} first.")
    e = Enrollment(owner_id=user.id, course_id=body.course_id,
                   name=body.name.strip(), email=body.email.strip().lower())
    db.add(e)
    db.add(Activity(owner_id=user.id, kind="system", title=f"Enrolled in {body.course_id}", meta=e.email))
    db.commit()
    db.refresh(e)
    return {"course_id": e.course_id, "name": e.name, "email": e.email, "at": _iso(e.created_at)}


@router.post("/checkout", status_code=201)
def checkout(body: CheckoutIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if body.course_id not in {c["id"] for c in COURSES}:
        raise HTTPException(status_code=404, detail="Course not found")
    price = price_for(body.course_id)
    if price == 0 or offer_active():
        raise HTTPException(status_code=400, detail="This course is currently free — just enroll.")
    existing = db.query(Purchase).filter(
        Purchase.owner_id == user.id, Purchase.course_id == body.course_id).first()
    if existing:
        return {"course_id": body.course_id, "amount_cents": existing.amount_cents, "at": _iso(existing.created_at)}
    # Mock charge: last4 shape-validated only; nothing is stored or charged.
    p = Purchase(owner_id=user.id, course_id=body.course_id, amount_cents=price)
    db.add(p)
    # Auto-enroll on successful (mock) payment.
    e = Enrollment(owner_id=user.id, course_id=body.course_id, name=user.name, email=user.email)
    db.add(e)
    db.add(Activity(owner_id=user.id, kind="system", title=f"Purchased {body.course_id}", meta=f"${price / 100:.2f} (demo)"))
    db.commit()
    db.refresh(p)
    return {"course_id": body.course_id, "amount_cents": p.amount_cents, "at": _iso(p.created_at)}


@router.get("/progress/{course_id}")
def get_progress(course_id: str, user: User = Depends(require_member), db: Session = Depends(get_db)):
    rows = db.query(CourseProgress).filter(
        CourseProgress.owner_id == user.id, CourseProgress.course_id == course_id).all()
    return {"progress": [
        {"lesson_id": r.lesson_id, "done": r.done, "best_score": r.best_score, "at": _iso(r.updated_at)} for r in rows
    ]}


@router.post("/progress")
def save_progress(body: ProgressIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    enrolled = db.query(Enrollment).filter(
        Enrollment.owner_id == user.id, Enrollment.course_id == body.course_id).first()
    if not enrolled:
        raise HTTPException(status_code=403, detail="Enroll in this course first.")
    row = db.query(CourseProgress).filter(
        CourseProgress.owner_id == user.id, CourseProgress.course_id == body.course_id,
        CourseProgress.lesson_id == body.lesson_id).first()
    if not row:
        row = CourseProgress(owner_id=user.id, course_id=body.course_id, lesson_id=body.lesson_id)
        db.add(row)
    row.done = row.done or body.done
    row.best_score = max(row.best_score or 0, body.score)
    db.commit()
    db.refresh(row)
    return {"lesson_id": row.lesson_id, "done": row.done, "best_score": row.best_score}


@router.get("/lessons/{course_id}")
def course_lessons(course_id: str, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """Tutorial content from the database — enrollment required."""
    enrolled = db.query(Enrollment).filter(
        Enrollment.owner_id == user.id, Enrollment.course_id == course_id).first()
    if not enrolled:
        raise HTTPException(status_code=403, detail="Enroll in this course first.")
    rows = db.query(LessonRow).filter(LessonRow.course_id == course_id).order_by(LessonRow.id).all()
    return {"lessons": [
        {"id": r.lesson_id, "title": r.title, "minutes": r.minutes,
         "body": r.body or [], "quiz": r.quiz or []} for r in rows
    ], "source": "database"}


@router.get("/glossary")
def glossary(q: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(GlossaryTerm).order_by(GlossaryTerm.term).all()
    items = [{"term": r.term, "definition": r.definition, "tag": r.tag} for r in rows]
    needle = (q or "").strip().lower()
    if needle:
        items = [t for t in items if needle in t["term"].lower() or needle in t["definition"].lower()]
    return {"terms": items, "total": len(items), "source": "database"}
