"""Bloque 5 (B): carga de identidades a la ficha. Nombres inventados; la base aislada de pruebas es la única que los ve."""
import logging
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.models.s1 import AppUser
from app.services.identities import load_identities
from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, write, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infra'))
import load_identities as cli  # noqa: E402

NAMES = ['Zzquux Plokijh Uno', 'Qwertyx Mnbvcxz Dos', 'Plokijh Zzquux Tres']


def students(state, count=3):
    period, section = real_setup(state, 'REAL')
    created = [write(state, '/students', dict(creation_key=str(uuid4()), anon_code=f'I{uuid4().hex[:5].upper()}-{i}', full_name='Pendiente',
                                              period_id=period['id'], section_id=section['id'])).json() for i in range(count)]
    return period, created


def rows(created, names=NAMES):
    return [(index + 2, item['anon_code'], name) for index, (item, name) in enumerate(zip(created, names))]


def actor(state, db, role='ADMIN'):
    return db.get(AppUser, state.context['accounts'][role]['id'])


def text_columns_with(state, needle):
    """Tablas y columnas de texto/JSON donde aparece el texto buscado."""
    found = set()
    with state.owner.connect() as conn:
        columns = conn.execute(text("""SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='risk_school'
            AND data_type IN ('text','character varying','jsonb','json')""")).all()
        for table, column in columns:
            count = conn.scalar(text(f'SELECT count(*) FROM risk_school.{table} WHERE "{column}"::text LIKE :n'), {'n': f'%{needle}%'})
            if count:
                found.add(f'{table}.{column}')
    return found


def test_names_reach_only_the_student_record_and_audit_keeps_counts(study_env, caplog):
    state = study_env
    period, created = students(state)
    caplog.set_level(logging.DEBUG)
    with state.app.state.database.session_factory() as db:
        result = load_identities(db, actor(state, db), rows(created))
    assert result == {'rows': 3, 'updated': 3, 'unchanged': 0}
    for item, name in zip(created, NAMES):
        detail = state.client.get(API + f"/students/{item['id']}?period_id={period['id']}").json()
        assert detail['student']['full_name'] == name and detail['student']['version'] == 2          # solo la ficha
    assert text_columns_with(state, 'Zzquux') == {'students.full_name'}
    assert text_columns_with(state, 'Mnbvcxz') == {'students.full_name'}
    with state.owner.connect() as conn:
        payload = conn.scalar(text("SELECT payload::text FROM risk_school.audit_events WHERE action='STUDENT_IDENTITIES_LOADED'"))
    assert '"updated": 3' in payload and '"rows": 3' in payload
    assert not any(word in caplog.text for word in ('Zzquux', 'Qwertyx', 'Plokijh', 'Mnbvcxz'))
    # Idempotente: repetir la carga no cambia nada.
    with state.app.state.database.session_factory() as db:
        assert load_identities(db, actor(state, db), rows(created)) == {'rows': 3, 'updated': 0, 'unchanged': 3}


def test_unknown_duplicate_or_invalid_rows_reject_everything(study_env):
    state = study_env
    _, created = students(state)
    token = 'Kx' + uuid4().hex[:10]                                         # texto único: la base de pruebas conserva nombres de otras pruebas
    bad = rows(created, [f'{token} Uno', f'{token} Dos', f'{token} Tres']) + [(10, 'NOEXISTE-1', f'{token} Desconocido'),
                                                                                (11, created[0]['anon_code'], 'Otro Duplicado')]
    with state.app.state.database.session_factory() as db:
        with pytest.raises(AppError) as error:
            load_identities(db, actor(state, db), bad)
    assert error.value.code == 'IDENTITIES_REJECTED'
    assert {(item['row'], item['code']) for item in error.value.details} == {(10, 'CODE_UNKNOWN'), (11, 'CODE_DUPLICATED')}
    assert token not in str(error.value.details) and text_columns_with(state, token) == set()      # todo o nada


