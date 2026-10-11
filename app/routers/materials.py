"""DB-backed materials catalogue: search, category filter, sorting."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Material, User

router = APIRouter(prefix="/materials", tags=["materials"])


def _full(m: Material) -> dict:
    d = dict(m.data or {})
    return {"id": m.id, "name": m.name, "formula": m.formula, "category": m.category, **d}


@router.get("")
def list_materials(
    q: str = Query(default="", max_length=120),
    category: str = Query(default="", max_length=60),
    sort: str = Query(default="name", pattern="^(name|conductivity|bandgap|newest)$"),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Material).all()
    items = [_full(m) for m in rows]
    needle = q.strip().lower()
    if needle:
        items = [m for m in items
                 if needle in m["name"].lower() or needle in m["formula"].lower()
                 or needle in m.get("tagline", "").lower()
                 or any(needle in a.lower() for a in m.get("applications", []))]
    if category and category != "All":
        items = [m for m in items if m["category"] == category]
    if sort == "name":
        items.sort(key=lambda m: m["name"])
    elif sort == "conductivity":
        items.sort(key=lambda m: m.get("numbers", {}).get("conductivity", 0), reverse=True)
    elif sort == "bandgap":
        items.sort(key=lambda m: m.get("numbers", {}).get("bandGap", 0))
    else:
        items.sort(key=lambda m: m.get("year", 0), reverse=True)
    return {"materials": items, "total": len(items), "source": "database"}


@router.get("/{material_id}")
def get_material(material_id: str, _user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(Material, material_id)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    return _full(m)
