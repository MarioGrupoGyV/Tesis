"""Validación negativa y DPAPI nativo. No toca Docker ni la base activa."""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backup_restore as backup
import runtime_target as runtime
import windows_dpapi as dpapi


def descriptor(kind='RESTORE'):
    project = 'riesgo-escolar' if kind == 'ACTIVE' else 's6-' + kind.lower() + '-0123456789ab'
    database = 'riesgo_escolar' if kind == 'ACTIVE' else project.replace('-', '_')
    ports = {'web': 15173, 'api': 18000, 'db': 55432} if kind == 'ACTIVE' else {'web': 26273, 'api': 26200, 'db': 56262}
    return {'version': 1, 'kind': kind, 'target_id': str(uuid4()), 'project': project, 'database': database,
        'volumes': {name: project + '_' + name for name in runtime.VOLUMES}, 'ports': ports,
        'web_url': 'http://localhost:' + str(ports['web']), 'api_url': 'http://localhost:' + str(ports['api']),
        'images': {name: 'sha256:' + character * 64 for name, character in (('api', '1'), ('web', '2'), ('db', '3'))},
        'compose_file': 'not-used-compose.json', 'compose_sha256': '0' * 64, 'secrets_dir': 'not-used-secrets'}


def package_payloads():
    values = {'database.dump': b'isolated-archive-test-dump',
        'volumes/ml_data/.internal-key': b'isolated-archive-test-key',
        'volumes/ml_data/studies/fixture/payload.json': b'{}',
        'volumes/import_data/fixture/input.csv': b'header\n'}
    values.update({f'config/{name}': b'isolated-configuration-test-only' for name in runtime.SECRET_FILES})
    return values


