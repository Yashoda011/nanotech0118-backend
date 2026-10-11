"""Seed demo workspace for a user — mirrors frontend src/data/seeds.ts."""

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from .models import Activity, Dataset, Notification, Project, Task


def _ago(h: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=h)


SEED_PROJECTS = [
    {"name": "Nano Sensor", "description": "Room-temperature gas sensor array based on ZnO nanorods and graphene interconnects.",
     "status": "Planning", "ago": 26,
     "tasks": [("Define target analytes", True), ("Order nanorod substrates", False), ("Draft baseline schematic", False)]},
    {"name": "Conductive Ink v2", "description": "Silver nanoparticle ink with 45% lower sintering temperature.",
     "status": "Active", "ago": 120,
     "tasks": [("Bench viscosity tests", True), ("Print test traces on PET", True), ("Resistance after 500 bend cycles", False)]},
    {"name": "TiO2 Self-Cleaning Film", "description": "Spray-coated anatase film for glazing panels.",
     "status": "Review", "ago": 300,
     "tasks": [("Methylene blue decay run", True), ("Write comparison summary", False)]},
]


def seed_user(db: Session, user) -> None:
    for p in SEED_PROJECTS:
        proj = Project(owner_id=user.id, name=p["name"], description=p["description"],
                       status=p["status"], created_at=_ago(p["ago"]))
        db.add(proj)
        db.flush()
        for title, done in p["tasks"]:
            db.add(Task(project_id=proj.id, title=title, done=done))
    db.add(Dataset(owner_id=user.id, name="graphene-conductivity.csv", source="seed",
                   uploaded_at=_ago(6),
                   series=[{"name": "Sheet conductivity", "unit": "kS/sq",
                             "points": [{"label": f"{t}K", "value": v} for t, v in
                                        [(300, 42), (325, 45), (350, 47), (375, 46), (400, 44), (425, 41), (450, 38), (475, 35), (500, 32)]]}],
                   stats={"Sheet conductivity": {"count": 9, "mean": 41.11}}))
    for kind, title, meta, ago in [
        ("search", 'You searched for "Carbon Nanotube"', "Explore Nanomaterials", 2),
        ("simulation", "Simulation completed · Graphene", "Electron transport model", 4),
        ("dataset", "New dataset uploaded", "graphene-conductivity.csv", 6),
        ("project", 'Project "Nano Sensor" created', "Status: Planning", 26),
    ]:
        db.add(Activity(owner_id=user.id, kind=kind, title=title, meta=meta, created_at=_ago(ago)))
    for title, body, read, ago in [
        ("Simulation finished", "Graphene · electron transport run #42 completed with peak 68.4.", False, 4),
        ("Dataset processed", "graphene-conductivity.csv parsed successfully — 24 rows.", False, 6),
        ("Weekly research digest", "6 new papers matched your graphene and 2D material interests.", True, 30),
    ]:
        db.add(Notification(owner_id=user.id, title=title, body=body, read=read, created_at=_ago(ago)))
    db.commit()
