"""Bloque 3B-3 (C): auditoría y efectos del protocolo REAL, y búsqueda automática de nombres. Datos ficticios; solo códigos."""
import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
import re
from uuid import uuid4

from sqlalchemy import text

from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, write, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)
from test_b1_manual_evaluation import demo  # noqa: F401
from test_b3_protocol import body, call, BLOCKED

NAME_LIKE = re.compile(r'^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+( (de|del|la|los|y))?( [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+$')
NAME_HEADERS = re.compile(r'nombre|apellido|name|alumno|estudiante_nombre', re.I)
SENTINELS = ('Zzxqwv', 'Apellidoz', 'Alumno de Prueba', 'Álvaro de Prueba')


def name_findings(csv_text):
    """Cabeceras o celdas con aspecto de nombre propio (varias palabras capitalizadas). Los códigos nunca coinciden."""
    reader = csv.reader(io.StringIO(csv_text.lstrip('﻿')))
    header = next(reader, [])
    found = [f'cabecera:{item}' for item in header if NAME_HEADERS.search(item)]
    for line in reader:
        found += [f'celda:{cell}' for cell in line if NAME_LIKE.match(cell.strip())]
    return found


def test_name_heuristic_flags_names_and_accepts_codes():
    assert name_findings('codigo_anonimo,seccion\nE57D7-029,E2E-A\n') == []
    assert name_findings('nombre,seccion\nE57D7-029,E2E-A\n') == ['cabecera:nombre']
    assert name_findings('codigo\nMaría Pérez Quispe\n') == ['celda:María Pérez Quispe']


def student(state, period, section):
    return write(state, '/students', dict(creation_key=str(uuid4()), anon_code='B5P-' + uuid4().hex[:10], full_name='Zzxqwv Prueba Apellidoz',
                                           period_id=period['id'], section_id=section['id'])).json()


def flags(state, student_id):
    with state.owner.connect() as conn:
        return tuple(conn.execute(text('SELECT eligible_for_processing,consent_documented,assent_documented FROM risk_school.students WHERE id=:s'),
                                  {'s': student_id}).one())


def test_protocol_audit_eligibility_and_blocking_on_confirm_revoke_confirm(demo):
    state = demo
    period, section = real_setup(state, 'REAL')
    first = student(state, period, section)
    protocol = call(state, 'post', '/processing-protocols', body(period['id'])).json()
    assert flags(state, first['id']) == (False, False, False)

    with state.owner.connect() as conn:                                            # el protocolo no tiene campos de autorización
        columns = {row[0] for row in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='processing_protocols'"))}
    assert not [name for name in columns if re.search(r'consent|assent|document|authorizer|permit|permiso', name)]
    assert {'authorization_confirmed_by_admin', 'confirmed_by', 'confirmed_at'} <= columns

    before = datetime.now(UTC)
    assert call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm").status_code == 200
    second = student(state, period, section)                                       # alumno creado con el protocolo ya confirmado
    assert flags(state, first['id']) == (True, False, False) and flags(state, second['id']) == (True, False, False)
    with state.owner.connect() as conn:
        audit = conn.execute(text("""SELECT action,actor_id,recorded_at,payload FROM risk_school.audit_events
            WHERE entity_type='PROCESSING_PROTOCOL' AND entity_id=:id ORDER BY recorded_at,id"""), {'id': protocol['id']}).all()
    confirmed = audit[-1]
    assert confirmed.action == 'PROTOCOL_AUTHORIZATION_CONFIRMED' and str(confirmed.actor_id) == str(state.context['accounts']['ADMIN']['id'])
    assert confirmed.recorded_at.utcoffset().total_seconds() == 0 and before <= confirmed.recorded_at <= datetime.now(UTC)
    assert set(confirmed.payload) == {'protocol_id', 'period_id'}                    # solo identificadores: ni documento ni autorizador

    with state.owner.connect() as conn:                                            # datos que no deben perderse al revocar
        counts_before = {name: conn.scalar(text(f'SELECT count(*) FROM risk_school.{name}')) for name in ('students', 'enrollments', 'audit_events')}
    assert call(state, 'post', f"/processing-protocols/{protocol['id']}/revoke").status_code == 200
    assert flags(state, first['id']) == (False, False, False) and flags(state, second['id']) == (False, False, False)
    assert call(state, 'get', f"/alerts?period_id={period['id']}").json()['code'] == BLOCKED
    assert call(state, 'get', f"/indicators?period_id={period['id']}").json()['code'] == BLOCKED
    assert call(state, 'post', '/alerts/sync', {'period_id': period['id']}).json()['code'] == BLOCKED
    with state.owner.connect() as conn:
        counts_after = {name: conn.scalar(text(f'SELECT count(*) FROM risk_school.{name}')) for name in ('students', 'enrollments')}
        revoked = conn.execute(text("""SELECT action,payload FROM risk_school.audit_events WHERE entity_type='PROCESSING_PROTOCOL'
            AND entity_id=:id ORDER BY recorded_at DESC,id DESC LIMIT 1"""), {'id': protocol['id']}).one()
    assert counts_after == {name: counts_before[name] for name in counts_after}       # nada se borró
    assert revoked.action == 'PROTOCOL_AUTHORIZATION_REVOKED' and set(revoked.payload) == {'protocol_id', 'period_id'}

    assert call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm").status_code == 200
    assert flags(state, first['id']) == (True, False, False) and flags(state, second['id']) == (True, False, False)
    assert call(state, 'get', f"/alerts?period_id={period['id']}").json().get('code') != BLOCKED   # vuelve a estar habilitado


def test_evidence_files_contain_no_names():
    """Todo `mejoras-03b3-*` de texto (CSV, JSON, XML) está libre de nombres; los CSV además de cabeceras o celdas con aspecto de nombre."""
    root = Path(__file__).resolve().parents[2] / 'tests' / 'evidence'
    for path in sorted(root.glob('mejoras-03b3-*')) if root.exists() else []:
        if path.suffix.lower() not in ('.csv', '.json', '.xml'):
            continue
        content = path.read_text(encoding='utf-8')
        assert not any(sentinel in content for sentinel in SENTINELS), path.name
        if path.suffix.lower() == '.csv':
            assert name_findings(content) == [], path.name
        if path.suffix.lower() == '.json':
            json.loads(content)