def manifest_for(values):
    return {'version': 1, 'id': 's6-test-' + uuid4().hex, 'origin': 'SYNTHETIC', 'migration': '0004_followup',
        'database': {'counts': {name: 0 for name in runtime.TABLES},
            'fingerprints': {name: hashlib.md5(b'').hexdigest() for name in runtime.TABLES},
            'alembic': ['0004_followup']}, 'code': {'locks': {}}, 'source': descriptor('ACTIVE'),
        'inventory': {name: {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in values.items()}}


def zip_package(values=None, manifest=None, *, extra=(), include_manifest=True):
    values = package_payloads() if values is None else values
    manifest = manifest_for(values) if manifest is None else manifest
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in values.items():
                archive.writestr(name, data)
            if include_manifest:
                archive.writestr('manifest.json', json.dumps(manifest).encode())
            for name, data in extra:
                if isinstance(name, str):
                    # Preserve the actual ZIP name, including Windows backslash.
                    member = zipfile.ZipInfo('temporary-name')
                    member.filename = name
                    name = member
                archive.writestr(name, data)
    return buffer.getvalue()


class ArchiveValidationTests(unittest.TestCase):
    scope = 'REAL_PACKAGE_VALIDATOR_TEMPORARY_FIXTURES'

    def test_complete_inventory_validates_without_extraction(self):
        values = package_payloads()
        manifest = manifest_for(values)
        self.assertEqual(backup.validate_archive(zip_package(values, manifest))['inventory'], manifest['inventory'])

    def test_versions_and_origins_are_rejected_before_restore(self):
        for mutation in ({'version': 2}, {'origin': 'REAL'}, {'migration': '0003_synthetic_study'}):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(RuntimeError, '^BACKUP_VERSION_INCOMPATIBLE$'):
                values = package_payloads()
                manifest = {**manifest_for(values), **mutation}
                backup.validate_archive(zip_package(values, manifest))

    def test_missing_manifest_or_required_private_members(self):
        with self.assertRaisesRegex(RuntimeError, '^BACKUP_MANIFEST_MISSING$'):
            backup.validate_archive(zip_package(include_manifest=False))
        for missing in ('database.dump', 'config/csrf-secret', 'volumes/ml_data/.internal-key'):
            with self.subTest(missing=missing), self.assertRaisesRegex(RuntimeError, '^BACKUP_INVENTORY_INCOMPLETE$'):
                values = package_payloads()
                manifest = manifest_for(values)
                values.pop(missing)
                backup.validate_archive(zip_package(values, manifest))

    def test_corrupt_hash_size_and_inventory_coverage_are_rejected(self):
        values = package_payloads()
        for mutation in ({'sha256': '0' * 64}, {'size': 0}, {'size': True}, {'sha256': None}):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(RuntimeError, '^BACKUP_FILE_INTEGRITY_FAILED$'):
                manifest = manifest_for(values)
                manifest['inventory']['database.dump'].update(mutation)
                backup.validate_archive(zip_package(values, manifest))
        manifest = manifest_for(values)
        manifest['inventory'].pop('volumes/import_data/fixture/input.csv')
        with self.assertRaisesRegex(RuntimeError, '^BACKUP_INVENTORY_INCOMPLETE$'):
            backup.validate_archive(zip_package(values, manifest))

    def test_duplicate_member_and_unsafe_paths_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, '^BACKUP_DUPLICATE_MEMBER$'):
            backup.validate_archive(zip_package(extra=[('database.dump', b'duplicate')]))
        for name in ('../escape', '/absolute', 'C:/Windows/escape', 'volumes/../escape',
                     'volumes\\escape', './database.dump', 'volumes//duplicate', 'safe/./unsafe'):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, '^BACKUP_PATH_INVALID$'):
                backup.validate_archive(zip_package(extra=[(name, b'invalid')]))

    def test_symlink_directory_and_special_types_are_rejected(self):
        for name, mode in (('volumes/ml_data/link', stat.S_IFLNK | 0o777),
                           ('volumes/ml_data/socket', stat.S_IFSOCK | 0o600),
                           ('volumes/ml_data/device', stat.S_IFCHR | 0o600),
                           ('volumes/ml_data/directory/', stat.S_IFDIR | 0o700)):
            member = zipfile.ZipInfo(name)
            member.create_system = 3
            member.external_attr = mode << 16
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, '^BACKUP_(LINK_OR_MEMBER_INVALID|PATH_INVALID)$'):
                backup.validate_archive(zip_package(extra=[(member, b'invalid')]))

    def test_size_and_member_limits_do_not_need_large_test_allocation(self):
        content = zip_package()
        with patch.object(backup, 'MAX_PACKAGE', len(content) - 1), self.assertRaisesRegex(RuntimeError, '^BACKUP_SIZE_LIMIT$'):
            backup.validate_archive(content)
        with patch.object(backup, 'MAX_FILE', 4), self.assertRaisesRegex(RuntimeError, '^BACKUP_SIZE_LIMIT$'):
            backup.validate_archive(content)
        with patch.object(backup, 'MAX_MEMBERS', 1), self.assertRaisesRegex(RuntimeError, '^BACKUP_MEMBER_LIMIT$'):
            backup.validate_archive(content)

    def test_unknown_member_and_database_coverage_are_rejected(self):
        values = package_payloads()
        values['checkout/source.py'] = b'forbidden-checkout-member'
        with self.assertRaisesRegex(RuntimeError, '^BACKUP_MEMBER_UNEXPECTED$'):
            backup.validate_archive(zip_package(values))
        values.pop('checkout/source.py')
        manifest = manifest_for(values)
        manifest['database']['counts'].pop('followup_decisions')
        with self.assertRaisesRegex(RuntimeError, '^BACKUP_DATABASE_COVERAGE_INVALID$'):
            backup.validate_archive(zip_package(values, manifest))

    def test_wrong_json_types_are_sanitized(self):
        values = package_payloads()
        for mutation, expected in (([], 'BACKUP_MANIFEST_INVALID'),
                ({**manifest_for(values), 'inventory': []}, 'BACKUP_INVENTORY_INVALID'),
                ({**manifest_for(values), 'database': []}, 'BACKUP_DATABASE_COVERAGE_INVALID')):
            with self.subTest(expected=expected), self.assertRaisesRegex(RuntimeError, '^' + expected + '$'):
                backup.validate_archive(zip_package(values, mutation))
        manifest = manifest_for(values)
        manifest['inventory']['database.dump'] = 'invalid-record'
        with self.assertRaisesRegex(RuntimeError, '^BACKUP_INVENTORY_INVALID$'):
            backup.validate_archive(zip_package(values, manifest))

    def test_non_zip_and_truncated_zip_are_sanitized(self):
        for content in (b'not-an-archive', zip_package()[:64]):
            with self.subTest(size=len(content)), self.assertRaisesRegex(RuntimeError, '^BACKUP_ARCHIVE_INVALID$'):
                backup.validate_archive(content)


