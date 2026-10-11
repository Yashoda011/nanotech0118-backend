"""SQLAlchemy models — mirrors frontend src/data/seeds.ts + auth."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("usr"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="email")
    phone: Mapped[str] = mapped_column(String(30), default="")
    role: Mapped[str] = mapped_column(String(120), default="Principal Researcher")
    density: Mapped[str] = mapped_column(String(20), default="comfortable")
    default_metric: Mapped[str] = mapped_column(String(20), default="electrical")
    email_digest: Mapped[bool] = mapped_column(Boolean, default=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_pro: Mapped[bool] = mapped_column(Boolean, default=False)
    pro_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    is_team: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    activities: Mapped[list["Activity"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("proj"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Planning")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped["User"] = relationship(back_populates="projects")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("task"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, default=False)

    project: Mapped["Project"] = relationship(back_populates="tasks")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("ds"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="upload")
    file_path: Mapped[str] = mapped_column(Text, default="")
    series: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)  # pandas describe() output
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped["User"] = relationship(back_populates="datasets")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("act"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="system")
    title: Mapped[str] = mapped_column(String(400))
    meta: Mapped[str] = mapped_column(String(400), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped["User"] = relationship(back_populates="activities")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("notif"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    owner: Mapped["User"] = relationship(back_populates="notifications")


class SavedMaterial(Base):
    __tablename__ = "saved_materials"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    material_id: Mapped[str] = mapped_column(String(80), primary_key=True)


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    term: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Enrollment(Base):
    """Course enrollment — members only (guests blocked at the API layer)."""

    __tablename__ = "enrollments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("enr"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CourseProgress(Base):
    """Per-lesson completion + best quiz score, owned by the member."""

    __tablename__ = "course_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[str] = mapped_column(String(80), index=True)
    lesson_id: Mapped[str] = mapped_column(String(80))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    best_score: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Purchase(Base):
    """Mock checkout record — required to enroll after the free offer ends."""

    __tablename__ = "purchases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("pay"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[str] = mapped_column(String(80), index=True)
    amount_cents: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EmailToken(Base):
    """6-digit verification code with expiry. Single active code per user."""

    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Material(Base):
    """DB-backed nanomaterials catalogue (searchable columns + full JSON)."""

    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    formula: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Article(Base):
    """Verified-source research summaries (bundled catalogue)."""

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(400))
    source: Mapped[str] = mapped_column(String(200))
    date: Mapped[str] = mapped_column(String(20))
    read_minutes: Mapped[int] = mapped_column(default=5)
    art: Mapped[str] = mapped_column(String(20), default="future")
    accent: Mapped[str] = mapped_column(String(20), default="#8b5cf6")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    body: Mapped[list] = mapped_column(JSON, default=list)


class LessonRow(Base):
    """Course lesson content (tutorials stored in the database)."""

    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(String(80), index=True)
    lesson_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(300))
    minutes: Mapped[int] = mapped_column(default=5)
    body: Mapped[list] = mapped_column(JSON, default=list)
    quiz: Mapped[list] = mapped_column(JSON, default=list)


class GlossaryTerm(Base):
    __tablename__ = "glossary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    definition: Mapped[str] = mapped_column(Text)
    tag: Mapped[str] = mapped_column(String(60), default="General")


class SimRun(Base):
    """Historical experiment record: every backend simulation, timestamped."""

    __tablename__ = "sim_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("run"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    material_id: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(20))
    temperature_k: Mapped[float] = mapped_column(default=300)
    size_nm: Mapped[float] = mapped_column(default=10)
    iterations: Mapped[int] = mapped_column(default=100)
    peak: Mapped[float] = mapped_column(default=0)
    mean: Mapped[float] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Ticket(Base):
    """Contact / support submissions."""

    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("tkt"))
    owner_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Batch(Base):
    """Industrial production batch — backend-owned business data."""

    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("batch"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    material_id: Mapped[str] = mapped_column(String(80))
    kg: Mapped[float] = mapped_column(default=0)
    yield_pct: Mapped[float] = mapped_column(default=0)
    qc_pass: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Thread(Base):
    """Community discussion thread."""

    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("th"))
    owner_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    tag: Mapped[str] = mapped_column(String(60), default="General")
    author: Mapped[str] = mapped_column(String(120), default="Member")
    likes_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    replies: Mapped[list["Reply"]] = relationship(back_populates="thread", cascade="all, delete-orphan")


class Reply(Base):
    __tablename__ = "replies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: _uid("re"))
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=True)
    author: Mapped[str] = mapped_column(String(120), default="Member")
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    thread: Mapped["Thread"] = relationship(back_populates="replies")


class ThreadLike(Base):
    __tablename__ = "thread_likes"

    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), primary_key=True)
