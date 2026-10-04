"""Perfil ADMIN explícito Windows, autenticado contra un destino identificado."""
import argparse
import getpass
import hashlib
import http.cookiejar
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
import warnings

import windows_credentials as store


def target_binding(target):
    identity = {key: getattr(target, key) for key in ('project', 'database', 'web_url', 'api_url', 'kind')}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise RuntimeError('OPERATOR_DESTINATION_REDIRECT_REFUSED')


class SessionClient:
    """Cookie en memoria; URL obligatoria, sin proxy o redirección a otro destino."""
    def __init__(self, target):
        target.assert_identity()
        self.target = target
        self.base_url = target.web_url
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect())

    def request(self, method, path, body=None, headers=None):
        if not path.startswith('/') or '://' in path or '\\' in path:
            raise RuntimeError('OPERATOR_REQUEST_PATH_INVALID')
        if method not in ('GET', 'HEAD'):
            self.target.assert_identity()
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + '/api/v1' + path, data=payload,
            method=method, headers={**({'Content-Type': 'application/json'} if payload is not None else {}),
                **(headers or {})})
        try:
            response = self.opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        except (urllib.error.URLError, OSError):
            raise RuntimeError('OPERATOR_DESTINATION_UNAVAILABLE') from None
        with response:
            content = response.read(1024 * 1024 + 1)
            if len(content) > 1024 * 1024:
                raise RuntimeError('OPERATOR_RESPONSE_INVALID')
            try:
                return response.status, json.loads(content) if content else None
            except (ValueError, UnicodeError):
                raise RuntimeError('OPERATOR_RESPONSE_INVALID') from None


def verify_admin(target, account, *, client_factory=SessionClient):
    """Autenticación real y revocación antes de aceptar un perfil. No crea usuarios."""
    target.assert_identity()
    client = client_factory(target)
    csrf = None
    try:
        status, login = client.request('POST', '/auth/login', account, {'Origin': target.web_url})
        if status != 200 or not isinstance(login, dict):
            raise RuntimeError('OPERATOR_ADMIN_AUTHENTICATION_REQUIRED')
        csrf = login.get('csrf_token')
        user = login.get('user', {})
        if user.get('role') != 'ADMIN' or not isinstance(csrf, str) or not csrf:
            raise RuntimeError('OPERATOR_ADMIN_AUTHENTICATION_REQUIRED')
        status, current = client.request('GET', '/auth/me')
        if (status != 200 or not isinstance(current, dict)
            or current.get('role') != 'ADMIN' or current.get('id') != user.get('id')):
            raise RuntimeError('OPERATOR_ADMIN_AUTHENTICATION_REQUIRED')
    finally:
        if csrf:
            status, _ = client.request('POST', '/auth/logout', headers={'X-CSRF-Token': csrf})
            if status != 204:
                raise RuntimeError('OPERATOR_VERIFICATION_LOGOUT_FAILED')
    target.assert_identity()


def register_profile(target, name, email, password, *, client_factory=SessionClient):
    store.operator_target(name)
    target.assert_identity()
    if store.read_operator_profile(name) is not None:
        raise RuntimeError('OPERATOR_PROFILE_EXISTS')
    # Bootstrap es quien valida 12–200 caracteres. Aquí se verifica el acceso real;
    # no se aplica la política de 20 caracteres de las cuentas de revisión S2.2.
    account = {'email': email.strip().lower(), 'password': password}
    verify_admin(target, account, client_factory=client_factory)
    store.write_new_operator_profile(name, account['email'], account['password'], target_binding(target))
    return {'status': 'COMPROBADO', 'profile': name, 'role': 'ADMIN',
        'target': {'project': target.project, 'database': target.database, 'kind': target.kind},
        'users_created': False, 'credentials_overwritten': False}


def admin_account(target, *, admin_credential=None, operator_profile=None):
    target.assert_identity()
    if bool(admin_credential) == bool(operator_profile):
        raise RuntimeError('EXPLICIT_ADMIN_ACCESS_REQUIRED')
    if admin_credential:
        if admin_credential != 'ADMIN':
            raise RuntimeError('ADMIN_CREDENTIAL_INVALID')
        account = store.read('ADMIN')
        if account is None:
            raise RuntimeError('ADMIN_CREDENTIAL_NOT_FOUND')
        return account
    account = store.read_operator_profile(operator_profile)
    if account is None:
        raise RuntimeError('OPERATOR_PROFILE_NOT_FOUND')
    if account['target_binding'] != target_binding(target):
        raise RuntimeError('OPERATOR_PROFILE_TARGET_MISMATCH')
    return {'email': account['email'], 'password': account['password']}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Registrar acceso ADMIN privado Windows contra un destino explícito; no crea usuarios.')
    parser.add_argument('command', choices=['register-profile'])
    parser.add_argument('--target', type=Path, required=True, help='Descriptor privado del destino identificado')
    parser.add_argument('--name', required=True, help='Nombre nuevo: minúsculas, números, guion o guion bajo')
    args = parser.parse_args(argv)
    try:
        from runtime_target import Target
        target = Target.load(args.target)
        target.assert_identity()
        store.operator_target(args.name)
        if store.read_operator_profile(args.name) is not None:
            raise RuntimeError('OPERATOR_PROFILE_EXISTS')
        if not sys.stdin.isatty():
            raise RuntimeError('OPERATOR_INTERACTIVE_TERMINAL_REQUIRED')
        email = input('Correo del administrador existente: ').strip()
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('Contraseña privada: ')
        result = register_profile(target, args.name, email, password)
        del password
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except getpass.GetPassWarning:
        print(json.dumps({'code': 'OPERATOR_PRIVATE_INPUT_UNAVAILABLE'})); return 2
    except (RuntimeError, OSError, ValueError):
        # Nunca incluir el correo/contraseña, errores ctypes, URL o traceback.
        error = sys.exc_info()[1]
        code = str(error)
        if not code or any(character not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for character in code):
            code = 'OPERATOR_PROFILE_FAILED'
        print(json.dumps({'code': code})); return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
