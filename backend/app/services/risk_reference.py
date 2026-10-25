"""Reglas de riesgo de referencia: funciones puras, independientes del modelo y sin acceso a datos.

RIESGO_V1 (ADR 012 §4, se conserva intacta para trazabilidad): cinco componentes de 0 a 2 puntos.
Nivel: Bajo 0–1, Medio 2–4, Alto ≥ 5.
RIESGO_V2 (ADR 013, regla activa del estudio REAL): los mismos umbrales y la misma aritmética de V1 sin la
participación (no existe un registro original de la participación en aula). Cuatro componentes, total 0–8.
Nivel: Bajo 0–1, Medio 2–3, Alto ≥ 4 (Alto conserva el 50 % del máximo, como V1). La participación no se lee
ni se valida en V2: si llega en los insumos, se ignora.
Porcentajes con aritmética entera (sin flotantes) y promedio de notas con Decimal redondeado a 2 decimales
(mitad hacia arriba); la regla se aplica al promedio redondeado.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Literal

RULE_VERSION_V1 = 'RIESGO_V1'
RULE_VERSION_V2 = 'RIESGO_V2'
RULE_VERSIONS = (RULE_VERSION_V1, RULE_VERSION_V2)
# Única constante de regla activa: el estudio REAL, los indicadores y la exportación dependen de ella.
ACTIVE_RULE_VERSION = RULE_VERSION_V2
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
    participation_level: int | None          # obligatoria en V1; en V2 puede ser None y se ignora
    behavior_incidents: int


@dataclass(frozen=True)
class RiskResult:
    points_grade: int
    points_attendance: int
    points_activities: int
    points_participation: int | None         # None en V2
    points_conduct: int
    total_points: int
    risk_level: Level
    rule_version: str = RULE_VERSION_V1

    @property
    def components(self):
        if self.rule_version == RULE_VERSION_V2:
            return (self.points_grade, self.points_attendance, self.points_activities, self.points_conduct)
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


def level_of_v2(total: int) -> Level:
    return 'HIGH' if total >= 4 else 'MEDIUM' if total >= 2 else 'LOW'


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


def validated_v2(inputs: ClosingInputs) -> ClosingInputs:
    """Como `validated`, pero sin exigir ni validar la participación (V2 no la usa): se devuelve como None."""
    grade = round_grade(inputs.average_grade)
    ints = (inputs.days_scheduled, inputs.days_attended, inputs.activities_scheduled,
            inputs.activities_delivered, inputs.behavior_incidents)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in ints):
        raise InvalidClosingInputs('NON_INTEGER_COUNTS')
    if not Decimal('0') <= grade <= Decimal('20'):
        raise InvalidClosingInputs('GRADE_OUT_OF_SCALE')
    if inputs.days_scheduled <= 0 or not 0 <= inputs.days_attended <= inputs.days_scheduled:
        raise InvalidClosingInputs('ATTENDANCE_INCONSISTENT')
    if inputs.activities_scheduled <= 0 or not 0 <= inputs.activities_delivered <= inputs.activities_scheduled:
        raise InvalidClosingInputs('ACTIVITIES_INCONSISTENT')
    if inputs.behavior_incidents < 0:
        raise InvalidClosingInputs('INCIDENTS_NEGATIVE')
    return ClosingInputs(grade, inputs.days_scheduled, inputs.days_attended, inputs.activities_scheduled,
                         inputs.activities_delivered, None, inputs.behavior_incidents)


def compute_riesgo_v2(inputs: ClosingInputs) -> RiskResult:
    i = validated_v2(inputs)
    grade = 2 if i.average_grade < 11 else 1 if i.average_grade < 14 else 0
    attendance = 2 if 100 * i.days_attended < 80 * i.days_scheduled else 1 if 100 * i.days_attended < 90 * i.days_scheduled else 0
    activities = (2 if 100 * i.activities_delivered < 60 * i.activities_scheduled
                  else 1 if 100 * i.activities_delivered < 80 * i.activities_scheduled else 0)
    conduct = 2 if i.behavior_incidents >= 3 else 1 if i.behavior_incidents >= 1 else 0
    total = grade + attendance + activities + conduct
    return RiskResult(grade, attendance, activities, None, conduct, total, level_of_v2(total), RULE_VERSION_V2)


RULES = {RULE_VERSION_V1: (compute_riesgo_v1, validated), RULE_VERSION_V2: (compute_riesgo_v2, validated_v2)}


def compute(rule_version: str, inputs: ClosingInputs) -> RiskResult:
    """Calcula con la regla indicada (por defecto, quien llama pasa ACTIVE_RULE_VERSION)."""
    try:
        return RULES[rule_version][0](inputs)
    except KeyError:
        raise InvalidClosingInputs('UNKNOWN_RULE_VERSION') from None


def validated_for(rule_version: str, inputs: ClosingInputs) -> ClosingInputs:
    return RULES[rule_version][1](inputs)
