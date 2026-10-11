from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_member
from ..models import Activity, Project, Task, User
from ..schemas import ProjectCreate, ProjectOut, ProjectUpdate, TaskCreate, TaskOut

router = APIRouter(prefix="/projects", tags=["projects"])


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


def _project_out(p: Project) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description or "", "status": p.status,
            "createdAt": _iso(p.created_at),
            "tasks": [{"id": t.id, "title": t.title, "done": t.done} for t in p.tasks]}


@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.owner_id == user.id).order_by(Project.created_at.desc()).all()
    return [_project_out(p) for p in projects]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, user: User = Depends(require_member), db: Session = Depends(get_db)):
    p = Project(owner_id=user.id, name=body.name.strip(), description=body.description, status=body.status)
    db.add(p)
    db.add(Activity(owner_id=user.id, kind="project", title=f'Project "{p.name}" created', meta=f"Status: {p.status}"))
    db.commit()
    db.refresh(p)
    return _project_out(p)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, user: User = Depends(require_member), db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id, Project.owner_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.name is not None:
        p.name = body.name.strip()
    if body.description is not None:
        p.description = body.description
    if body.status is not None:
        p.status = body.status
    db.commit()
    db.refresh(p)
    return _project_out(p)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user: User = Depends(require_member), db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id, Project.owner_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(p)
    db.commit()
    return None


@router.post("/{project_id}/tasks", response_model=TaskOut, status_code=201)
def add_task(project_id: str, body: TaskCreate, user: User = Depends(require_member), db: Session = Depends(get_db)):
    p = db.query(Project).filter(Project.id == project_id, Project.owner_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    t = Task(project_id=p.id, title=body.title.strip(), done=False)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, "title": t.title, "done": t.done}


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskOut)
def toggle_task(project_id: str, task_id: str, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = db.query(Task).join(Project).filter(Task.id == task_id, Project.id == project_id,
                                            Project.owner_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    t.done = not t.done
    db.commit()
    db.refresh(t)
    return {"id": t.id, "title": t.title, "done": t.done}


@router.delete("/{project_id}/tasks/{task_id}", status_code=204)
def delete_task(project_id: str, task_id: str, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = db.query(Task).join(Project).filter(Task.id == task_id, Project.id == project_id,
                                            Project.owner_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(t)
    db.commit()
    return None