def test_only_admin_and_only_real_students(study_env):
    state = study_env
    prepare(state)
    import_study(state)                                                   # alumnos SYNTHETIC existentes: no admitidos
    with state.owner.connect() as conn:
        synthetic_code = conn.scalar(text("SELECT anon_code FROM risk_school.students WHERE data_origin='SYNTHETIC' LIMIT 1"))
    _, created = students(state, 1)
    with state.app.state.database.session_factory() as db:
        with pytest.raises(AppError) as error:
            load_identities(db, actor(state, db, 'TUTOR'), rows(created))
        assert error.value.code == 'FORBIDDEN'
        with pytest.raises(AppError) as error:
            load_identities(db, actor(state, db), [(2, synthetic_code, 'Zzquux Sintetico')])
        assert error.value.code == 'IDENTITIES_REJECTED' and error.value.details == [{'row': 2, 'code': 'CODE_UNKNOWN'}]


def test_cli_parser_is_strict_and_does_not_echo_values(tmp_path, capsys):
    good = tmp_path / 'identidades.local.csv'
    good.write_text('student_code,full_name\nAAA-1,Zzquux Uno\nAAA-2,Qwertyx Dos\n', encoding='utf-8')
    assert cli.parse_csv(good) == [(2, 'AAA-1', 'Zzquux Uno'), (3, 'AAA-2', 'Qwertyx Dos')]
    for content, code in (('codigo,nombre\nA,B\n', 'IDENTITIES_CSV_HEADERS_INVALID'), ('student_code,full_name\n', 'IDENTITIES_CSV_EMPTY'),
                          ('student_code,full_name\nAAA-1,\n', 'IDENTITIES_CSV_ROW_INVALID:2')):
        (tmp_path / 'x.csv').write_text(content, encoding='utf-8')
        with pytest.raises(cli.IdentitiesCsvError) as error:
            cli.parse_csv(tmp_path / 'x.csv')
        assert str(error.value) == code
    # Sin archivo: instrucciones, no error con valores.
    assert cli.main(['--target', str(tmp_path / 't.json'), '--operator-profile', 'x', '--csv', str(tmp_path / 'no-existe.csv')]) == 2
    output = capsys.readouterr().out
    assert 'IDENTITIES_CSV_UNAVAILABLE' in output and '--identities' in output


def test_real_names_are_hidden_in_list_search_and_identity_lookup_but_not_in_the_record(study_env):
    state = study_env
    token = 'Kx' + uuid4().hex[:10]                                        # texto único: la base de pruebas conserva nombres de otras pruebas
    period, created = students(state)
    with state.app.state.database.session_factory() as db:
        load_identities(db, actor(state, db), rows(created, [f'{token} Uno', f'{token} Dos', f'{token} Tres']))
    listing = state.client.get(API + '/students', params={'period_id': period['id'], 'page_size': 100}).json()
    assert listing['total'] == 3 and all(item['full_name'] is None for item in listing['items'])
    assert state.client.get(API + '/students', params={'period_id': period['id'], 'search': token}).json()['total'] == 0       # no se busca por nombre
    assert state.client.get(API + '/students', params={'period_id': period['id'], 'search': created[0]['anon_code']}).json()['total'] == 1
    assert state.client.get(API + '/student-identities', params={'search': token}).json() == []
    found = state.client.get(API + '/student-identities', params={'search': created[0]['anon_code']}).json()
    assert [item['full_name'] for item in found] == [None] and token not in json_text(found)
    detail = state.client.get(API + f"/students/{created[0]['id']}?period_id={period['id']}").json()
    assert detail['student']['full_name'] == f'{token} Uno'                  # la ficha sí muestra el nombre
    # SYNTHETIC conserva su comportamiento: lista y búsqueda por nombre.
    synthetic_period, synthetic_section = real_setup(state, 'SYNTHETIC')
    named = write(state, '/students', dict(creation_key=str(uuid4()), anon_code='S' + uuid4().hex[:6].upper(), full_name=f'{token} Sintetico',
                                           period_id=synthetic_period['id'], section_id=synthetic_section['id'])).json()
    shown = state.client.get(API + '/students', params={'period_id': synthetic_period['id'], 'search': token}).json()
    assert shown['total'] == 1 and shown['items'][0]['full_name'] == f'{token} Sintetico'
    assert [item['full_name'] for item in state.client.get(API + '/student-identities', params={'search': token}).json()] == [f'{token} Sintetico']


def json_text(value):
    import json
    return json.dumps(value)
