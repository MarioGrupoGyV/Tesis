"""Regla RIESGO_V1 (ADR 012 §4): función pura, independiente del modelo y sin acceso a datos.

Cinco componentes de 0 a 2 puntos. Nivel: Bajo 0–1, Medio 2–4, Alto ≥ 5. Porcentajes con aritmética
entera (sin flotantes) y promedio de notas con Decimal redondeado a 2 decimales (mitad hacia arriba);
la regla se aplica al promedio redondeado.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Literal

RULE_VERSION = 'RIESGO_V1'
Level = Literal['LOW', 'MEDIUM', 'HIGH']
TWO_PLACES = Decimal('0.01')


class InvalidClosingInputs(ValueError):
    """Insumos de cierre fuera de escala o incoherentes; el mensaje es un código sin datos personales."""


@dataclass(frozen=True)
class ClosingInputs:
    average_grade: Decimal
    days_scheduled: int
    days_attended: int
    activities_scheduled: int
    activities_delivered: int
    participation_level: int
    behavior_incidents: int


@dataclass(frozen=True)
class RiskResult:
    points_grade: int
    points_attendance: int
    points_activities: int
    points_participation: int
    points_conduct: int
    total_points: int
    risk_level: Level

    @property
    def components(self):
        return (self.points_grade, self.points_attendance, self.points_activities,
                self.points_participation, self.points_conduct)


def round_grade(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def mean_grade(grades: Iterable) -> Decimal:
    """Media de las notas de curso (igual peso) redondeada a 2 decimales, mitad hacia arriba."""
    values = [Decimal(str(grade)) for grade in grades]
    if not values:
        raise InvalidClosingInputs('NO_COURSE_GRADES')
    return round_grade(sum(values) / len(values))


def level_of(total: int) -> Level:
    return 'HIGH' if total >= 5 else 'MEDIUM' if total >= 2 else 'LOW'


def validated(inputs: ClosingInputs) -> ClosingInputs:
    grade = round_grade(inputs.average_grade)
    ints = (inputs.days_scheduled, inputs.days_attended, inputs.activities_scheduled,
            inputs.activities_delivered, inputs.participation_level, inputs.behavior_incidents)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in ints):
        raise InvalidClosingInputs('NON_INTEGER_COUNTS')
    if not Decimal('0') <= grade <= Decimal('20'):
        raise InvalidClosingInputs('GRADE_OUT_OF_SCALE')
    if inputs.days_scheduled <= 0 or not 0 <= inputs.days_attended <= inputs.days_scheduled:
        raise InvalidClosingInputs('ATTENDANCE_INCONSISTENT')
    if inputs.activities_scheduled <= 0 or not 0 <= inputs.activities_delivered <= inputs.activities_scheduled:
        raise InvalidClosingInputs('ACTIVITIES_INCONSISTENT')
    if not 1 <= inputs.participation_level <= 5:
        raise InvalidClosingInputs('PARTICIPATION_OUT_OF_SCALE')
    if inputs.behavior_incidents < 0:
        raise InvalidClosingInputs('INCIDENTS_NEGATIVE')
    return ClosingInputs(grade, inputs.days_scheduled, inputs.days_attended, inputs.activities_scheduled,
                         inputs.activities_delivered, inputs.participation_level, inputs.behavior_incidents)


def compute_riesgo_v1(inputs: ClosingInputs) -> RiskResult:
    i = validated(inputs)
    grade = 2 if i.average_grade < 11 else 1 if i.average_grade < 14 else 0
    attendance = 2 if 100 * i.days_attended < 80 * i.days_scheduled else 1 if 100 * i.days_attended < 90 * i.days_scheduled else 0
    activities = (2 if 100 * i.activities_delivered < 60 * i.activities_scheduled
                  else 1 if 100 * i.activities_delivered < 80 * i.activities_scheduled else 0)
    participation = 2 if i.participation_level <= 2 else 1 if i.participation_level == 3 else 0
    conduct = 2 if i.behavior_incidents >= 3 else 1 if i.behavior_incidents >= 1 else 0
    total = grade + attendance + activities + participation + conduct
    return RiskResult(grade, attendance, activities, participation, conduct, total, level_of(total))
