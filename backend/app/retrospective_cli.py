"""Explicit ADMIN registration. JSON stdin avoids secrets in process arguments.

No startup seed, no institutional activation, no execution of ZIP scripts.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import sys
from uuid import uuid4

from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import Database
from app.core.security import password_verify
from app.repositories.s1 import user_by_email
from app.repositories.retrospective import RetrospectiveStore
from app.ml.retrospective import MAX_PACKAGE, PACKAGE_SHA256, RetrospectiveError
from app.ml.retrospective_runtime import invoke
from app.services import retrospective


def main():
    parser = argparse.ArgumentParser(description='Registro ADMIN privado del paquete retrospectivo autorizado')
    parser.add_argument('--stdin', action='store_true', required=True)
    parser.add_argument('--evaluate', action='store_true')
    args = parser.parse_args()
    database = None
    try:
        payload = json.loads(sys.stdin.read(MAX_PACKAGE * 2))
        settings = get_settings()
        database = Database(settings)
        with Session(database.engine) as db:
            user = user_by_email(db, payload['email'].lower())
            if user is None or not user.is_active or not password_verify(payload['password'], user.password_hash):
                raise RetrospectiveError('RETROSPECTIVE_ADMIN_AUTHENTICATION_FAILED')
            retrospective.require_admin(user)
            if payload.get('authorized_local_processing') is not True:
                raise RetrospectiveError('RETROSPECTIVE_AUTHORIZATION_REQUIRED')
            content = base64.b64decode(payload['package_base64'], validate=True)
            invoke('inspect', content)
            audit = payload.get('source_audit')
            if audit is not None and (audit.get('audit_version') != 'source-declarations-v1'
                    or audit.get('input_sha256') != '9cd4243f420b6da5e4ddab629d239334cbe6f2c100642eb6c0ec7ae53243c862'
                    or audit.get('package_sha256') != PACKAGE_SHA256 or audit.get('source_events_verified') is not True
                    or audit.get('authenticity_verified') is not False or audit.get('partial_grades') != 720
                    or audit.get('derived_feature_matches') != 360 or audit.get('reference_matches') != 120):
                raise RetrospectiveError('RETROSPECTIVE_SOURCE_AUDIT_INVALID')
            store = RetrospectiveStore(settings.ml_storage_dir)
            created = store.register(content, {'action': 'RETROSPECTIVE_PACKAGE_REGISTERED', 'actor_id': str(user.id),
                'registered_at': datetime.now(timezone.utc).isoformat(), 'package_sha256': PACKAGE_SHA256,
                'authorized_local_processing': True, 'authorization_basis': 'USER_EXPLICIT_LOCAL_PROCESSING_2026_10_11',
                'provenance_verified': False, 'institutional_activation': False, 'source_audit': audit})
            result = {'registered': True, 'created': created}
            if args.evaluate:
                detail = retrospective.run(user, settings, uuid4())
                result.update(id=str(detail.id), executed_at=detail.executed_at.isoformat(), metrics=detail.metrics.model_dump(),
                              prediction_mismatches=detail.prediction_mismatches, compatibility=detail.compatibility)
            print(json.dumps(result))
    except Exception as error:
        from app.core.errors import AppError
        code = str(error) if isinstance(error, RetrospectiveError) else error.code if isinstance(error, AppError) else 'RETROSPECTIVE_REGISTRATION_FAILED'
        print(json.dumps({'error': code}), file=sys.stderr)
        sys.exit(1)
    finally:
        if database:
            database.engine.dispose()


if __name__ == '__main__':
    main()
