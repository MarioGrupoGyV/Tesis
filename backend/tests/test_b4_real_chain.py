"""Bloque 3B-2 (migración 0008): no mezcla REAL/SYNTHETIC a nivel de triggers, CHECK y FK.

Todo con datos ficticios construidos aquí, directamente en SQL sobre una base aislada migrada hasta 0008.
"""
import json
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from conftest import create_context
from test_b3_migration import new_database
from test_s1_schema import assert_sqlstate

PERIOD = ('2026-01-01', '2026-12-31')


class World:
    pass


def run(conn, sql, **params):
    return conn.execute(text(sql), params)


def study(conn, w, period, origin, kind, protocol=None, label='a'):
    sid = uuid4()
    run(conn, """INSERT INTO risk_school.synthetic_studies(id,period_id,data_origin,generator_version,seed,config,manifest,csv_sha256,
        storage_key,payload_sha256,created_by,kind,protocol_id) VALUES(:id,:p,:o,:g,1,'{}','{}',repeat(:l,64),replace(CAST(:id AS text),'-','')||'.json',
        repeat('b',64),:u,:k,:pr)""", id=sid, p=period, o=origin, l=label, u=w.admin, k=kind, pr=protocol,
        g='synthetic-generator-v1' if kind == 'SYNTHETIC_STUDY' else 'institutional-loader-v1')
    return sid, label * 64


def batch(conn, w, period, origin, study_id, csv_hash):
    bid = uuid4()
    run(conn, """INSERT INTO risk_school.import_batches(id,period_id,data_origin,created_by,file_name,file_sha256,storage_key,status,total_rows,
        valid_rows,invalid_rows,committed_at,study_id) VALUES(:id,:p,:o,:u,'f.csv',:h,CAST(:id AS text)||'.csv','COMMITTED',1,1,0,now(),:s)""",
        id=bid, p=period, o=origin, u=w.admin, h=csv_hash, s=study_id)
    return bid


def student_chain(conn, w, period, section, origin, batch_id, *, eligible=False, consent=False):
    sid, eid, snap = uuid4(), uuid4(), uuid4()
    run(conn, """INSERT INTO risk_school.students(id,anon_code,data_origin,eligible_for_processing,consent_documented,assent_documented)
        VALUES(:id,:c,:o,false,:k,:k)""", id=sid, c=origin[:1] + '-' + uuid4().hex[:12], o=origin, k=consent)
    run(conn, "INSERT INTO risk_school.enrollments(id,student_id,period_id,section_id,data_origin) VALUES(:id,:s,:p,:g,:o)",
        id=eid, s=sid, p=period, g=section, o=origin)
    run(conn, """INSERT INTO risk_school.academic_snapshots(id,enrollment_id,period_id,data_origin,import_batch_id,window_start,cutoff_at,available_at,
        target_date,average_grade,missing_fraction,source_row_number,row_sha256) VALUES(:id,:e,:p,:o,:b,'2026-03-09','2026-04-21T17:00:00Z',
        '2026-04-21T16:00:00Z','2026-05-08',10,0,2,repeat('c',64))""", id=snap, e=eid, p=period, o=origin, b=batch_id)
    return sid, eid, snap


def model(conn, w, origin, study_id, *, scope=None, approval=None, status='APPROVED', active=False):
    mid = uuid4()
    manifest = {'study_id': str(study_id) if study_id else None, 'data_origin': origin,
                'scope': scope or ('SYNTHETIC_STUDY' if origin == 'SYNTHETIC' else 'INSTITUTIONAL_STUDY'),
                'approval_kind': approval or ('TECHNICAL_SIMULATION' if origin == 'SYNTHETIC' else 'LOCAL_EXPLORATORY')}
    run(conn, """INSERT INTO risk_school.model_versions(id,name,version,algorithm,data_origin,dataset_hash,artifact_sha256,artifact_key,
        feature_schema_version,reference_criterion_version,status,is_active,parameters,metrics,manifest,study_id) VALUES(:id,:n,'1','DUMMY',:o,
        repeat('c',64),repeat('d',64),'k','ml-features-v1','v',:st,:a,'{}','{}',CAST(:m AS jsonb),:s)""",
        id=mid, n='m-' + mid.hex[:10], o=origin, st=status, a=active, m=json.dumps(manifest), s=study_id)
    return mid


