"""Generador y protocolo explícitos de simulación; nunca se ejecutan al arrancar.

Los resultados futuros dependen de trayectorias latentes y perturbaciones nuevas.
Las escalas/umbrales son supuestos de este generador, no reglas de un colegio.
"""
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import numpy as np
from pydantic import Field, model_validator

from app.ml.features import (BASE_FEATURES, Dataset, FeatureConfig, InternalModel, Label,
                             LIMA, MLDiagnostic, Observation, Scale, validate_dataset)

GENERATOR_VERSION = 'synthetic-generator-v1'
HEADERS = ('student_code', 'grade', 'section', 'cutoff_at', 'target_date', 'available_at',
           'window_start', 'average_grade', 'attendance_pct', 'activities_pct',
           'participation_level', 'behavior_incidents', 'age_years')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def instant(day: date, hour=17):
    return datetime.combine(day, time(hour), LIMA).astimezone(UTC)


class FutureCriterion(InternalModel):
    version: Literal['synthetic-future-v1'] = 'synthetic-future-v1'
    high_grade_below: float = 10.0
    high_attendance_below: float = 65.0
    high_incidents_at_least: int = 6
    medium_grade_below: float = 14.0
    medium_attendance_below: float = 85.0
    medium_incidents_at_least: int = 3
    precedence: Literal['HIGH_THEN_MEDIUM_THEN_LOW'] = 'HIGH_THEN_MEDIUM_THEN_LOW'

    @model_validator(mode='after')
    def coherent(self):
        if not (0 <= self.high_grade_below < self.medium_grade_below <= 20 and
                0 <= self.high_attendance_below < self.medium_attendance_below <= 100 and
                0 <= self.medium_incidents_at_least < self.high_incidents_at_least <= 12):
            raise ValueError('INVALID_SYNTHETIC_CRITERION')
        return self

    @property
    def definition(self):
        return ('Hypothetical future simulated outcome: HIGH if future average_grade < '
                f'{self.high_grade_below:g} OR attendance_pct < {self.high_attendance_below:g} OR '
                f'behavior_incidents >= {self.high_incidents_at_least}; otherwise MEDIUM if '
                f'average_grade < {self.medium_grade_below:g} OR attendance_pct < '
                f'{self.medium_attendance_below:g} OR behavior_incidents >= '
                f'{self.medium_incidents_at_least}; otherwise LOW. HIGH takes precedence.')

    def classify(self, outcome):
        if (outcome['average_grade'] < self.high_grade_below or
                outcome['attendance_pct'] < self.high_attendance_below or
                outcome['behavior_incidents'] >= self.high_incidents_at_least):
            return 'HIGH'
        if (outcome['average_grade'] < self.medium_grade_below or
                outcome['attendance_pct'] < self.medium_attendance_below or
                outcome['behavior_incidents'] >= self.medium_incidents_at_least):
            return 'MEDIUM'
        return 'LOW'


