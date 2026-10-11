from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Activity, Notification, SavedMaterial, SearchHistory, User
from ..schemas import ActivityOut, NotificationOut, SearchIn, SettingsUpdate, UserOut

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


@router.get("/activities", response_model=list[ActivityOut])
def activities(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Activity).filter(Activity.owner_id == user.id).order_by(Activity.created_at.desc()).limit(40).all()
    return [{"id": r.id, "kind": r.kind, "title": r.title, "meta": r.meta or "", "at": _iso(r.created_at)} for r in rows]


@router.post("/activities/log")
def log_activity(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = Activity(owner_id=user.id, kind=str(body.get("kind", "system"))[:20],
                 title=str(body.get("title", ""))[:400], meta=str(body.get("meta", ""))[:400])
    db.add(a)
    db.commit()
    return {"ok": True}


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.owner_id == user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return [{"id": r.id, "title": r.title, "body": r.body or "", "read": r.read, "at": _iso(r.created_at)} for r in rows]


@router.post("/notifications/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.owner_id == user.id).update({"read": True})
    db.commit()
    return {"ok": True}


@router.delete("/notifications")
def clear_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.owner_id == user.id).delete()
    db.commit()
    return {"ok": True}


@router.get("/saved")
def get_saved(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(SavedMaterial).filter(SavedMaterial.owner_id == user.id).all()
    return {"saved": [r.material_id for r in rows]}


@router.post("/saved/{material_id}")
def toggle_saved(material_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    existing = db.query(SavedMaterial).filter(SavedMaterial.owner_id == user.id,
                                              SavedMaterial.material_id == material_id).first()
    if existing:
        db.delete(existing)
        saved = False
    else:
        db.add(SavedMaterial(owner_id=user.id, material_id=material_id[:80]))
        saved = True
    db.commit()
    return {"saved": saved}


@router.get("/search-history")
def get_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(SearchHistory).filter(SearchHistory.owner_id == user.id)
            .order_by(SearchHistory.created_at.desc()).limit(8).all())
    return {"history": [r.term for r in rows]}


@router.post("/search-history")
def push_search(body: SearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    term = body.term.strip()
    if term:
        db.add(SearchHistory(owner_id=user.id, term=term[:300]))
        db.add(Activity(owner_id=user.id, kind="search", title=f'You searched for "{term}"',
                        meta="Explore Nanomaterials"))
        db.commit()
    return {"ok": True}


@router.patch("/settings", response_model=UserOut)
def update_settings(body: SettingsUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        user.name = body.name.strip() or user.name
    if body.email is not None:
        user.email = body.email.strip().lower()
    if body.role is not None:
        user.role = body.role[:120]
    if body.density is not None:
        user.density = body.density
    if body.default_metric is not None:
        user.default_metric = body.default_metric[:20]
    if body.email_digest is not None:
        user.email_digest = body.email_digest
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "density": user.density, "default_metric": user.default_metric, "email_digest": user.email_digest}


@router.post("/reset")
def reset_workspace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..seed import seed_user
    # delete user data (keep account)
    for m in (SearchHistory, SavedMaterial, Notification, Activity):
        db.query(m).filter(m.owner_id == user.id).delete()
    from ..models import Dataset, Project
    db.query(Dataset).filter(Dataset.owner_id == user.id).delete()
    db.query(Project).filter(Project.owner_id == user.id).delete()
    db.commit()
    seed_user(db, user)
    return {"ok": True}
