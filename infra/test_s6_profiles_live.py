"""Perfiles: autenticación HTTP real en INSTALL; secretos solo en memoria."""
import hashlib
from pathlib import Path
from uuid import uuid4

from operator_profiles import admin_account, register_profile, verify_admin
from study import internal
import windows_credentials as store


_ACTIVE_STATE = '''import json,sys
from sqlalchemy import select
from app.core.config import Settings
from app.core.database import Database
from app.models.s1 import AppUser
p=json.load(sys.stdin);d=Database(Settings())
with d.session_factory() as c:
 u=c.scalar(select(AppUser).where(AppUser.email==p['email'],AppUser.role=='ADMIN'))
 if u is None: raise RuntimeError('ISOLATED_ADMIN_MISSING')
 previous=u.is_active
 u.is_active=p['is_active'];c.commit()
 print(json.dumps({'previous_is_active':previous,'is_active':u.is_active}))
'''


def check_live(target, accounts):
    """Cuatro intentos HTTP; cuatro usuarios originales y S2.2 quedan conservados."""
    if target.kind != 'INSTALL':
        raise RuntimeError('PROFILE_TEST_REQUIRES_INSTALL_TARGET')
    target.assert_identity()
    administrator = accounts['ADMIN']
    if not 12 <= len(administrator['password']) <= 19:
        raise RuntimeError('PROFILE_TEST_REQUIRES_OWN_ADMIN_PASSWORD_POLICY')
    before = {role: store.read(role) for role in store.ROLES}
    names = {case: 's6-live-' + uuid4().hex for case in ('valid', 'invalid', 'non_admin', 'inactive')}
    cases = []
    original_active = None
    try:
        result = register_profile(target, names['valid'], administrator['email'], administrator['password'])
        loaded = admin_account(target, operator_profile=names['valid'])
        if loaded != administrator:
            raise RuntimeError('PROFILE_LIVE_PRIVATE_ROUNDTRIP_FAILED')
        readiness = internal('status', loaded, target=target)
        if readiness.get('institutional_ready') is not False:
            raise RuntimeError('PROFILE_LIVE_INSTITUTIONAL_BLOCK_MISSING')
        cases.append({'case': 'own_admin_valid_12_to_19', 'status': 'COMPROBADO',
            'authentication': 'HTTP_LOGIN_ME_LOGOUT', 'private_command': 'study_status',
            'users_created_by_profile': result['users_created'], 'password_exported': False})
        for case, values in (('invalid', {**administrator, 'password': 'invalid-' + uuid4().hex}),
                             ('non_admin', accounts['TUTOR'])):
            try:
                register_profile(target, names[case], values['email'], values['password'])
            except RuntimeError as error:
                if str(error) != 'OPERATOR_ADMIN_AUTHENTICATION_REQUIRED':
                    raise
            else:
                raise RuntimeError('PROFILE_LIVE_INVALID_ACCESS_ACCEPTED')
            if store.read_operator_profile(names[case]) is not None:
                raise RuntimeError('PROFILE_LIVE_INVALID_ACCESS_STORED')
            cases.append({'case': case, 'status': 'COMPROBADO', 'authentication': 'REAL_HTTP_REJECTED',
                'credential_stored': False})
        change = target.api_python(_ACTIVE_STATE, {'email': administrator['email'], 'is_active': False})
        original_active = change['previous_is_active']
        if original_active is not True:
            raise RuntimeError('PROFILE_LIVE_INITIAL_ADMIN_INACTIVE')
        try:
            register_profile(target, names['inactive'], administrator['email'], administrator['password'])
        except RuntimeError as error:
            if str(error) != 'OPERATOR_ADMIN_AUTHENTICATION_REQUIRED':
                raise
        else:
            raise RuntimeError('PROFILE_LIVE_INACTIVE_ACCESS_ACCEPTED')
        if store.read_operator_profile(names['inactive']) is not None:
            raise RuntimeError('PROFILE_LIVE_INACTIVE_ACCESS_STORED')
        cases.append({'case': 'inactive', 'status': 'COMPROBADO', 'authentication': 'REAL_HTTP_REJECTED',
            'credential_stored': False, 'scope': 'TEMPORARY_INSTALL_ADMIN_FLAG_ONLY'})
    finally:
        if original_active is not None:
            target.api_python(_ACTIVE_STATE, {'email': administrator['email'], 'is_active': original_active})
        for name in names.values():
            if name in store._created_operator_profiles:
                store.delete_operator_profile_created_here(name)
    if any(store.read_operator_profile(name) is not None for name in names.values()):
        raise RuntimeError('PROFILE_LIVE_TEMPORARY_ENTRY_NOT_CLEANED')
    if {role: store.read(role) for role in store.ROLES} != before:
        raise RuntimeError('PROFILE_LIVE_S22_CREDENTIAL_CHANGED')
    source = Path(__file__)
    return {'status': 'COMPROBADO', 'target': {'kind': target.kind, 'project': target.project,
        'database': target.database, 'web_url': target.web_url}, 'http_login_attempts': 4,
        'cases': cases, 'temporary_profiles_cleaned': True, 's22_entries_unchanged': True,
        'admin_active_restored': True, 'secret_files_created': False,
        'executed_code_sha256': {source.name: hashlib.sha256(source.read_bytes()).hexdigest()}}


def check_legacy_live(target):
    """S2.2: leer solo ADMIN y comprobar acceso en RESTORE; no cambia sus entradas."""
    if target.kind != 'RESTORE':
        raise RuntimeError('LEGACY_PROFILE_TEST_REQUIRES_RESTORE_TARGET')
    before = {role: store.read(role) for role in store.ROLES}
    account = admin_account(target, admin_credential='ADMIN')
    verify_admin(target, account)
    result = internal('status', account, target=target)
    if result.get('institutional_ready') is not False:
        raise RuntimeError('LEGACY_PROFILE_INSTITUTIONAL_BLOCK_MISSING')
    if {role: store.read(role) for role in store.ROLES} != before:
        raise RuntimeError('LEGACY_PROFILE_S22_CREDENTIAL_CHANGED')
    return {'status': 'COMPROBADO', 'target': {'kind': target.kind, 'project': target.project,
        'database': target.database, 'web_url': target.web_url}, 'http_login_attempts': 1,
        'authentication': 'HTTP_LOGIN_ME_LOGOUT', 'credential_selection': 'ADMIN_ONLY',
        's22_entries_unchanged': True, 'institutional_ready': False}