class SyntheticStudyConfig(InternalModel):
    version: Literal['synthetic-study-v1'] = 'synthetic-study-v1'
    generator_version: Literal['synthetic-generator-v1'] = GENERATOR_VERSION
    timezone: Literal['America/Lima'] = 'America/Lima'
    student_count: int = Field(default=60, ge=12, le=1000)
    school_year: int = 2025
    period_start: date = date(2025, 1, 1)
    period_end: date = date(2025, 12, 31)
    development_cutoffs: list[date] = Field(default_factory=lambda: [date(2025, 1, 31), date(2025, 2, 28), date(2025, 3, 31)])
    external_cutoffs: list[date] = Field(default_factory=lambda: [date(2025, 7, 31), date(2025, 8, 31), date(2025, 9, 30)])
    fit_date: date = date(2025, 5, 1)
    horizon_days: int = Field(default=14, ge=1, le=90)
    label_delay_days: int = Field(default=1, ge=0, le=7)
    window_days: int = Field(default=30, ge=1, le=90)
    external_fraction: float = Field(default=0.2, gt=0, lt=0.5)
    requested_folds: int = Field(default=5, ge=2, le=5)
    missing_probability: float = Field(default=0.04, ge=0, le=0.2)
    # Distinct decisions: quality selection for evaluation vs operational abstention.
    research_max_missing_fraction: float = Field(default=0.4, ge=0, lt=1)
    inference_max_missing_fraction: float = Field(default=0.4, ge=0, lt=1)
    required_features: list[str] = Field(default_factory=lambda: ['average_grade'])
    abstention_student_every: int = Field(default=17, ge=2, le=1000)
    criterion: FutureCriterion = Field(default_factory=FutureCriterion)
    selection: Literal['DEV_MACRO_F1_THEN_BALANCED_ACCURACY_THEN_FIXED_ORDER'] = 'DEV_MACRO_F1_THEN_BALANCED_ACCURACY_THEN_FIXED_ORDER'

    @model_validator(mode='after')
    def closed_calendar(self):
        cuts = self.development_cutoffs + self.external_cutoffs
        if (not self.development_cutoffs or not self.external_cutoffs or len(cuts) != len(set(cuts)) or
                cuts != sorted(cuts) or self.period_start.year != self.school_year or
                self.period_end.year != self.school_year or self.period_start >= self.period_end or
                min(cuts) - timedelta(days=self.window_days) < self.period_start or
                max(cuts) + timedelta(days=self.horizon_days + self.label_delay_days) > self.period_end or
                max(self.development_cutoffs) + timedelta(days=self.horizon_days + self.label_delay_days) >= self.fit_date or
                self.fit_date >= min(self.external_cutoffs) or
                self.student_count * len(cuts) > 10000 or
                not set(self.required_features) <= set(BASE_FEATURES)):
            raise ValueError('SYNTHETIC_PROTOCOL_TEMPORAL_OR_FEATURE_CONFIGURATION_INVALID')
        return self

    @property
    def features(self):
        bounds = {'average_grade': (0, 20, 2, 'simulated grade /20'),
                  'attendance_pct': (0, 100, 2, 'simulated percentage'),
                  'activities_pct': (0, 100, 2, 'simulated percentage'),
                  'participation_level': (1, 3, 0, 'simulated category 1/2/3'),
                  'behavior_incidents': (0, 12, 0, 'simulated count')}
        return FeatureConfig(criterion_version=self.criterion.version, criterion_definition=self.criterion.definition,
            horizon_days=self.horizon_days, inference_max_missing_fraction=self.inference_max_missing_fraction,
            required_features=self.required_features, participation_values=[1, 2, 3], scales={
                name: Scale(minimum=lo, maximum=hi, decimals=precision, unit=unit)
                for name, (lo, hi, precision, unit) in bounds.items()})


def load_config(path: str | Path | None = None):
    path = Path(path) if path else Path(__file__).with_name('synthetic-study-v1.json')
    return SyntheticStudyConfig.model_validate_json(path.read_bytes())


@dataclass(frozen=True)
class GeneratedStudy:
    study_id: UUID
    period_id: UUID
    csv_bytes: bytes
    dataset: Dataset
    config_json: dict
    manifest_json: dict
    labels_json: dict