def prediction(conn, enrollment, snapshot, model_id, origin):
    return run(conn, """INSERT INTO risk_school.predictions(id,enrollment_id,snapshot_id,model_id,data_origin,risk_level)
        VALUES(gen_random_uuid(),:e,:s,:m,:o,'HIGH') RETURNING id""", e=enrollment, s=snapshot, m=model_id, o=origin).scalar()


def protocol(conn, w, period, confirmed=False):
    pid = uuid4()
    run(conn, """INSERT INTO risk_school.processing_protocols(id,period_id,school_label,cohort_label,grade_scale_min,grade_scale_max,
        participation_min,participation_max,bimesters,source_label,eligibility_rules,risk_rule,opportune_windows,created_by)
        VALUES(:id,:p,'Colegio de prueba','Cohorte de prueba',0,20,1,5,CAST(:b AS jsonb),'Fuente de prueba',CAST(:e AS jsonb),
        CAST(:r AS jsonb),CAST(:o AS jsonb),:u)""", id=pid, p=period, u=w.admin, b=json.dumps([{'code': 'B1'}]),
        e=json.dumps({'inference_max_missing_fraction': 0.4, 'required_features': ['average_grade']}),
        r=json.dumps({'version': 'RIESGO_V1'}), o=json.dumps({'detection_days': 0, 'intervention_days': 14}))
    if confirmed:
        set_confirmed(conn, w, pid, True)
    return pid


def set_confirmed(conn, w, protocol_id, value):
    run(conn, """UPDATE risk_school.processing_protocols SET authorization_confirmed_by_admin=:v,confirmed_by=CASE WHEN :v THEN CAST(:u AS uuid) END,
        confirmed_at=CASE WHEN :v THEN now() END,version=version+1 WHERE id=:id
        AND authorization_confirmed_by_admin IS DISTINCT FROM :v""", v=value, u=w.admin, id=protocol_id)


@pytest.fixture(scope='module')
def world(database_urls, synthetic_password, synthetic_password_hash):
    name, migrate = new_database(database_urls, 'b4_chain')
    migrate('head')
    engine = create_engine(make_url(database_urls[1]).set(database=name), hide_parameters=True)
    w = World()
    w.engine = engine
    with engine.begin() as conn:
        context = create_context(conn, synthetic_password, synthetic_password_hash)
        w.admin = context['accounts']['ADMIN']['id']
        w.real_period = context['periods']['real']['id']          # REAL 2026
        w.other_real_period = context['periods']['demo']['id']    # REAL 2026 (otro estudio)
        w.real_section = context['sections'][0]['id']
        run(conn, "UPDATE risk_school.grade_sections SET data_origin='REAL' WHERE id=:id", id=w.real_section)
        w.synthetic_period = uuid4()
        run(conn, "INSERT INTO risk_school.academic_periods(id,code,school_year,start_date,end_date,data_origin) VALUES(:id,:c,2026,:a,:b,'SYNTHETIC')",
            id=w.synthetic_period, c='B4-SYN-' + uuid4().hex[:8], a=PERIOD[0], b=PERIOD[1])
        w.synthetic_section = context['sections'][1]['id']
        w.protocol = protocol(conn, w, w.real_period)
        w.other_protocol = protocol(conn, w, w.other_real_period)
        w.real_study, hash_real = study(conn, w, w.real_period, 'REAL', 'INSTITUTIONAL_STUDY', w.protocol, 'a')
        w.other_study, hash_other = study(conn, w, w.other_real_period, 'REAL', 'INSTITUTIONAL_STUDY', w.other_protocol, 'e')
        w.syn_study, hash_syn = study(conn, w, w.synthetic_period, 'SYNTHETIC', 'SYNTHETIC_STUDY', None, 'f')
        w.real_batch = batch(conn, w, w.real_period, 'REAL', w.real_study, hash_real)
        w.other_batch = batch(conn, w, w.other_real_period, 'REAL', w.other_study, hash_other)
        w.syn_batch = batch(conn, w, w.synthetic_period, 'SYNTHETIC', w.syn_study, hash_syn)
        w.real_student, w.real_enrollment, w.real_snapshot = student_chain(conn, w, w.real_period, w.real_section, 'REAL', w.real_batch)
        w.syn_student, w.syn_enrollment, w.syn_snapshot = student_chain(conn, w, w.synthetic_period, w.synthetic_section, 'SYNTHETIC', w.syn_batch)
        w.real_model = model(conn, w, 'REAL', w.real_study)
        w.other_real_model = model(conn, w, 'REAL', w.other_study)
        w.syn_model = model(conn, w, 'SYNTHETIC', w.syn_study)
    yield w
    engine.dispose()


