"""Entradas M1 estrictas; auditoría y procedencia derivadas en servidor."""
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
import unicodedata
from pydantic import AwareDatetime, Field, StrictBool, StrictInt, StrictFloat, field_validator, model_validator
from app.schemas.s1 import ContractModel
from app.schemas.s2 import Origin, Snapshot

Code = Annotated[str, Field(min_length=3, max_length=40)]
Name = Annotated[str, Field(min_length=1, max_length=160)]
Version = Annotated[StrictInt, Field(ge=1)]
Metric = StrictInt | StrictFloat
Feature = Literal['average_grade','attendance_pct','activities_pct','participation_level','behavior_incidents']


def normalize_code(value):
    if not isinstance(value, str):
        raise ValueError('Escribe un código válido.')
    return ' '.join(unicodedata.normalize('NFKC', value).split()).upper()


def normalize_name(value):
    if not isinstance(value, str):
        raise ValueError('Escribe un nombre válido.')
    return ' '.join(unicodedata.normalize('NFC', value).split())


class Command(ContractModel):
    creation_key: UUID


class PeriodCreate(Command):
    code: Annotated[str, Field(min_length=1, max_length=40)]
    school_year: StrictInt = Field(ge=2000, le=2100)
    start_date: date
    end_date: date
    data_origin: Origin
    _code = field_validator('code', mode='before')(normalize_code)

    @model_validator(mode='after')
    def dates(self):
        if not self.start_date < self.end_date or self.start_date.year != self.school_year or self.end_date.year != self.school_year:
            raise ValueError('Las fechas deben estar ordenadas y pertenecer al año escolar.')
        return self


class PeriodPatch(PeriodCreate):
    expected_version: Version
    is_locked: StrictBool


class SectionCreate(Command):
    code: Annotated[str, Field(min_length=1, max_length=40)]
    grade: StrictInt = Field(ge=1, le=5)
    school_year: StrictInt = Field(ge=2000, le=2100)
    tutor_id: UUID
    data_origin: Origin
    _code = field_validator('code', mode='before')(normalize_code)


class SectionPatch(SectionCreate):
    expected_version: Version


class StudentCreate(Command):
    anon_code: Code
    full_name: Name
    period_id: UUID
    section_id: UUID
    _code = field_validator('anon_code', mode='before')(normalize_code)

    _name = field_validator('full_name', mode='before')(normalize_name)


class StudentPatch(Command):
    expected_version: Version
    full_name: Name
    is_active: StrictBool
    confirmed: StrictBool
    reason: Annotated[str, Field(min_length=3, max_length=1000)]
    _name = field_validator('full_name', mode='before')(normalize_name)


class EnrollmentCreate(Command):
    student_id: UUID
    period_id: UUID
    section_id: UUID


class EnrollmentPatch(Command):
    section_id: UUID
    expected_version: Version


class Identity(ContractModel):
    id: UUID
    anon_code: str
    full_name: str | None
    data_origin: Origin
    is_active: bool
    version: int


class EnrollmentView(ContractModel):
    id: UUID
    student_id: UUID
    period_id: UUID
    section_id: UUID
    data_origin: Origin
    version: int


class MeasurementCreate(Command):
    window_start: date
    cutoff_at: AwareDatetime
    available_at: AwareDatetime
    purpose: Literal['PARTIAL','CLOSING_REFERENCE']
    average_grade: Annotated[Metric, Field(ge=0, le=20, allow_inf_nan=False)] | None = None
    attendance_pct: Annotated[Metric, Field(ge=0, le=100, allow_inf_nan=False)] | None = None
    activities_pct: Annotated[Metric, Field(ge=0, le=100, allow_inf_nan=False)] | None = None
    participation_level: Annotated[StrictInt, Field(ge=1, le=5)] | None = None
    behavior_incidents: Annotated[StrictInt, Field(ge=0, le=2147483647)] | None = None
    variable_available_at: dict[Feature, AwareDatetime] = Field(default_factory=dict)
    supersedes_id: UUID | None = None
    expected_revision: Version | None = None
    correction_reason: Annotated[str, Field(min_length=3, max_length=1000)] | None = None

    @model_validator(mode='after')
    def content(self):
        if not any(getattr(self, key) is not None for key in ('average_grade','attendance_pct','activities_pct','participation_level','behavior_incidents')):
            raise ValueError('Registra al menos una variable; vacío es distinto de cero.')
        if self.supersedes_id and (not self.expected_revision or not self.correction_reason or not self.correction_reason.strip()):
            raise ValueError('La corrección exige revisión esperada y motivo.')
        if not self.supersedes_id and (self.expected_revision is not None or self.correction_reason is not None):
            raise ValueError('Una primera medición no corrige otra revisión.')
        return self


class MeasurementPage(ContractModel):
    items: list[Snapshot]
    total: int
    page: int
    page_size: int
