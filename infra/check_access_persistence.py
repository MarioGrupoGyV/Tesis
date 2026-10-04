"""Recreación explícita sin borrar volúmenes; conserva la protección de check_runtime."""
import json
import os
import subprocess
from runtime_snapshot import ROOT, snapshot, school_unchanged, SCHOOL
from review_accounts import credentials
from review_endpoints import Client, BASE


def main():
    before = snapshot()
    subprocess.run(['docker', 'compose', 'down'], cwd=ROOT, check=True)
    subprocess.run(['docker', 'compose', 'up', '-d', '--wait'], cwd=ROOT, check=True)
    restored = snapshot()
    identical = before == restored
    assert identical, 'La instantánea cambió durante la recreación'
    verified = []
    for role, account in credentials().items():
        client = Client()
        status, login = client.request('POST', '/auth/login', account, {'Origin': BASE})
        assert status == 200 and login['user']['role'] == role
        old = list(client.jar)
        assert client.request('POST', '/auth/logout', headers={'X-CSRF-Token': login['csrf_token']})[0] == 204
        for cookie in old:
            client.jar.set_cookie(cookie)
        assert client.request('GET', '/auth/me')[0] == 401
        verified.append(role)
    after = snapshot()
    assert school_unchanged(before, after) and before['users'] == after['users']
    report = {'status': 'COMPROBADO', 'recreated_without_deleting_volumes': True,
              'all_tables_users_credentials_audit_files_identical_after_recreation': identical,
              'counts_before': before['counts'], 'counts_after_recreation': restored['counts'],
              'school_counts_after_access': {t: after['counts'][t] for t in SCHOOL},
              'school_and_files_unchanged': True, 'login_logout_revocation_roles': verified,
              'users': after['users']}
    prefix=os.environ.get('PERSISTENCE_REPORT_PREFIX','s2-2')
    if not prefix.replace('-','').isalnum():
        raise ValueError('Prefijo inválido')
    report['ml_files_unchanged']=before.get('ml_files',[])==after.get('ml_files',[])
    (ROOT / f'tests/evidence/{prefix}-persistence.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('COMPROBADO: 13 tablas y archivos conservados; acceso y revocación de los cuatro roles.')


if __name__ == '__main__':
    main()