def blocked(w, sql, state, **params):
    """Rechazo con el SQLSTATE indicado; una tupla admite varios (un trigger BEFORE puede actuar antes que la FK)."""
    states = (state,) if isinstance(state, str) else state
    with w.engine.connect() as conn:
        with pytest.raises(Exception) as caught:
            conn.execute(text(sql), params)
        assert caught.value.orig.sqlstate in states, caught.value.orig.sqlstate


INSERT_PREDICTION = """INSERT INTO risk_school.predictions(id,enrollment_id,snapshot_id,model_id,data_origin,risk_level)
    VALUES(gen_random_uuid(),:e,:s,:m,:o,'HIGH')"""


def test_real_prediction_requires_confirmed_protocol_same_study_and_period(world):
    w = world
    with w.engine.begin() as conn:
        set_confirmed(conn, w, w.protocol, False)
    blocked(w, INSERT_PREDICTION, '23514', e=w.real_enrollment, s=w.real_snapshot, m=w.real_model, o='REAL')   # sin protocolo confirmado
    with w.engine.begin() as conn:
        set_confirmed(conn, w, w.protocol, True)
        assert prediction(conn, w.real_enrollment, w.real_snapshot, w.real_model, 'REAL')                      # con protocolo: sí
    blocked(w, INSERT_PREDICTION, '23514', e=w.real_enrollment, s=w.real_snapshot, m=w.other_real_model, o='REAL')  # modelo de otro estudio REAL


def test_cross_origin_models_are_rejected_in_both_directions(world):
    w = world
    with w.engine.begin() as conn:
        set_confirmed(conn, w, w.protocol, True)
    blocked(w, INSERT_PREDICTION, ('23503', '23514'), e=w.real_enrollment, s=w.real_snapshot, m=w.syn_model, o='REAL')            # REAL con modelo SYNTHETIC
    blocked(w, INSERT_PREDICTION, ('23503', '23514'), e=w.syn_enrollment, s=w.syn_snapshot, m=w.real_model, o='SYNTHETIC')        # SYNTHETIC con modelo REAL
    with w.engine.begin() as conn:                                                                                     # lo propio de cada origen sigue funcionando
        assert prediction(conn, w.syn_enrollment, w.syn_snapshot, w.syn_model, 'SYNTHETIC')


def test_isolated_real_evidence_without_study_is_still_allowed_but_cannot_be_activated(world):
    w = world
    with w.engine.begin() as conn:
        isolated_batch = batch(conn, w, w.other_real_period, 'REAL', None, 'd' * 64)
        _, enrollment, snapshot = student_chain(conn, w, w.other_real_period, w.real_section, 'REAL', isolated_batch)
        isolated_model = model(conn, w, 'REAL', None, scope='ISOLATED_TEST', approval='NONE', status='DRAFT')
        assert prediction(conn, enrollment, snapshot, isolated_model, 'REAL')                                           # compatibilidad histórica
    blocked(w, "UPDATE risk_school.model_versions SET is_active=true,status='APPROVED' WHERE id=:id", '23514', id=isolated_model)


