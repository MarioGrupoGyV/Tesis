from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.bootstrap_admin import BootstrapError
from app.configure_context import configure, PeriodInput, SectionInput
from app.models.s1 import AppUser

def test_explicit_context_and_duplicate_rollback(db, context):
    with Session(bind=db, join_transaction_mode='create_savepoint') as session:
        admin = session.get(AppUser, context['accounts']['ADMIN']['id'])
        values = PeriodInput(code='fixture-'+uuid4().hex[:12], school_year=2030, start_date='2030-03-01', end_date='2030-12-20')
        period_id = configure(session, admin, values)
        before = db.scalar(text('SELECT count(*) FROM risk_school.audit_events'))
        with pytest.raises(IntegrityError):
            configure(session, admin, values)
        assert db.scalar(text('SELECT count(*) FROM risk_school.audit_events')) == before
        section_id = configure(session, admin, SectionInput(code='fixture',grade=1,school_year=2030,tutor_id=None))
        assert period_id and section_id

def test_configuration_requires_admin_and_valid_tutor(db, context):
    with Session(bind=db, join_transaction_mode='create_savepoint') as session:
        tutor = session.get(AppUser, context['accounts']['TUTOR']['id'])
        values = SectionInput(code='fixture',grade=1,school_year=2026,tutor_id=uuid4())
        with pytest.raises(BootstrapError):
            configure(session,tutor,values)
        admin = session.get(AppUser, context['accounts']['ADMIN']['id'])
        with pytest.raises(BootstrapError):
            configure(session,admin,values)
