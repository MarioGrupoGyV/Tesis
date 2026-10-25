"""Bloque 3B-1: RIESGO_V1 (función pura con casos de frontera) y risk_references (inmutable, calculada por el backend).

Los casos se generan aquí: ningún dato real en el repositorio. El esperado de cada frontera se escribe a mano.
"""
import inspect
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.models.s1 import AppUser
from app.services import risk_reference_store as store
from app.services.risk_reference import (ClosingInputs, InvalidClosingInputs, compute_riesgo_v1, mean_grade, level_of)
from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)
from test_b1_manual_evaluation import demo  # noqa: F401
from test_s1_schema import assert_sqlstate

LIMA = ZoneInfo('America/Lima')


def inputs(**changes):
    """Insumos con los cinco componentes en 0 puntos; cada prueba mueve solo el que verifica."""
    base = dict(average_grade=Decimal('16'), days_scheduled=45, days_attended=45, activities_scheduled=24,
                activities_delivered=24, participation_level=5, behavior_incidents=0)
    base.update(changes)
    return ClosingInputs(**base)


def test_baseline_has_zero_points():
    result = compute_riesgo_v1(inputs())
    assert result.components == (0, 0, 0, 0, 0) and result.total_points == 0 and result.risk_level == 'LOW'


@pytest.mark.parametrize('grade,points', [('10.99', 2), ('11', 1), ('11.00', 1), ('13.99', 1), ('14', 0), ('14.00', 0),
                                           ('0', 2), ('20', 0), ('10.994', 2), ('10.995', 1)])  # 10.995 → 11.00 (mitad hacia arriba)
def test_grade_boundaries(grade, points):
    assert compute_riesgo_v1(inputs(average_grade=Decimal(grade))).points_grade == points


@pytest.mark.parametrize('attended,points', [(7999, 2), (8000, 1), (8999, 1), (9000, 0)])  # 79,99 / 80 / 89,99 / 90 %
def test_attendance_boundaries_use_integer_arithmetic(attended, points):
    assert compute_riesgo_v1(inputs(days_scheduled=10000, days_attended=attended)).points_attendance == points


@pytest.mark.parametrize('delivered,points', [(59, 2), (60, 1), (79, 1), (80, 0)])
def test_activities_boundaries(delivered, points):
    assert compute_riesgo_v1(inputs(activities_scheduled=100, activities_delivered=delivered)).points_activities == points


@pytest.mark.parametrize('level,points', [(1, 2), (2, 2), (3, 1), (4, 0), (5, 0)])
def test_participation_boundaries(level, points):
    assert compute_riesgo_v1(inputs(participation_level=level)).points_participation == points


@pytest.mark.parametrize('incidents,points', [(0, 0), (1, 1), (2, 1), (3, 2), (9, 2)])
def test_conduct_boundaries(incidents, points):
    assert compute_riesgo_v1(inputs(behavior_incidents=incidents)).points_conduct == points


@pytest.mark.parametrize('changes,total,level', [
    (dict(average_grade=Decimal('13')), 1, 'LOW'),                                                  # 1 punto: Bajo
    (dict(average_grade=Decimal('10')), 2, 'MEDIUM'),                                               # 2 puntos: frontera Medio/Bajo
    (dict(average_grade=Decimal('10'), days_attended=30), 4, 'MEDIUM'),                             # 4 puntos: Medio
    (dict(average_grade=Decimal('10'), days_attended=30, activities_delivered=15), 5, 'HIGH'),      # 5 puntos: frontera Alto/Medio
    (dict(average_grade=Decimal('10'), days_attended=30, activities_delivered=10, participation_level=1,
          behavior_incidents=4), 10, 'HIGH')])
def test_total_and_level_boundaries(changes, total, level):
    result = compute_riesgo_v1(inputs(**changes))
    assert result.total_points == total and result.risk_level == level == level_of(total)
    assert result.total_points == sum(result.components)


def test_mean_grade_rounds_half_up_to_two_places():
    assert mean_grade(['10.99', '11.00']) == Decimal('11.00')  # 10,995 → 11,00
    assert mean_grade([10, 12, 13]) == Decimal('11.67')
    with pytest.raises(InvalidClosingInputs):
        mean_grade([])


@pytest.mark.parametrize('changes', [dict(average_grade=Decimal('20.01')), dict(average_grade=Decimal('-0.01')),
    dict(days_attended=46), dict(days_scheduled=0), dict(activities_delivered=25), dict(participation_level=6),
    dict(participation_level=0), dict(behavior_incidents=-1), dict(days_attended=True)])
def test_invalid_inputs_are_rejected_without_values(changes):
    with pytest.raises(InvalidClosingInputs) as error:
        compute_riesgo_v1(inputs(**changes))
    assert str(error.value).isupper() or '_' in str(error.value)  # código estable, no datos


# ---------- risk_references (DB aislada) ----------