def test_active_model_rule_by_scope_one_per_origin(world):
    w = world
    activate = "UPDATE risk_school.model_versions SET is_active=true WHERE id=:id"
    with w.engine.begin() as conn:
        wrong_scope = model(conn, w, 'REAL', w.real_study, scope='SYNTHETIC_STUDY')
        wrong_approval = model(conn, w, 'REAL', w.real_study, approval='TECHNICAL_SIMULATION')
        synthetic_with_institutional = model(conn, w, 'SYNTHETIC', w.syn_study, scope='INSTITUTIONAL_STUDY')
        synthetic_wrong_approval = model(conn, w, 'SYNTHETIC', w.syn_study, approval='LOCAL_EXPLORATORY')
    for identifier in (wrong_scope, wrong_approval, synthetic_with_institutional, synthetic_wrong_approval):
        blocked(w, activate, '23514', id=identifier)
    with w.engine.begin() as conn:
        run(conn, activate, id=w.real_model)         # REAL: INSTITUTIONAL_STUDY + LOCAL_EXPLORATORY
        run(conn, activate, id=w.syn_model)          # SYNTHETIC: un activo propio, simultáneo al de REAL
    blocked(w, activate, '23505', id=w.other_real_model)                                                                # un solo activo por origen
    with w.engine.begin() as conn:
        run(conn, "UPDATE risk_school.model_versions SET is_active=false WHERE id IN (:a,:b)", a=w.real_model, b=w.syn_model)


def test_study_and_provenance_checks(world):
    w = world
    insert = """INSERT INTO risk_school.synthetic_studies(id,period_id,data_origin,generator_version,seed,config,manifest,csv_sha256,storage_key,
        payload_sha256,created_by,kind,protocol_id) VALUES(:id,:p,:o,:g,1,'{}','{}',repeat('a',64),replace(CAST(:id AS text),'-','')||'.json',repeat('b',64),:u,:k,:pr)"""
    base = dict(u=w.admin)
    other = uuid4()
    blocked(w, insert, '23514', id=other, p=w.real_period, o='REAL', g='institutional-loader-v1', k='INSTITUTIONAL_STUDY', pr=None, **base)  # sin protocolo
    blocked(w, insert, '23514', id=other, p=w.real_period, o='REAL', g='synthetic-generator-v1', k='INSTITUTIONAL_STUDY', pr=w.protocol, **base)  # generador de otro tipo
    blocked(w, insert, '23514', id=other, p=w.real_period, o='SYNTHETIC', g='institutional-loader-v1', k='INSTITUTIONAL_STUDY', pr=w.protocol, **base)  # tipo REAL con origen SYNTHETIC
    blocked(w, "INSERT INTO risk_school.import_batches(id,period_id,data_origin,created_by,file_name,file_sha256,storage_key) VALUES(gen_random_uuid(),:p,'SYNTHETIC',:u,'f',repeat('a',64),'k')",
            '23514', p=w.synthetic_period, u=w.admin)                                                                    # lote SYNTHETIC sin estudio
    blocked(w, """INSERT INTO risk_school.model_versions(id,name,version,algorithm,data_origin,dataset_hash,artifact_sha256,artifact_key,feature_schema_version,
        reference_criterion_version,status,parameters,metrics,manifest) VALUES(gen_random_uuid(),'x','1','DUMMY','SYNTHETIC',repeat('c',64),repeat('d',64),'k','a','b','DRAFT','{}','{}','{}')""",
            '23514')                                                                                                     # modelo SYNTHETIC sin estudio
    blocked(w, "UPDATE risk_school.import_batches SET study_id=:s WHERE id=:b", '23503', s=w.syn_study, b=w.real_batch)   # estudio de otro origen (FK compuesta)


