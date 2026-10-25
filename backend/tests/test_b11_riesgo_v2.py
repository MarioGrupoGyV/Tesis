"""Bloque 8 (ADR 013): RIESGO_V2 sin participación junto a RIESGO_V1 intacta, y migración 0009 sobre una base limpia.

Casos generados aquí (ningún dato real). El esperado de cada frontera se escribe a mano.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.services.risk_reference import (ACTIVE_RULE_VERSION, ClosingInputs, InvalidClosingInputs, compute, compute_riesgo_v1, compute_riesgo_v2,
                                         level_of, level_of_v2)
from conftest import create_context
from test_b3_migration import new_database
from test_s1_schema import assert_sqlstate


def inputs(**changes):
    """Insumos con todos los componentes en 0 puntos; cada prueba mueve solo el que verifica."""
    base = dict(average_grade=Decimal('16'), days_scheduled=45, days_attended=45, activities_scheduled=24,
                activities_delivered=24, participation_level=5, behavior_incidents=0)
    base.update(changes)
    return ClosingInputs(**base)


# ---------------------------------------------------------------- regla pura
def test_v2_is_the_active_rule_and_the_baseline_has_zero_points():
    assert ACTIVE_RULE_VERSION == 'RIESGO_V2'
    result = compute_riesgo_v2(inputs())
    assert result.rule_version == 'RIESGO_V2' and result.total_points == 0 and result.risk_level == 'LOW'
    assert result.points_participation is None and result.components == (0, 0, 0, 0)


@pytest.mark.parametrize('total,level', [(0, 'LOW'), (1, 'LOW'), (2, 'MEDIUM'), (3, 'MEDIUM'), (4, 'HIGH'), (8, 'HIGH')])
def test_v2_level_borders(total, level):
    assert level_of_v2(total) == level


@pytest.mark.parametrize('changes,total,level', [
    (dict(behavior_incidents=1), 1, 'LOW'),                                                   # 1 → Bajo
    (dict(behavior_incidents=3), 2, 'MEDIUM'),                                                # 2 → Medio
    (dict(behavior_incidents=3, average_grade=Decimal('13.99')), 3, 'MEDIUM'),                # 3 → Medio
    (dict(behavior_incidents=3, average_grade=Decimal('10.99')), 4, 'HIGH'),                  # 4 → Alto
    (dict(behavior_incidents=3, average_grade=Decimal('10'), days_attended=35, activities_delivered=14), 8, 'HIGH'),   # 8 = máximo
])
def test_v2_totals_on_the_level_borders(changes, total, level):
    result = compute_riesgo_v2(inputs(**changes))
    assert (result.total_points, result.risk_level) == (total, level) and sum(result.components) == total


@pytest.mark.parametrize('grade,points', [('10.99', 2), ('10.995', 1), ('11', 1), ('13.99', 1), ('13.995', 0), ('14', 0)])
def test_v2_grade_thresholds_use_the_rounded_mean(grade, points):
    assert compute_riesgo_v2(inputs(average_grade=Decimal(grade))).points_grade == points


@pytest.mark.parametrize('attended,points', [(7999, 2), (8000, 1), (8999, 1), (9000, 0)])
def test_v2_attendance_thresholds_with_integer_arithmetic(attended, points):
    assert compute_riesgo_v2(inputs(days_scheduled=10000, days_attended=attended)).points_attendance == points


@pytest.mark.parametrize('delivered,points', [(59, 2), (60, 1), (79, 1), (80, 0)])
def test_v2_activities_thresholds(delivered, points):
    assert compute_riesgo_v2(inputs(activities_scheduled=100, activities_delivered=delivered)).points_activities == points


@pytest.mark.parametrize('incidents,points', [(0, 0), (1, 1), (2, 1), (3, 2), (12, 2)])
def test_v2_incident_thresholds(incidents, points):
    assert compute_riesgo_v2(inputs(behavior_incidents=incidents)).points_conduct == points


@pytest.mark.parametrize('participation', [None, 1, 3, 5, 9, -4])
def test_v2_ignores_participation_entirely(participation):
    result = compute_riesgo_v2(inputs(participation_level=participation, behavior_incidents=2))
    assert result.points_participation is None and result.total_points == 1 and result.risk_level == 'LOW'


def test_v2_still_validates_the_other_inputs():
    for changes in (dict(days_attended=46), dict(activities_delivered=25), dict(average_grade=Decimal('20.01')), dict(behavior_incidents=-1),
                    dict(days_scheduled=0)):
        with pytest.raises(InvalidClosingInputs):
            compute_riesgo_v2(inputs(**changes))


def test_v1_is_unchanged():
    # Mismos casos que fijaban V1 antes del bloque 8: cinco componentes, Alto ≥ 5, participación obligatoria.
    assert compute_riesgo_v1(inputs()).total_points == 0 and level_of(4) == 'MEDIUM' and level_of(5) == 'HIGH'
    low_participation = compute_riesgo_v1(inputs(participation_level=2))
    assert low_participation.points_participation == 2 and low_participation.risk_level == 'MEDIUM' and low_participation.rule_version == 'RIESGO_V1'
    four = compute_riesgo_v1(inputs(behavior_incidents=3, average_grade=Decimal('10.99')))
    assert (four.total_points, four.risk_level) == (4, 'MEDIUM')                              # V2 lo llama Alto; V1 no cambia
    assert compute_riesgo_v2(inputs(behavior_incidents=3, average_grade=Decimal('10.99'))).risk_level == 'HIGH'
    with pytest.raises(InvalidClosingInputs):
        compute_riesgo_v1(inputs(participation_level=None))
    with pytest.raises(InvalidClosingInputs):
        compute_riesgo_v1(inputs(participation_level=9))
    assert compute('RIESGO_V1', inputs(participation_level=2)) == low_participation
    with pytest.raises(InvalidClosingInputs, match='UNKNOWN_RULE_VERSION'):
        compute('RIESGO_V3', inputs())


# ---------------------------------------------------------------- migración 0009 en una base limpia
REFERENCE = """INSERT INTO risk_school.risk_references(id,enrollment_id,period_id,data_origin,snapshot_id,bimester,rule_version,closing_date,
    closing_available_at,average_grade,days_scheduled,days_attended,activities_scheduled,activities_delivered,participation_level,behavior_incidents,
    points_grade,points_attendance,points_activities,points_participation,points_conduct,total_points,risk_level,computed_by)
    VALUES(:id,:e,:p,'REAL',:s,'B1',:rule,'2026-05-02','2026-05-03T15:00:00Z',:grade,45,45,24,24,:participation,:incidents,
    :pg,0,0,:pp,:pc,:total,:level,:a)"""


def row(ids, actor, **values):
    base = dict(id=uuid4(), e=ids['enrollment'], p=ids['period'], s=ids['snapshot'], a=actor, rule='RIESGO_V2', grade=16, participation=None,
                incidents=0, pg=0, pp=None, pc=0, total=0, level='LOW')
    base.update(values)
    return base


def test_migration_0009_keeps_v1_rows_untouched_and_enforces_each_rule(database_urls, synthetic_password, synthetic_password_hash):
    name, migrate = new_database(database_urls, 'b11_v2')
    migrate('0008_real_chain')
    engine = create_engine(make_url(database_urls[1]).set(database=name), hide_parameters=True)
    ids = {key: uuid4() for key in ('student', 'enrollment', 'batch', 'snapshot', 'v1')}
    with engine.begin() as db:
        context = create_context(db, synthetic_password, synthetic_password_hash)
        ids['period'], section, actor = context['periods']['real']['id'], context['sections'][0]['id'], context['accounts']['ADMIN']['id']
        # Fixture histórico en una base desechable: sin triggers de usuario en las tablas del corte (no en risk_references).
        for table in ('students', 'enrollments', 'import_batches', 'academic_snapshots'):
            db.execute(text(f'ALTER TABLE risk_school.{table} DISABLE TRIGGER USER'))
        db.execute(text("INSERT INTO risk_school.students(id,anon_code,data_origin) VALUES(:id,:code,'REAL')"),
                   {'id': ids['student'], 'code': 'B11-' + uuid4().hex[:10]})
        db.execute(text("INSERT INTO risk_school.enrollments(id,student_id,period_id,section_id,data_origin) VALUES(:id,:s,:p,:g,'REAL')"),
                   {'id': ids['enrollment'], 's': ids['student'], 'p': ids['period'], 'g': section})
        db.execute(text("""INSERT INTO risk_school.import_batches(id,period_id,data_origin,created_by,file_name,file_sha256,storage_key)
            VALUES(:id,:p,'REAL',:a,'fixture.csv',repeat('a',64),'fixture.csv')"""), {'id': ids['batch'], 'p': ids['period'], 'a': actor})
        db.execute(text("""INSERT INTO risk_school.academic_snapshots(id,enrollment_id,period_id,data_origin,import_batch_id,window_start,
            cutoff_at,available_at,target_date,average_grade,missing_fraction,source_row_number,row_sha256)
            VALUES(:id,:e,:p,'REAL',:b,'2026-01-01','2026-04-21T17:00:00Z','2026-04-21T16:00:00Z','2026-05-02',10,0.8,2,repeat('b',64))"""),
            {'id': ids['snapshot'], 'e': ids['enrollment'], 'p': ids['period'], 'b': ids['batch']})
        for table in ('students', 'enrollments', 'import_batches', 'academic_snapshots'):
            db.execute(text(f'ALTER TABLE risk_school.{table} ENABLE TRIGGER USER'))
        # Fila V1 existente antes de 0009: participación 2 (2 puntos) e incidencias 3 (2 puntos) → 4 = Medio en V1.
        db.execute(text(REFERENCE), row(ids, actor, id=ids['v1'], rule='RIESGO_V1', participation=2, pp=2, incidents=3, pc=2, total=4, level='MEDIUM'))
    with engine.connect() as db:
        columns = [c['name'] for c in inspect(db).get_columns('risk_references', schema='risk_school')]
        snapshot = 'SELECT to_jsonb(x)::text FROM (SELECT {} FROM risk_school.risk_references WHERE id=:id) x'.format(','.join(columns))
        before = db.scalar(text(snapshot), {'id': ids['v1']})
    migrate('0009_riesgo_v2')
    with engine.connect() as db:
        assert db.scalar(text('SELECT version_num FROM alembic_version')) == '0009_riesgo_v2'
        assert db.scalar(text(snapshot), {'id': ids['v1']}) == before                       # la fila V1 no cambia
        nullable = {c['name']: c['nullable'] for c in inspect(db).get_columns('risk_references', schema='risk_school')}
        assert nullable['participation_level'] and nullable['points_participation'] and not nullable['total_points']
        assert 'RIESGO_V2' in db.scalar(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='protocol_risk_rule_version'"))
        assert_sqlstate(db, 'UPDATE risk_school.risk_references SET risk_level=\'HIGH\' WHERE id=:id', {'id': ids['v1']}, '55000')   # sigue inmutable
    actor = context['accounts']['ADMIN']['id']
    # V2 válida para el mismo corte (fila nueva, revision 1): mismos insumos sin participación → 2 puntos = Medio.
    with engine.begin() as db:
        db.execute(text(REFERENCE), row(ids, actor, incidents=3, pc=2, total=2, level='MEDIUM'))
    invalid = [
        dict(participation=3),                                                  # V2 con participación
        dict(pp=0),                                                             # V2 con puntaje de participación
        dict(incidents=3, pc=2, total=2, level='LOW'),                          # nivel incoherente con el total
        dict(grade=10, pg=2, incidents=3, pc=2, total=4, level='MEDIUM'),       # 4 en V2 es Alto
        dict(incidents=3, pc=2, total=3, level='MEDIUM'),                       # total que no es la suma de cuatro componentes
        dict(rule='RIESGO_V3'),                                                 # regla desconocida
        dict(rule='RIESGO_V1', participation=None, pp=None),                    # V1 sin participación
        dict(rule='RIESGO_V1', participation=5, pp=0, incidents=3, pc=2, total=2, level='LOW'),   # V1 conserva su regla de nivel
    ]
    for values in invalid:
        with engine.connect() as db:
            assert_sqlstate(db, REFERENCE, row(ids, actor, id=uuid4(), s=ids['snapshot'], **values), '23514')
    with engine.connect() as db:
        counts = dict(db.execute(text('SELECT rule_version, count(*) FROM risk_school.risk_references GROUP BY 1')).all())
        assert counts == {'RIESGO_V1': 1, 'RIESGO_V2': 1}
        # Una segunda V2 revision 1 del mismo corte es un duplicado (inmutable, insert-only).
        assert_sqlstate(db, REFERENCE, row(ids, actor, incidents=3, pc=2, total=2, level='MEDIUM'), '23505')
    engine.dispose()