def generate(config: SyntheticStudyConfig, seed: int = 1729) -> GeneratedStudy:
    if not 0 <= seed < 2**32:
        raise MLDiagnostic('INVALID_GENERATOR_SEED')
    config = SyntheticStudyConfig.model_validate(config.model_dump())
    config_json = config.model_dump(mode='json')
    config_hash = digest(canonical(config_json))
    study_id = uuid5(NAMESPACE_URL, f'{GENERATOR_VERSION}:{config_hash}:{seed}')
    period_id = uuid5(study_id, 'academic-period')
    prefix = study_id.hex[:8]
    rng = np.random.default_rng(seed)
    student_codes = [f'SYN-{prefix}-{i + 1:04d}' for i in range(config.student_count)]
    shuffled = rng.permutation(config.student_count)
    reserved_count = max(2, int(round(config.student_count * config.external_fraction)))
    external_students = sorted(student_codes[int(i)] for i in shuffled[:reserved_count])
    development_students = sorted(set(student_codes) - set(external_students))
    sections = [{'grade': 1, 'code': f'SYN-{prefix}-A'}, {'grade': 2, 'code': f'SYN-{prefix}-B'}]
    cuts = config.development_cutoffs + config.external_cutoffs
    observations, labels, csv_rows, outcomes = [], [], [], []
    for index, code in enumerate(student_codes):
        # Latent heterogeneity, gradual change and independent observation/future shocks.
        achievement = rng.uniform(8, 19)
        engagement = rng.uniform(55, 99)
        conduct = rng.uniform(0.05, 3.5)
        drift = rng.normal(0, 0.5)
        enrollment = uuid5(study_id, f'enrollment:{code}')
        grade = 1 + index % 2
        section = sections[grade - 1]['code']
        for cut_index, cutoff_day in enumerate(cuts):
            state = achievement + drift * cut_index + rng.normal(0, 0.7)
            engaged = engagement + rng.normal(0, 3)
            values = {'average_grade': round(float(np.clip(state + rng.normal(0, 1.1), 0, 20)), 2),
                      'attendance_pct': round(float(np.clip(engaged + rng.normal(0, 4), 0, 100)), 2),
                      'activities_pct': round(float(np.clip(engaged - 4 + rng.normal(0, 7), 0, 100)), 2),
                      'participation_level': float(np.clip(1 + int((engaged + rng.normal(0, 8)) / 34), 1, 3)),
                      'behavior_incidents': float(min(12, rng.poisson(conduct)))}
            # Futures use new innovations and latent states, never the label as an input.
            future = {'average_grade': round(float(np.clip(state + drift * 0.5 + rng.normal(0, 2.0), 0, 20)), 2),
                      'attendance_pct': round(float(np.clip(engaged + rng.normal(0, 7), 0, 100)), 2),
                      'activities_pct': round(float(np.clip(engaged - 4 + rng.normal(0, 9), 0, 100)), 2),
                      'behavior_incidents': float(min(12, rng.poisson(conduct + 0.15)))}
            for name in BASE_FEATURES:
                if rng.random() < config.missing_probability:
                    values[name] = None
            # Declared non-response examples at the final cut, independent of future risk.
            if (index + 1) % config.abstention_student_every == 0 and cut_index == len(cuts) - 1:
                values = dict.fromkeys(BASE_FEATURES)
            missing_fraction = sum(v is None for v in values.values()) / len(BASE_FEATURES)
            cutoff_at = instant(cutoff_day)
            available_at = cutoff_at - timedelta(hours=1)
            target = cutoff_day + timedelta(days=config.horizon_days)
            snapshot_id = uuid5(enrollment, f'cutoff:{cutoff_day.isoformat()}:revision:1')
            row = Observation(student_key=code, snapshot_id=snapshot_id, enrollment_id=enrollment,
                period_id=period_id, data_origin='SYNTHETIC', revision=1,
                window_start=cutoff_day - timedelta(days=config.window_days), available_at=available_at,
                cutoff_at=cutoff_at, target_date=target, created_at=available_at,
                eligible=missing_fraction <= config.research_max_missing_fraction,
                values=values, feature_available_at={name: available_at for name in BASE_FEATURES},
                input_provenance=f'{GENERATOR_VERSION}:observation')
            label = Label(snapshot_id=snapshot_id, risk=config.criterion.classify(future),
                criterion_version=config.criterion.version, outcome_definition=config.criterion.definition,
                provenance=f'{GENERATOR_VERSION}:future-outcome', observed_at=instant(target),
                available_at=instant(target + timedelta(days=config.label_delay_days)), future_outcome=future)
            observations.append(row)
            labels.append(label)
            csv_rows.append([code, grade, section, cutoff_at.isoformat(), target.isoformat(),
                available_at.isoformat(), row.window_start.isoformat(),
                *['' if values[name] is None else (str(int(values[name])) if name in
                  ('participation_level', 'behavior_incidents') else f'{values[name]:.2f}') for name in BASE_FEATURES],
                12 + grade])
            outcomes.append({'student_code': code, 'cutoff_at': cutoff_at.isoformat(), 'revision': 1,
                             'source_row_number': len(csv_rows) + 1, **label.model_dump(mode='json')})
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(HEADERS)
    writer.writerows(csv_rows)
    csv_bytes = buffer.getvalue().encode('utf-8')
    protocol = {'study_id': str(study_id), 'generator_version': GENERATOR_VERSION,
                'config_hash': config_hash, 'seed': seed, 'development_students': development_students,
                'external_students': external_students, 'config': config_json}
    dataset = Dataset(schema_version='ml-dataset-v2', scope='SYNTHETIC_STUDY',
        provenance=f'{GENERATOR_VERSION}:{config_hash}', evaluation_as_of=instant(config.period_end),
        config=config.features, observations=observations, labels=labels, synthetic_protocol=protocol)
    validate_dataset(dataset, allow_ineligible=True)
    labels_json = {'schema_version': 'synthetic-outcomes-v1', 'data_origin': 'SYNTHETIC',
                   'scope': 'SYNTHETIC_STUDY', 'study_id': str(study_id), 'outcomes': outcomes}
    manifest = {'version': config.version, 'generator_version': GENERATOR_VERSION,
        'scope': 'SYNTHETIC_STUDY', 'data_origin': 'SYNTHETIC', 'study_id': str(study_id),
        'period_id': str(period_id), 'seed': seed, 'config_hash': config_hash,
        'csv_sha256': digest(csv_bytes), 'dataset_sha256': digest(dataset.model_dump_json().encode()),
        'labels_sha256': digest(canonical(labels_json)), 'student_count': config.student_count,
        'observation_count': len(observations), 'eligible_observation_count': sum(r.eligible for r in observations),
        'context': {'school_year': config.school_year, 'period_start': config.period_start.isoformat(),
                    'period_end': config.period_end.isoformat(), 'sections': sections},
        'protocol': protocol,
        'limits': ['Registros y resultados completamente simulados; no corresponden a personas reales.',
                   'Relaciones y métricas condicionadas por el generador; sin evidencia de eficacia escolar.']}
    return GeneratedStudy(study_id, period_id, csv_bytes, dataset, config_json, manifest, labels_json)