def test_followup_requires_confirmed_protocol_and_real_section(world):
    w = world
    with w.engine.begin() as conn:
        set_confirmed(conn, w, w.protocol, True)
        _, enrollment, snapshot = student_chain(conn, w, w.real_period, w.real_section, 'REAL', w.real_batch)
        model_id = model(conn, w, 'REAL', w.real_study)
        predicted = prediction(conn, enrollment, snapshot, model_id, 'REAL')
        run(conn, "INSERT INTO risk_school.alerts(id,enrollment_id,prediction_id,data_origin,severity) VALUES(gen_random_uuid(),:e,:p,'REAL','HIGH')",
            e=enrollment, p=predicted)                                                                                   # con protocolo y sección REAL: sí
        _, enrollment2, snapshot2 = student_chain(conn, w, w.real_period, w.real_section, 'REAL', w.real_batch)
        predicted2 = prediction(conn, enrollment2, snapshot2, model_id, 'REAL')
    with w.engine.begin() as conn:
        set_confirmed(conn, w, w.protocol, False)                                                                        # revocado: se bloquea de nuevo
    alert = "INSERT INTO risk_school.alerts(id,enrollment_id,prediction_id,data_origin,severity) VALUES(gen_random_uuid(),:e,:p,'REAL','HIGH')"
    blocked(w, alert, '23514', e=enrollment2, p=predicted2)
    with w.engine.begin() as conn:
        set_confirmed(conn, w, w.protocol, True)
        run(conn, "UPDATE risk_school.grade_sections SET data_origin=NULL WHERE id=:id", id=w.real_section)
    blocked(w, alert, '23514', e=enrollment2, p=predicted2)                                                              # sección que no es REAL
    with w.engine.begin() as conn:
        run(conn, "UPDATE risk_school.grade_sections SET data_origin='REAL' WHERE id=:id", id=w.real_section)
        set_confirmed(conn, w, w.protocol, False)


def test_real_student_eligibility_by_protocol_with_legacy_consent_route(world):
    w = world
    mark = "UPDATE risk_school.students SET eligible_for_processing=true WHERE id=:id"
    insert = """INSERT INTO risk_school.students(id,anon_code,data_origin,eligible_for_processing,consent_documented,assent_documented)
        VALUES(gen_random_uuid(),:c,'REAL',true,:k,:k)"""
    with w.engine.begin() as conn:
        set_confirmed(conn, w, w.protocol, False)
        student, _, _ = student_chain(conn, w, w.real_period, w.real_section, 'REAL', w.real_batch)
    blocked(w, mark, '23514', id=student)                                                                                # sin protocolo no se marca elegible
    blocked(w, insert, '23514', c='R-' + uuid4().hex[:10], k=False)                                                      # ni al insertar
    with w.engine.begin() as conn:
        run(conn, insert, c='R-' + uuid4().hex[:10], k=True)                                                              # ruta histórica aislada (consent+assent)
        set_confirmed(conn, w, w.protocol, True)
        run(conn, mark, id=student)                                                                                      # con protocolo que cubre su matrícula: sí
        set_confirmed(conn, w, w.protocol, False)
        run(conn, "UPDATE risk_school.students SET is_active=true,version=version+1 WHERE id=:id", id=student)            # editar después de revocar no se bloquea
        other, _, _ = student_chain(conn, w, w.other_real_period, w.real_section, 'REAL', w.other_batch)
    blocked(w, mark, '23514', id=other)                                                                                  # su periodo no está cubierto
    with w.engine.connect() as conn:
        assert conn.scalar(text('SELECT eligible_for_processing FROM risk_school.students WHERE id=:id'), {'id': student}) is True
        assert conn.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='students_eligibility_check'")) == 0
        assert conn.scalar(text("SELECT count(*) FROM pg_trigger WHERE tgfoid='risk_school.check_real_student_eligibility()'::regprocedure")) == 2


def test_synthetic_behaviour_is_unchanged(world):
    w = world
    with w.engine.begin() as conn:  # SYNTHETIC sigue elegible sin protocolo y sin consentimientos
        run(conn, "UPDATE risk_school.students SET eligible_for_processing=true WHERE id=:id", id=w.syn_student)
        run(conn, "INSERT INTO risk_school.students(id,anon_code,data_origin,eligible_for_processing) VALUES(gen_random_uuid(),:c,'SYNTHETIC',true)",
            c='S-' + uuid4().hex[:10])