class TargetGuardTests(unittest.TestCase):
    scope = 'UNIT_TARGET_GUARDS_NO_DOCKER'

    def test_valid_install_restore_and_active_descriptors(self):
        for kind in ('INSTALL', 'RESTORE', 'ACTIVE'):
            self.assertEqual(runtime.Target(descriptor(kind)).kind, kind)

    def test_historical_active_volume_aliases_and_unknown_destination_rejected(self):
        for mutation, code in (({'project': 'riesgo-escolar-demo'}, 'ISOLATED_TARGET_IDENTITY_INVALID'),
                ({'database': 'riesgo_escolar'}, 'ISOLATED_TARGET_IDENTITY_INVALID'),
                ({'kind': 'DEMO'}, 'TARGET_VERSION_OR_KIND_INVALID'),
                ({'volumes': {v: 'riesgo-escolar_' + v for v in runtime.VOLUMES}}, 'TARGET_VOLUME_IDENTITY_INVALID'),
                ({'volumes': {v: 'riesgo-escolar-demo_' + v for v in runtime.VOLUMES}}, 'TARGET_VOLUME_IDENTITY_INVALID')):
            with self.subTest(code=code), self.assertRaisesRegex(RuntimeError, '^' + code + '$'):
                runtime.Target({**descriptor(), **mutation})

    def test_port_origin_image_and_id_guards(self):
        for mutation, code in (({'ports': {'web': 26273, 'api': 26273, 'db': 56262}}, 'TARGET_PORTS_INVALID'),
                ({'web_url': 'http://external.example.com'}, 'TARGET_ORIGINS_INVALID'),
                ({'target_id': ''}, 'TARGET_ID_REQUIRED'),
                ({'images': {'api': 'latest', 'db': 'latest', 'web': 'latest'}}, 'TARGET_IMAGES_INVALID')):
            with self.subTest(code=code), self.assertRaisesRegex(RuntimeError, '^' + code + '$'):
                runtime.Target({**descriptor(), **mutation})

    def test_existing_project_and_volume_refuse_fresh_target(self):
        target = runtime.Target(descriptor())
        with patch.object(target, 'configuration', return_value={}), patch.object(target, 'containers', return_value=[{}]), self.assertRaisesRegex(RuntimeError, '^TARGET_PROJECT_EXISTS$'):
            target.assert_resources(fresh=True)
        with patch.object(target, 'configuration', return_value={}), patch.object(target, 'containers', return_value=[]), patch.object(runtime, 'docker', return_value=SimpleNamespace(stdout=target.data['volumes']['ml_data'] + '\n')), self.assertRaisesRegex(RuntimeError, '^TARGET_VOLUME_EXISTS$'):
            target.assert_resources(fresh=True)

    def test_unknown_volume_owner_refused_before_operation(self):
        target = runtime.Target(descriptor())
        volume = target.data['volumes']['db_data']
        def docker(*args, **kwargs):
            return SimpleNamespace(stdout=volume + '\n' if args[:2] == ('volume', 'ls') else json.dumps([{'Labels': {runtime.LABEL: 'another-owner'}}]))
        with patch.object(target, 'configuration', return_value={}), patch.object(target, 'containers', return_value=[]), patch.object(runtime, 'docker', side_effect=docker), self.assertRaisesRegex(RuntimeError, '^TARGET_VOLUME_OWNER_INVALID$'):
            target.assert_resources()

    def test_destructive_and_active_database_stop_commands_refused(self):
        target = runtime.Target(descriptor('ACTIVE'))
        with patch.object(target, 'assert_resources', return_value=[]), patch.object(runtime.subprocess, 'run') as run:
            for args in (('stop',), ('restart',), ('stop', 'db'), ('restart', 'db')):
                with self.subTest(args=args), self.assertRaisesRegex(RuntimeError, '^ACTIVE_DATABASE_STOP_FORBIDDEN$'):
                    target.compose(*args)
            for args in (('down',), ('up', '--force-recreate'), ('rm', '-v')):
                with self.subTest(args=args), self.assertRaisesRegex(RuntimeError, '^TARGET_DESTRUCTIVE_COMMAND_FORBIDDEN$'):
                    target.compose(*args)
            run.assert_not_called()

    def test_active_cleanup_refused_before_inspection_or_mutation(self):
        target = runtime.Target(descriptor('ACTIVE'))
        with patch.object(target, 'assert_resources') as inspect, patch.object(runtime, 'docker') as docker, patch.object(target, 'compose') as compose:
            with self.assertRaisesRegex(RuntimeError, '^CLEANUP_ONLY_ISOLATED_S6$'):
                runtime.cleanup(target)
        inspect.assert_not_called()
        docker.assert_not_called()
        compose.assert_not_called()

    def test_unknown_compose_command_refused_without_execution(self):
        target = runtime.Target(descriptor())
        with patch.object(target, 'assert_resources', return_value=[]), patch.object(runtime.subprocess, 'run') as run:
            for args in ((), ('unknown-operation',), ('exec', 'api', 'arbitrary-command')):
                with self.subTest(args=args), self.assertRaisesRegex(RuntimeError, '^TARGET_COMMAND_FORBIDDEN$'):
                    target.compose(*args)
            run.assert_not_called()


