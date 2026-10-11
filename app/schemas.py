"""Pydantic schemas for request/response."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field

# ---------- Auth ----------
class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    density: str
    default_metric: str
    email_digest: bool
    email_verified: bool = False
    is_admin: bool = False

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Projects ----------
ProjectStatus = Literal["Planning", "Active", "Review", "Completed"]

class TaskOut(BaseModel):
    id: str
    title: str
    done: bool

    class Config:
        from_attributes = True


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    status: str
    createdAt: str
    tasks: list[TaskOut]

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    status: ProjectStatus = "Planning"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    status: ProjectStatus | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)


# ---------- Datasets ----------
class DatasetPoint(BaseModel):
    label: str
    value: float


class DatasetSeries(BaseModel):
    name: str
    unit: str = ""
    points: list[DatasetPoint]


class DatasetOut(BaseModel):
    id: str
    name: str
    source: str
    uploadedAt: str
    series: list[DatasetSeries]
    stats: dict = {}


# ---------- Workspace ----------
class ActivityOut(BaseModel):
    id: str
    kind: str
    title: str
    meta: str = ""
    at: str


class NotificationOut(BaseModel):
    id: str
    title: str
    body: str
    read: bool
    at: str


class SettingsUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    density: Literal["comfortable", "compact"] | None = None
    default_metric: str | None = None
    email_digest: bool | None = None


class SearchIn(BaseModel):
    term: str = Field(min_length=1, max_length=300)


# ---------- Science ----------
class SimulationIn(BaseModel):
    materialId: str = Field(min_length=1, max_length=80)
    electricalIndex: float = Field(ge=0, le=100)
    model: Literal["electron", "thermal", "tensile"] = "electron"
    temperatureK: float = Field(ge=10, le=2000)
    sizeNm: float = Field(ge=0.1, le=10000)
    iterations: int = Field(ge=1, le=10000)


class LabCalcIn(BaseModel):
    calc: Literal["scherrer", "dilution", "wavelength"]
    fwhmDeg: float | None = None
    thetaDeg: float | None = None
    lambdaNm: float | None = None
    c1: float | None = None
    v1: float | None = None
    c2: float | None = None
    ev: float | None = None
    nm: float | None = None


class HealthOut(BaseModel):
    status: str
    db: str
    version: str = "1.0.0"