def cut(state, which=0):
    with state.owner.connect() as conn:
        return conn.execute(text('''SELECT sn.id,sn.enrollment_id,sn.period_id,sn.target_date,s.anon_code FROM risk_school.academic_snapshots sn
            JOIN risk_school.enrollments e ON e.id=sn.enrollment_id JOIN risk_school.students s ON s.id=e.student_id
            WHERE sn.period_id=:p AND sn.entry_channel='CSV' AND sn.revision=1 ORDER BY s.anon_code,sn.cutoff_at LIMIT 1 OFFSET :o'''),
            {'p': state.period_id, 'o': which}).one()


def available(target: date):
    return datetime.combine(target + timedelta(days=1), time(12, 0), tzinfo=LIMA)


def with_session(state, work):
    with state.app.state.database.session_factory() as db:
        actor = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
        result = work(db, actor)
        db.commit()
        return result


def test_record_is_computed_by_backend_idempotent_and_revised(demo):
    state = demo
    snapshot = cut(state)
    low = inputs()
    row, created = with_session(state, lambda db, actor: store.record_closing(
        db, actor, snapshot.id, 'B1', snapshot.target_date, available(snapshot.target_date), low, uuid4()))
    assert created and row.revision == 1 and row.supersedes_id is None and row.risk_level == 'LOW' and row.total_points == 0
    first_id = row.id
    assert 'risk_level' not in inspect.signature(store.record_closing).parameters  # el nivel nunca se recibe
    # Mismos insumos: se reutiliza.
    again, created = with_session(state, lambda db, actor: store.record_closing(
        db, actor, snapshot.id, 'B1', snapshot.target_date, available(snapshot.target_date), low, uuid4()))
    assert not created and again.id == first_id
    # Insumos corregidos: otra revisión que reemplaza a la anterior.
    worse = inputs(average_grade=Decimal('10'), days_attended=30, activities_delivered=15)
    second, created = with_session(state, lambda db, actor: store.record_closing(
        db, actor, snapshot.id, 'B1', snapshot.target_date, available(snapshot.target_date), worse, uuid4()))
    assert created and second.revision == 2 and second.supersedes_id == first_id and second.risk_level == 'HIGH'
    assert second.total_points == 5 and second.points_attendance == 2 and second.points_activities == 1

    def reads(db, actor):
        latest = store.latest_by_snapshot(db, snapshot.period_id)
        history = store.references_for_snapshot(db, snapshot.id)
        return latest[snapshot.id].revision, [item.revision for item in history], [item.risk_level for item in history]
    assert with_session(state, reads) == (2, [1, 2], ['LOW', 'HIGH'])
    with state.owner.connect() as conn:
        events = conn.execute(text("SELECT payload FROM risk_school.audit_events WHERE action='RISK_REFERENCE_RECORDED' AND entity_id IN (:a,:b)"),
                              {'a': first_id, 'b': second.id}).all()
        assert len(events) == 2 and all(set(payload) == {'risk_reference_id', 'snapshot_id', 'revision'} for (payload,) in events)


def test_only_admin_and_valid_snapshot(demo):
    state = demo
    snapshot = cut(state)

    def tutor(db, _):
        actor = db.get(AppUser, state.context['accounts']['TUTOR']['id'])
        with pytest.raises(AppError) as error:
            store.record_closing(db, actor, snapshot.id, 'B1', snapshot.target_date, available(snapshot.target_date), inputs(), uuid4())
        assert error.value.status_code == 403

    with_session(state, tutor)

    def missing(db, actor):
        with pytest.raises(AppError) as error:
            store.record_closing(db, actor, uuid4(), 'B1', snapshot.target_date, available(snapshot.target_date), inputs(), uuid4())
        assert error.value.status_code == 404
        with pytest.raises(AppError) as error:
            store.record_closing(db, actor, snapshot.id, 'B1', snapshot.target_date, available(snapshot.target_date),
                                 inputs(behavior_incidents=-1), uuid4())
        assert error.value.code == 'INVALID_CLOSING_INPUTS'
        # Periodo sin protocolo → regla activa RIESGO_V2: la participación no se valida ni se guarda (ADR 013).
        record, _ = store.record_closing(db, actor, snapshot.id, 'B1', snapshot.target_date, available(snapshot.target_date),
                                         inputs(participation_level=9), uuid4())
        assert record.rule_version == 'RIESGO_V2' and record.participation_level is None and record.points_participation is None
        db.rollback()

    with_session(state, missing)


RAW = '''INSERT INTO risk_school.risk_references(enrollment_id,period_id,data_origin,snapshot_id,bimester,rule_version,closing_date,
    closing_available_at,average_grade,days_scheduled,days_attended,activities_scheduled,activities_delivered,participation_level,
    behavior_incidents,points_grade,points_attendance,points_activities,points_participation,points_conduct,total_points,risk_level,
    revision,supersedes_id,computed_by) VALUES(:enrollment_id,:period_id,'SYNTHETIC',:snapshot_id,'B1','RIESGO_V1',:closing_date,
    :available,16,45,45,24,24,5,0,:pg,:pa,:pc,:pp,:pk,:total,:level,:revision,:supersedes,:actor)'''