class StorageHelperCommandTests(unittest.TestCase):
    scope = 'UNIT_COMMAND_CAPTURE_NO_DOCKER'

    def test_helpers_override_inherited_application_labels_and_isolate_storage(self):
        data = descriptor('RESTORE')
        target = SimpleNamespace(data=data, target_id=data['target_id'], assert_resources=lambda: None)
        with tempfile.TemporaryDirectory(prefix='s6-storage-command-') as temporary:
            directory = Path(temporary)
            with patch.object(backup.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as command:
                backup.volume_tar(target, 'ml_data', directory / 'export.tar')
                with zipfile.ZipFile(io.BytesIO(zip_package())) as archive:
                    backup.restore_files(target, archive, 'ml_data', directory)
            self.assertEqual(command.call_count, 2)
            for index, call in enumerate(command.call_args_list):
                args = call.args[0]
                labels = [args[position + 1] for position, value in enumerate(args) if value == '--label']
                self.assertEqual(labels, [
                    'com.docker.compose.project=seguimiento-s6-storage-' + target.target_id,
                    'com.docker.compose.service=storage', 'com.docker.compose.oneoff=True'])
                self.assertNotIn('com.docker.compose.project=riesgo-escolar', labels)
                self.assertEqual(args[args.index('--network') + 1], 'none')
                self.assertIn('--read-only', args)
                self.assertEqual(args[args.index('--user') + 1], '0')
                self.assertEqual(args[args.index('--entrypoint') + 1], 'python')
                mount = args[args.index('--mount') + 1]
                self.assertEqual(mount, 'type=volume,source=' + data['volumes']['ml_data']
                    + ',target=/private' + (',readonly' if index == 0 else ''))
                self.assertIn(data['images']['api'], args)


class FakeProcess:
    def __init__(self, snapshot='00000003-00000042-1', *, timeout=False):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(snapshot + '\n')
        self.stderr = io.StringIO()
        self.timeout = timeout
        self.killed = False
        self.communications = []

    def communicate(self, input=None, timeout=None):
        self.communications.append(input)
        if self.timeout and not self.killed:
            raise subprocess.TimeoutExpired('fake-private-psql', 10)
        return '', ''

    def kill(self):
        self.killed = True


class FakeWindowTarget:
    database = 's6_mock_window_only'
    def __init__(self, running=('api', 'web'), fail_stop=False):
        self.running = running
        self.fail_stop = fail_stop
        self.commands = []

    def containers(self):
        return [{'Config': {'Labels': {'com.docker.compose.service': name}}, 'State': {'Running': name in self.running}}
            for name in ('db', 'api', 'web')]

    def compose(self, *args, **kwargs):
        self.commands.append(args)
        if self.fail_stop and args[0] == 'stop':
            raise RuntimeError('FAKE_PARTIAL_STOP_FAILURE')

    def db_command(self, *args, **kwargs):
        return ['fake-private-psql']


class ConsistentWindowTests(unittest.TestCase):
    scope = 'UNIT_LIFECYCLE_MOCKS_NO_DATABASE_PAUSE'

    def test_failure_resumes_exact_initial_writers_and_releases_transaction(self):
        for running in (('api', 'web'), ('api',), ('web',), ()):
            target = FakeWindowTarget(running)
            process = FakeProcess()
            with self.subTest(running=running), patch.object(backup, 'check_writers'), patch.object(backup.subprocess, 'Popen', return_value=process):
                with self.assertRaisesRegex(RuntimeError, '^SIMULATED_CAPTURE_FAILURE$'):
                    with backup.consistent_window(target) as window:
                        self.assertEqual(window['services_paused'], list(running))
                        self.assertIn('pg_export_snapshot()', process.stdin.getvalue())
                        raise RuntimeError('SIMULATED_CAPTURE_FAILURE')
            expected = [('stop', *running), ('start', *running), ('up', '-d', '--wait', '--no-deps', *running)] if running else []
            self.assertEqual(target.commands, expected)
            self.assertEqual(process.communications, ['COMMIT;\n'])

    def test_partial_stop_failure_still_resumes_initial_writers(self):
        target = FakeWindowTarget(('api',), fail_stop=True)
        with patch.object(backup, 'check_writers'), patch.object(backup.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(RuntimeError, '^FAKE_PARTIAL_STOP_FAILURE$'):
                with backup.consistent_window(target):
                    pass
            process.assert_not_called()
        self.assertEqual(target.commands, [('stop', 'api'), ('start', 'api'), ('up', '-d', '--wait', '--no-deps', 'api')])

    def test_invalid_exported_snapshot_and_timeout_resume_writers(self):
        for process, code in ((FakeProcess(snapshot='not-a-snapshot'), 'BACKUP_SNAPSHOT_LOCK_FAILED'),
                              (FakeProcess(timeout=True), 'CAPTURE_FAILURE')):
            target = FakeWindowTarget(('api', 'web'))
            with self.subTest(code=code), patch.object(backup, 'check_writers'), patch.object(backup.subprocess, 'Popen', return_value=process):
                with self.assertRaisesRegex(RuntimeError, '^' + code + '$'):
                    with backup.consistent_window(target):
                        raise RuntimeError('CAPTURE_FAILURE')
            self.assertEqual(target.commands[-2:], [('start', 'api', 'web'), ('up', '-d', '--wait', '--no-deps', 'api', 'web')])
            if process.timeout:
                self.assertTrue(process.killed)

    def test_writer_rejection_never_pauses_services(self):
        target = FakeWindowTarget()
        with patch.object(backup, 'check_writers', side_effect=RuntimeError('BACKUP_WRITER_IN_PROGRESS')), patch.object(backup.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(RuntimeError, '^BACKUP_WRITER_IN_PROGRESS$'):
                with backup.consistent_window(target):
                    pass
            process.assert_not_called()
        self.assertEqual(target.commands, [])


class WriterInspectionTests(unittest.TestCase):
    scope = 'UNIT_EXECUTED_PROC_INSPECTOR_MOCK_FILESYSTEM'

    def inspect(self, entries):
        class ProcFile:
            def __init__(self, process_id, content):
                self.parent = SimpleNamespace(name=str(process_id))
                self.content = content
            def read_bytes(self):
                return self.content
        class ProcRoot:
            def glob(self, pattern):
                return [ProcFile(identifier, content) for identifier, content in entries]
        class ProcTarget:
            project = 's6-mock-proc-inspection'
            data = {'volumes': {volume: 's6-mock-' + volume for volume in runtime.VOLUMES}}
            def assert_identity(self):
                pass
            def api_python(self, code):
                output = io.StringIO()
                with patch('pathlib.Path', return_value=ProcRoot()), redirect_stdout(output):
                    exec(code, {})
                return json.loads(output.getvalue())
        with patch.object(backup, 'docker', return_value=SimpleNamespace(stdout='')):
            backup.check_writers(ProcTarget())

    def test_actual_inspector_detects_module_and_runpy_launchers(self):
        for content in (b'python\0-m\0app.synthetic_cli\0compare',
                        b"python\0-c\0import runpy;runpy.run_module('app.synthetic_cli')",
                        b'python\0-m\0app.configure_context', b'python\0-m\0alembic\0upgrade'):
            with self.subTest(launcher=content.split(b'\0')[:2]), self.assertRaisesRegex(RuntimeError, '^BACKUP_WRITER_IN_PROGRESS$'):
                self.inspect([(os.getpid() + 1000, content)])

    def test_actual_inspector_excludes_observer_and_idle_api(self):
        self.inspect([(os.getpid(), b'python\0-c\0observer literals app.synthetic_cli'),
            (os.getpid() + 1000, b'python\0-m\0uvicorn\0app.main:app')])


@unittest.skipUnless(os.name == 'nt', 'DPAPI y ACL nativos requieren Windows')
class NativeWindowsRecoveryTests(unittest.TestCase):
    scope = 'NATIVE_WINDOWS_DPAPI_AND_PRIVATE_TEMPORARIES'

    @classmethod
    def setUpClass(cls):
        parent = runtime.private_directory(Path(os.environ['LOCALAPPDATA']) / 'SeguimientoEscolar' / 'RecoveryTests')
        cls.private = tempfile.TemporaryDirectory(prefix='s6-negative-', dir=parent)
        cls.directory = runtime.private_directory(Path(cls.private.name))

    @classmethod
    def tearDownClass(cls):
        cls.private.cleanup()

    def test_native_dpapi_roundtrip_tamper_and_foreign_format(self):
        plain = b'private-test-only-' + os.urandom(128)
        protected = dpapi.protect(plain)
        self.assertTrue(protected != plain and plain not in protected)
        self.assertTrue(dpapi.unprotect(protected) == plain, 'DPAPI round-trip inválido')
        tampered = bytearray(protected)
        tampered[-1] ^= 1
        with self.assertRaisesRegex(RuntimeError, '^DPAPI_INTEGRITY_OR_IDENTITY_FAILED$'):
            dpapi.unprotect(bytes(tampered))
        with self.assertRaisesRegex(RuntimeError, '^BACKUP_FORMAT_INVALID$'):
            dpapi.unprotect(b'foreign-package')

    def test_native_registered_package_verifies_and_external_unregistered_rejects(self):
        values = package_payloads()
        manifest = manifest_for(values)
        name = manifest['id'] + '.sebackup'
        package = self.directory / name
        content = zip_package(values, manifest)
        runtime.write_new(package, dpapi.protect(content))
        registry = package.with_suffix('.registered.json')
        record = {'version': 1, 'id': manifest['id'], 'file': name,
            'cipher_sha256': runtime.digest(package), 'bytes': package.stat().st_size}
        runtime.write_new(registry, json.dumps(record).encode())
        with patch.object(backup, 'location', return_value=self.directory):
            opened, observed = backup.verified_content(package)
            self.assertTrue(opened == content)
            self.assertEqual(observed['id'], manifest['id'])
            other = self.directory / ('s6-unregistered-' + uuid4().hex + '.sebackup')
            runtime.write_new(other, dpapi.protect(content))
            with self.assertRaisesRegex(RuntimeError, '^BACKUP_NOT_REGISTERED_OWN_PACKAGE$'):
                backup.verified_content(other)
            package.write_bytes(package.read_bytes()[:-1])
            with self.assertRaisesRegex(RuntimeError, '^BACKUP_CIPHER_INTEGRITY_FAILED$'):
                backup.verified_content(package)

    def test_tar_symlink_hardlink_traversal_duplicate_and_safe_member(self):
        for kind in ('valid', 'symlink', 'hardlink', 'traversal', 'duplicate'):
            path = self.directory / ('s6-' + kind + '-' + uuid4().hex + '.tar')
            with tarfile.open(path, 'w') as archive:
                member = tarfile.TarInfo('../escape' if kind == 'traversal' else 'private/file')
                if kind in ('symlink', 'hardlink'):
                    member.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
                    member.linkname = '/outside'
                    archive.addfile(member)
                else:
                    member.size = 4
                    archive.addfile(member, io.BytesIO(b'test'))
                    if kind == 'duplicate':
                        archive.addfile(member, io.BytesIO(b'test'))
            if kind == 'valid':
                self.assertEqual(list(backup.tar_members(path)), [('private/file', b'test')])
            else:
                code = {'symlink': 'BACKUP_LINK_OR_MEMBER_INVALID', 'hardlink': 'BACKUP_LINK_OR_MEMBER_INVALID',
                    'traversal': 'BACKUP_PATH_INVALID', 'duplicate': 'BACKUP_DUPLICATE_MEMBER'}[kind]
                with self.subTest(kind=kind), self.assertRaisesRegex(RuntimeError, '^' + code + '$'):
                    list(backup.tar_members(path))

    def test_new_descriptor_refuses_existing_file_before_any_docker_write(self):
        path = self.directory / 'existing-descriptor.json'
        runtime.write_new(path, b'preserved-original-file')
        with patch.object(runtime, 'docker') as docker, self.assertRaisesRegex(RuntimeError, '^TARGET_DESCRIPTOR_EXISTS$'):
            runtime.create('RESTORE', path, {'web': 26273, 'api': 26200, 'db': 56262})
        docker.assert_not_called()
        self.assertEqual(path.read_bytes(), b'preserved-original-file')


if __name__ == '__main__':
    unittest.main()
