from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Health(ContractModel):
    status: Literal["ok", "unavailable"]


class User(ContractModel):
    id: UUID
    display_name: str
    role: Literal["ADMIN", "TUTOR", "DIRECTOR", "RESEARCHER"]


class LoginInput(ContractModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class LoginResult(ContractModel):
    user: User
    csrf_token: str
    expires_at: datetime


class Csrf(ContractModel):
    csrf_token: str


class Period(ContractModel):
    id: UUID
    code: str
    school_year: int = Field(ge=2000, le=2100)
    start_date: date
    end_date: date
    data_origin: Literal["DEMO", "REAL"]
    is_locked: bool


class Section(ContractModel):
    id: UUID
    code: str
    grade: int = Field(ge=1, le=5)
    school_year: int = Field(ge=2000, le=2100)
    tutor_id: UUID | None