def raw(state, snapshot, **changes):
    values = dict(enrollment_id=snapshot.enrollment_id, period_id=snapshot.period_id, snapshot_id=snapshot.id,
                  closing_date=snapshot.target_date, available=available(snapshot.target_date), pg=0, pa=0, pc=0, pp=0, pk=0,
                  total=0, level='LOW', revision=1, supersedes=None, actor=state.context['accounts']['ADMIN']['id'])
    values.update(changes)
    return values


def test_check_constraints_and_immutability(demo):
    state = demo
    snapshot = cut(state, 1)
    with state.owner.begin() as conn:  # control: un registro coherente sí entra
        conn.execute(text(RAW), raw(state, snapshot))
    other = cut(state, 2)
    bad = {
        'componente que no sale del insumo': dict(pg=2, total=2, level='MEDIUM'),
        'total que no es la suma': dict(total=1),
        'nivel que no sale del total': dict(level='HIGH'),
        'cierre anterior a la fecha objetivo': dict(closing_date=other.target_date - timedelta(days=1)),
        'disponible antes del cierre': dict(available=datetime.combine(other.target_date - timedelta(days=2), time(12, 0), tzinfo=LIMA)),
        'revisión 2 sin predecesora': dict(revision=2),
    }
    for label, changes in bad.items():
        with state.owner.connect() as conn:
            assert_sqlstate(conn, RAW, raw(state, other, **changes), '23514')
    with state.owner.connect() as conn:
        row = conn.scalar(text('SELECT id FROM risk_school.risk_references WHERE snapshot_id=:s'), {'s': snapshot.id})
        assert_sqlstate(conn, 'UPDATE risk_school.risk_references SET bimester=\'B2\' WHERE id=:id', {'id': row}, '55000')
        assert_sqlstate(conn, 'DELETE FROM risk_school.risk_references WHERE id=:id', {'id': row}, '55000')


def test_revision_chain_and_single_successor(demo):
    state = demo
    snapshot = cut(state, 3)
    sql_low = 'INSERT INTO risk_school.risk_references(enrollment_id,period_id,data_origin,snapshot_id,bimester,rule_version,closing_date,closing_available_at,average_grade,days_scheduled,days_attended,activities_scheduled,activities_delivered,participation_level,behavior_incidents,points_grade,points_attendance,points_activities,points_participation,points_conduct,total_points,risk_level,revision,supersedes_id,computed_by) VALUES(:enrollment_id,:period_id,\'SYNTHETIC\',:snapshot_id,\'B1\',\'RIESGO_V1\',:closing_date,:available,16,45,45,24,24,5,0,0,0,0,0,0,0,\'LOW\',:revision,:supersedes,:actor) RETURNING id'
    ids = []
    with state.owner.begin() as conn:
        first = conn.scalar(text(sql_low), raw(state, snapshot))
        second = conn.scalar(text(sql_low), raw(state, snapshot, revision=2, supersedes=first))
        ids += [first, second]
    with state.owner.connect() as conn:
        assert_sqlstate(conn, sql_low, raw(state, snapshot, revision=3, supersedes=first), '23514')   # no es la inmediata
        assert_sqlstate(conn, sql_low, raw(state, snapshot, revision=2, supersedes=first), '23505')  # segundo sucesor / revisión repetida
    with state.owner.begin() as conn:
        third = conn.scalar(text(sql_low), raw(state, snapshot, revision=3, supersedes=second))
        assert third is not None


def test_load_closings_is_all_or_nothing_and_resolves_by_code_and_target_date(demo):
    state = demo
    first, second = cut(state, 4), cut(state, 5)

    def row(snapshot, line, **changes):
        return store.ClosingRow(line=line, student_code=snapshot.anon_code, bimester='B1', closing_date=snapshot.target_date,
                                closing_available_at=available(snapshot.target_date), inputs=inputs(**changes))
    good = [row(first, 2), row(second, 3, average_grade=Decimal('9'))]
    summary = with_session(state, lambda db, actor: store.load_closings(db, actor, first.period_id, good, uuid4()))
    assert summary == {'created': 2, 'reused': 0, 'rows': 2}
    assert with_session(state, lambda db, actor: store.load_closings(db, actor, first.period_id, good, uuid4())) == {'created': 0, 'reused': 2, 'rows': 2}
    with state.owner.connect() as conn:
        before = conn.scalar(text('SELECT count(*) FROM risk_school.risk_references'))
    unknown = store.ClosingRow(line=4, student_code='NO-EXISTE-001', bimester='B1', closing_date=first.target_date,
                               closing_available_at=available(first.target_date), inputs=inputs())
    changed = [row(first, 2, average_grade=Decimal('8')), unknown]

    def attempt(db, actor):
        with pytest.raises(AppError) as error:
            store.load_closings(db, actor, first.period_id, changed, uuid4())
        return error.value
    error = with_session(state, attempt)
    assert error.code == 'CLOSING_ROWS_REJECTED' and error.details == [{'row': 4, 'code': 'SNAPSHOT_NOT_FOUND'}]
    with state.owner.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM risk_school.risk_references')) == before  # ninguna fila válida se guardó
