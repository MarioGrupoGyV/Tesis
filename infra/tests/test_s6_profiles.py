"""Pruebas de selección/guards y Credential Manager nativo; sin cuentas operativas."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import operator_profiles as profiles
import study
import windows_credentials as store


class FakeTarget:
    project = 's6-unit-install'
    database = 's6_unit_install'
    web_url = 'http://127.0.0.1:29173'
    api_url = 'http://127.0.0.1:29000'
    kind = 'INSTALL'

    def __init__(self):
        self.checks = 0
        self.commands = []

    def assert_identity(self):
        self.checks += 1

    def api_command(self, module, command, payload):
        self.commands.append((module, command, payload))
        return {'status': 'sanitized'}


class FakeClient:
    def __init__(self, login_status=200, role='ADMIN', me_role='ADMIN', logout_status=204):
        self.calls = []
        self.login_status = login_status
        self.role = role
        self.me_role = me_role
        self.logout_status = logout_status

    def __call__(self, target):
        return self

    def request(self, method, path, body=None, headers=None):
        self.calls.append((method, path, body, headers))
        if path == '/auth/login':
            if self.login_status != 200:
                return self.login_status, {'code': 'INVALID_CREDENTIALS'}
            return 200, {'user': {'id': 'fixture-admin', 'role': self.role}, 'csrf_token': 'fixture-only-csrf'}
        if path == '/auth/me':
            return 200, {'id': 'fixture-admin', 'role': self.me_role}
        return self.logout_status, None


class ProfileGuardsTests(unittest.TestCase):
    def test_legacy_access_reads_only_admin_and_accepts_real_policy(self):
        target = FakeTarget()
        account = {'email': 'fixture@example.com', 'password': 'ValidLength13'}
        with patch.object(store, 'read', return_value=account) as read:
            result = profiles.admin_account(target, admin_credential='ADMIN')
        self.assertTrue(result == account)
        read.assert_called_once_with('ADMIN')
        self.assertGreater(target.checks, 0)

    def test_missing_legacy_entry_fails_without_review_account_dependency(self):
        with patch.object(store, 'read', return_value=None):
            with self.assertRaisesRegex(RuntimeError, '^ADMIN_CREDENTIAL_NOT_FOUND$'):
                profiles.admin_account(FakeTarget(), admin_credential='ADMIN')

    def test_exactly_one_explicit_access_is_required(self):
        for values in ({}, {'admin_credential': 'ADMIN', 'operator_profile': 'operator-unit'}):
            with self.subTest(values=values), self.assertRaisesRegex(RuntimeError, '^EXPLICIT_ADMIN_ACCESS_REQUIRED$'):
                profiles.admin_account(FakeTarget(), **values)

    def test_profile_is_bound_to_target_before_private_command(self):
        target = FakeTarget()
        value = {'email': 'fixture@example.com', 'password': 'unit-test-only', 'target_binding': '0' * 64}
        with patch.object(store, 'read_operator_profile', return_value=value):
            with self.assertRaisesRegex(RuntimeError, '^OPERATOR_PROFILE_TARGET_MISMATCH$'):
                profiles.admin_account(target, operator_profile='operator-unit')
            value['target_binding'] = profiles.target_binding(target)
            result = profiles.admin_account(target, operator_profile='operator-unit')
        self.assertEqual(set(result), {'email', 'password'})

    def test_profile_missing_is_sanitized(self):
        with patch.object(store, 'read_operator_profile', return_value=None):
            with self.assertRaisesRegex(RuntimeError, '^OPERATOR_PROFILE_NOT_FOUND$'):
                profiles.admin_account(FakeTarget(), operator_profile='operator-unit')

    def test_binding_changes_for_every_identity_field(self):
        original = profiles.target_binding(FakeTarget())
        for field in ('project', 'database', 'web_url', 'api_url', 'kind'):
            target = FakeTarget()
            setattr(target, field, getattr(target, field) + '-changed')
            self.assertNotEqual(profiles.target_binding(target), original)

    def test_operator_namespace_cannot_address_s22_or_traversal(self):
        for name in ('ADMIN', '../ADMIN', 'a/b', 'a\\b', 'a', '', 'área', 'name:secret'):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, '^OPERATOR_PROFILE_NAME_INVALID$'):
                store.operator_target(name)
        self.assertTrue(store.operator_target('s6-unit').startswith(store.OPERATOR_PREFIX))
        self.assertFalse(store.operator_target('s6-unit').startswith(store.PREFIX))

    def test_registration_authenticates_and_logs_out_before_store(self):
        target = FakeTarget()
        client = FakeClient()
        password = 'ValidLength13'  # 13, valid bootstrap password below fixture-only 20.
        with patch.object(store, 'read_operator_profile', return_value=None), patch.object(store, 'write_new_operator_profile') as write:
            result = profiles.register_profile(target, 'operator-unit', 'Own.Admin@example.com', password, client_factory=client)
        self.assertEqual([call[1] for call in client.calls], ['/auth/login', '/auth/me', '/auth/logout'])
        write.assert_called_once_with('operator-unit', 'own.admin@example.com', password, profiles.target_binding(target))
        self.assertTrue(result['users_created'] is False and result['credentials_overwritten'] is False)
        self.assertFalse(password in json.dumps(result))

    def test_invalid_inactive_and_non_admin_profiles_never_store(self):
        # Invalid and inactive users deliberately share the same safe HTTP response.
        for case, client in (('invalid', FakeClient(login_status=401)),
                             ('inactive', FakeClient(login_status=401)),
                             ('tutor', FakeClient(role='TUTOR')), ('changed-me', FakeClient(me_role='DIRECTOR'))):
            with self.subTest(case=case), patch.object(store, 'read_operator_profile', return_value=None), patch.object(store, 'write_new_operator_profile') as write:
                with self.assertRaisesRegex(RuntimeError, '^OPERATOR_ADMIN_AUTHENTICATION_REQUIRED$'):
                    profiles.register_profile(FakeTarget(), 'operator-unit', 'fixture@example.com', 'private-unit-only', client_factory=client)
                write.assert_not_called()
                if client.login_status == 200:
                    self.assertEqual(client.calls[-1][1], '/auth/logout')

    def test_failed_logout_prevents_store(self):
        with patch.object(store, 'read_operator_profile', return_value=None), patch.object(store, 'write_new_operator_profile') as write:
            with self.assertRaisesRegex(RuntimeError, '^OPERATOR_VERIFICATION_LOGOUT_FAILED$'):
                profiles.register_profile(FakeTarget(), 'operator-unit', 'fixture@example.com', 'private-unit-only', client_factory=FakeClient(logout_status=503))
            write.assert_not_called()

    def test_existing_profile_preserved_without_another_login(self):
        client = FakeClient()
        with patch.object(store, 'read_operator_profile', return_value={'existing': True}), patch.object(store, 'write_new_operator_profile') as write:
            with self.assertRaisesRegex(RuntimeError, '^OPERATOR_PROFILE_EXISTS$'):
                profiles.register_profile(FakeTarget(), 'operator-unit', 'fixture@example.com', 'private-unit-only', client_factory=client)
            self.assertEqual(client.calls, [])
            write.assert_not_called()

    def test_study_private_command_requires_target(self):
        with self.assertRaisesRegex(RuntimeError, '^EXPLICIT_TARGET_REQUIRED$'):
            study.internal('status', {})
        target = FakeTarget()
        result = study.internal('status', {'email': 'fixture', 'password': 'unit-only'}, target=target)
        self.assertEqual(result, {'status': 'sanitized'})
        self.assertEqual(target.commands[0][0:2], ('app.synthetic_cli', 'status'))
        self.assertGreater(target.checks, 0)

    def test_study_cli_requires_target_and_exclusive_access(self):
        for args in (['status', '--admin-credential', 'ADMIN'],
                     ['status', '--target', 'explicit.json'],
                     ['status', '--target', 'explicit.json', '--admin-credential', 'ADMIN', '--operator-profile', 'operator-unit']):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit:
                study.main(args)
            self.assertEqual(exit.exception.code, 2)

    def test_registration_cli_refuses_non_interactive_secret_input(self):
        target = FakeTarget()
        module = SimpleNamespace(Target=SimpleNamespace(load=lambda path: target))
        output = io.StringIO()
        with patch.dict(sys.modules, {'runtime_target': module}), patch.object(sys.stdin, 'isatty', return_value=False), patch.object(store, 'read_operator_profile', return_value=None), redirect_stdout(output):
            status = profiles.main(['register-profile', '--target', 'explicit.json', '--name', 'operator-unit'])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output.getvalue())['code'], 'OPERATOR_INTERACTIVE_TERMINAL_REQUIRED')


@unittest.skipUnless(os.name == 'nt', 'Credential Manager nativo requiere Windows')
class NativeCredentialManagerTests(unittest.TestCase):
    def test_native_roundtrip_collision_cleanup_and_s22_conservation(self):
        before = {role: store.read(role) for role in store.ROLES}
        name = 's6-native-' + uuid4().hex
        password = secrets.token_urlsafe(14)
        binding = profiles.target_binding(FakeTarget())
        expected = {'email': 'temporary.native@example.com', 'password': password, 'target_binding': binding}
        try:
            self.assertIsNone(store.read_operator_profile(name))
            store.write_new_operator_profile(name, expected['email'], password, binding)
            self.assertTrue(store.read_operator_profile(name) == expected, 'Credential Manager round-trip no coincide')
            with self.assertRaisesRegex(RuntimeError, '^OPERATOR_PROFILE_EXISTS$'):
                store.write_new_operator_profile(name, 'another@example.com', 'other-private-value', binding)
            self.assertTrue(store.read_operator_profile(name) == expected, 'Colisión modificó entrada temporal')
        finally:
            if name in store._created_operator_profiles:
                store.delete_operator_profile_created_here(name)
        self.assertIsNone(store.read_operator_profile(name))
        self.assertTrue({role: store.read(role) for role in store.ROLES} == before, 'Entradas S2.2 deben conservarse')
        with self.assertRaisesRegex(RuntimeError, '^OPERATOR_PROFILE_NOT_CREATED_HERE$'):
            store.delete_operator_profile_created_here('s6-unowned-' + uuid4().hex)

    def test_native_concurrent_registration_does_not_overwrite(self):
        name = 's6-native-' + uuid4().hex
        binding = profiles.target_binding(FakeTarget())
        candidates = [secrets.token_urlsafe(14), secrets.token_urlsafe(14)]
        def attempt(password):
            try:
                store.write_new_operator_profile(name, 'temporary.native@example.com', password, binding)
                return 'CREATED', password
            except RuntimeError as error:
                return str(error), None
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(attempt, candidates))
            self.assertEqual(sorted(code for code, _ in results), ['CREATED', 'OPERATOR_PROFILE_EXISTS'])
            chosen = next(password for code, password in results if code == 'CREATED')
            self.assertTrue(store.read_operator_profile(name)['password'] == chosen, 'Se conserva el ganador de la creación')
        finally:
            if name in store._created_operator_profiles:
                store.delete_operator_profile_created_here(name)


if __name__ == '__main__':
    unittest.main()
