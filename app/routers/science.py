from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import current_user
from ..models import Activity, SimRun, User
from ..schemas import LabCalcIn, SimulationIn
from .. import science as sci

router = APIRouter(prefix="/science", tags=["science"])

FREE_SIMS_PER_DAY = 5


def _sims_used_today(db: Session, user_id: str) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Activity)
        .filter(Activity.owner_id == user_id, Activity.kind == "simulation", Activity.created_at >= start)
        .count()
    )


@router.post("/simulate")
def simulate(body: SimulationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    used = _sims_used_today(db, user.id)
    unlimited = bool(getattr(user, "is_pro", False) or getattr(user, "is_team", False))
    if not unlimited and used >= FREE_SIMS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Daily limit reached ({FREE_SIMS_PER_DAY}/day on Starter) — upgrade to Pro for unlimited simulations.",
        )
    result = sci.run_simulation(body.materialId, body.electricalIndex, body.model,
                                body.temperatureK, body.sizeNm, body.iterations)
    db.add(Activity(owner_id=user.id, kind="simulation",
                    title=f"Simulation completed · {body.materialId}",
                    meta=f"{body.model} @ {body.temperatureK}K"))
    db.add(SimRun(owner_id=user.id, material_id=body.materialId, model=body.model,
                  temperature_k=body.temperatureK, size_nm=body.sizeNm, iterations=body.iterations,
                  peak=result["peak"], mean=result["mean"]))
    db.commit()
    return {**result, "quota": {"used": used + 1, "limit": None if unlimited else FREE_SIMS_PER_DAY, "pro": unlimited}}


@router.get("/runs")
def run_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Historical experiment records with timestamps (latest first)."""
    rows = db.query(SimRun).filter(SimRun.owner_id == user.id).order_by(SimRun.created_at.desc()).limit(50).all()
    def _iso(dt):
        if not dt:
            return ""
        if dt.tzinfo is None:
            from datetime import timezone as _tz
            dt = dt.replace(tzinfo=_tz.utc)
        return dt.isoformat()
    return {"runs": [
        {"id": r.id, "materialId": r.material_id, "model": r.model, "temperatureK": r.temperature_k,
         "sizeNm": r.size_nm, "iterations": r.iterations, "peak": r.peak, "mean": r.mean,
         "at": _iso(r.created_at)} for r in rows
    ]}


@router.post("/lab-calc")
def lab_calc(body: LabCalcIn, _user: User = Depends(current_user)):
    if body.calc == "scherrer":
        value = sci.scherrer_diameter(body.fwhmDeg or 0, body.thetaDeg or 0, body.lambdaNm or 0)
        return {"result": value, "unit": "nm"}
    if body.calc == "dilution":
        value = sci.dilution_volume(body.c1 or 0, body.v1 or 0, body.c2 or 0)
        return {"result": value, "unit": "same as V1"}
    # wavelength / photon energy
    if body.ev:
        return {"result": sci.ev_to_wavelength(body.ev), "unit": "nm"}
    return {"result": sci.wavelength_to_ev(body.nm or 0), "unit": "eV"}
