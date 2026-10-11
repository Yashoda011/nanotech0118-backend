"""Billing — real payment-gated plans (mock charge, real entitlement).

- GET /billing/status → current plan: starter | pro | team.
- POST /billing/checkout-pro → mock $199 charge → Pro.
- POST /billing/checkout-team → mock $999 charge → Team (includes Pro limits).
- POST /billing/cancel → back to Starter.
Cards are shape-validated only, never charged or stored. Members only.
Gates (e.g. /science/simulate quota) treat Pro and Team as unlimited.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_member
from ..models import Activity, Purchase, User

router = APIRouter(prefix="/billing", tags=["billing"])

PRO_PRICE_CENTS = 19900
TEAM_PRICE_CENTS = 99900


class CardIn(BaseModel):
    card_last4: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


def _iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def plan_of(user: User) -> str:
    if getattr(user, "is_team", False):
        return "team"
    if getattr(user, "is_pro", False):
        return "pro"
    return "starter"


@router.get("/status")
def status(user: User = Depends(require_member)):
    return {
        "plan": plan_of(user),
        "is_pro": plan_of(user) in ("pro", "team"),
        "pro_since": _iso(user.pro_since),
        "pro_price_cents": PRO_PRICE_CENTS,
        "team_price_cents": TEAM_PRICE_CENTS,
    }


def _grant(user: User, db: Session, course_id: str, amount: int, title: str, team: bool = False) -> None:
    now = datetime.now(timezone.utc)
    user.is_pro = True
    user.pro_since = now
    user.is_team = team
    db.add(Purchase(owner_id=user.id, course_id=course_id, amount_cents=amount))
    db.add(Activity(owner_id=user.id, kind="system", title=title, meta=f"${amount / 100:.2f} (demo)"))
    db.commit()
    db.refresh(user)


@router.post("/checkout-pro", status_code=201)
def checkout_pro(body: CardIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if plan_of(user) == "pro":
        return {"plan": "pro", "is_pro": True, "pro_since": _iso(user.pro_since)}
    if plan_of(user) == "team":
        raise HTTPException(status_code=400, detail="Team already includes Pro.")
    _grant(user, db, "__pro_plan__", PRO_PRICE_CENTS, "Upgraded to NanoSphere Pro")
    return {"plan": "pro", "is_pro": True, "pro_since": _iso(user.pro_since)}


@router.post("/checkout-team", status_code=201)
def checkout_team(body: CardIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    if plan_of(user) == "team":
        return {"plan": "team", "is_pro": True, "pro_since": _iso(user.pro_since)}
    _grant(user, db, "__team_plan__", TEAM_PRICE_CENTS, "Upgraded to NanoSphere Team", team=True)
    return {"plan": "team", "is_pro": True, "pro_since": _iso(user.pro_since)}


@router.post("/cancel")
def cancel(user: User = Depends(require_member), db: Session = Depends(get_db)):
    user.is_pro = False
    user.is_team = False
    user.pro_since = None
    db.add(Activity(owner_id=user.id, kind="system", title="Plan cancelled", meta="Back to Starter"))
    db.commit()
    return {"plan": "starter", "is_pro": False, "pro_since": ""}
