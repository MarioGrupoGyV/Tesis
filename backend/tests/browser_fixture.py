"""Solo runner aislado: crea una DB nueva y cuenta efímera; nunca la aplicación activa."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.bootstrap_admin import AdministratorInput, BootstrapError, create_first_admin
from app.configure_context import PeriodInput, UserInput, configure
from app.models.s1 import AppUser, AuditEvent

def main():
    owner = make_url(Path('/run/secrets/owner_url').read_text().strip()).set(host='dbtest', port=5432, database='riesgo_escolar_test')
    app = make_url(Path('/run/secrets/app_url').read_text().strip()).set(host='dbtest', port=5432)
    name = 'riesgo_escolar_test_browser_' + uuid4().hex[:12]
    engine = create_engine(owner, isolation_level='AUTOCOMMIT', hide_parameters=True)
    with engine.connect() as db:
        db.exec_driver_sql(f'CREATE DATABASE {name} OWNER riesgo_owner')
        db.exec_driver_sql(f'REVOKE ALL ON DATABASE {name} FROM PUBLIC')
        db.exec_driver_sql(f'GRANT CONNECT ON DATABASE {name} TO riesgo_app')
    engine.dispose()
    app, owner = app.set(database=name), owner.set(database=name)
    os.environ['MIGRATION_DATABASE_URL'] = owner.render_as_string(hide_password=False)
    subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],check=True,stdout=sys.stderr)
    email, password = 'browser-'+uuid4().hex+'@example.com', secrets.token_urlsafe(24)
    engine = create_engine(app, hide_parameters=True)
    with Session(engine) as db:
        assert db.scalar(text('SELECT current_user')) == 'riesgo_app'
        assert db.scalar(text('SELECT count(*) FROM risk_school.app_users')) == 0
        values = AdministratorInput(email=email, display_name='Prueba aislada de acceso', password=password)
        create_first_admin(db, values)
        try:
            create_first_admin(db, values)
            raise AssertionError('El bootstrap no rechazó repetición')
        except BootstrapError:
            pass
        accounts = {'ADMIN': {'email':email,'password':password}}
        account_ids = {'ADMIN': str(db.scalar(text("SELECT id FROM risk_school.app_users WHERE role='ADMIN'")))}
        admin = db.scalar(text("SELECT id FROM risk_school.app_users WHERE role='ADMIN'"))
        admin = db.get(AppUser, admin)
        for role in ('TUTOR','DIRECTOR','RESEARCHER'):
            account = {'email':f'browser-{role.lower()}-{uuid4().hex}@example.com','password':secrets.token_urlsafe(24)}
            account_ids[role]=str(configure(db,admin,UserInput(**account,display_name=f'Acceso aislado {role}',role=role)))
            accounts[role] = account
        real_period=str(configure(db,admin,PeriodInput(code='BROWSER-REAL-EMPTY',school_year=2026,
            start_date='2026-01-01',end_date='2026-12-31')))
    engine.dispose()
    # El padre captura esta salida en memoria; no se muestra ni se escribe el password.
    print(json.dumps({'database_url':app.render_as_string(hide_password=False),'accounts':accounts,
        'account_ids':account_ids,'database':name,'real_period_id':real_period}))


def browser_action(payload):
    """Hook privado de tests; describe es lectura y revision solo existe en DB aislada.

    Los cortes de la población entran por la importación real. La única revisión
    añadida aquí es evidencia de prueba para comprobar que la interfaz no atribuye
    una evaluación anterior a una corrección todavía pendiente.
    """
    from uuid import UUID
    from app.core.config import Settings
    from app.core.database import Database
    from app.core.security import password_verify
    from app.models.s2 import SnapshotRecord
    settings=Settings()
    database=Database(settings)
    try:
        with database.session_factory() as db:
            assert db.scalar(text('SELECT current_user'))=='riesgo_app'
            dbname=db.scalar(text('SELECT current_database()'))
            actor=db.scalar(select(AppUser).where(AppUser.email==payload['email'],AppUser.role=='ADMIN',AppUser.is_active.is_(True)))
            assert actor and password_verify(payload['password'],actor.password_hash)
            if payload['action']=='identity':
                assert settings.app_env=='test' and dbname.startswith('riesgo_escolar_test_browser_')
                return {'database':dbname,'database_role':'riesgo_app','administrator_verified':True}
            period=UUID(payload['period_id'])
            if payload['action']=='revision':
                assert settings.app_env=='test' and dbname.startswith('riesgo_escolar_test_browser_')
                row=db.execute(text("""SELECT sn.id FROM risk_school.academic_snapshots sn
                    JOIN risk_school.enrollments e ON e.id=sn.enrollment_id
                    JOIN risk_school.grade_sections g ON g.id=e.section_id
                    JOIN risk_school.students st ON st.id=e.student_id
                    JOIN risk_school.predictions p ON p.snapshot_id=sn.id
                    WHERE e.period_id=:period AND g.tutor_id IS NOT NULL AND sn.average_grade IS NOT NULL
                    ORDER BY st.anon_code,sn.cutoff_at DESC LIMIT 1"""),{'period':period}).first()
                assert row is not None
                original=db.get(SnapshotRecord,row.id)
                copy={column.name:getattr(original,column.name) for column in SnapshotRecord.__table__.columns
                    if column.name not in ('id','created_at','revision','supersedes_id','row_sha256')}
                correction=SnapshotRecord(**copy,revision=original.revision+1,supersedes_id=original.id,
                    row_sha256=hashlib.sha256(('s4-browser-test-revision:'+original.row_sha256).encode()).hexdigest())
                db.add(correction); db.flush()
                db.add(AuditEvent(actor_id=actor.id,entity_type='ACADEMIC_SNAPSHOT',entity_id=correction.id,
                    action='BROWSER_FIXTURE_REVISION_ADDED',request_id=uuid4(),payload={'isolated_test_only':True}))
                db.commit()
            elif payload['action']!='describe':
                raise ValueError('Unsupported private fixture action')
            sections=db.execute(text("""SELECT g.id,g.code,g.tutor_id FROM risk_school.grade_sections g
                JOIN risk_school.enrollments e ON e.section_id=g.id
                WHERE e.period_id=:period GROUP BY g.id ORDER BY g.grade,g.id"""),{'period':period}).mappings().all()
            rows=db.execute(text("""SELECT st.id,st.anon_code,e.section_id,sn.id AS snapshot_id,sn.revision,
                sn.average_grade,sn.attendance_pct,p.id AS prediction_id FROM risk_school.students st
                JOIN risk_school.enrollments e ON e.student_id=st.id
                JOIN LATERAL (SELECT * FROM risk_school.academic_snapshots x WHERE x.enrollment_id=e.id
                    ORDER BY cutoff_at DESC,revision DESC LIMIT 1) sn ON true
                LEFT JOIN risk_school.predictions p ON p.snapshot_id=sn.id
                WHERE e.period_id=:period ORDER BY st.anon_code"""),{'period':period}).mappings().all()
            assert sections and rows
            own=next(s for s in sections if s['tutor_id'] is not None)
            foreign=next(s for s in sections if s['tutor_id'] is None)
            def public(row):
                return {'id':str(row['id']),'anon_code':row['anon_code'],
                    'section_id':str(row['section_id']),'snapshot_id':str(row['snapshot_id']),
                    'revision':row['revision']}
            own_row=next(r for r in rows if r['section_id']==own['id'])
            foreign_row=next(r for r in rows if r['section_id']==foreign['id'])
            insufficient=next(r for r in rows if r['average_grade'] is None and r['attendance_pct'] is None)
            pending=next((r for r in rows if r['revision']>1 and r['prediction_id'] is None),None)
            model=db.execute(text("SELECT id,name FROM risk_school.model_versions WHERE is_active AND data_origin='SYNTHETIC'")).mappings().one()
            return {'period_id':str(period),'student_count':len(rows),
                'own_section':{'id':str(own['id']),'code':own['code']},
                'foreign_section':{'id':str(foreign['id']),'code':foreign['code']},
                'own_student':public(own_row),'foreign_student':public(foreign_row),
                'insufficient_student':public(insufficient),'pending_student':public(pending) if pending else None,
                'model':{'id':str(model['id']),'name':model['name']}}
    finally:
        database.engine.dispose()

if __name__ == '__main__':
    main()
