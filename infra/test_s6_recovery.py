"""PowerShell: pruebas recuperación con DPAPI Windows real y guards aislados."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'infra/tests'))
import test_s6_recovery as cases


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def record(self, test, status, reason=None):
        item = {'test': test.id(), 'status': status,
            'scope': getattr(test, 'scope', getattr(getattr(test, 'test_case', None), 'scope', 'UNIT'))}
        if reason:
            item['reason'] = reason
        self.cases.append(item)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, 'COMPROBADO')

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.record(test, 'FALLIDO')

    def addError(self, test, error):
        super().addError(test, error)
        self.record(test, 'FALLIDO')

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, 'OMITIDO', reason)

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self.record(subtest, 'FALLIDO')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    report = args.report.absolute()
    if (report.parent != ROOT / 'tests/evidence'
        or not re.fullmatch(r's6-[a-z0-9-]+\.json', report.name) or report.exists()):
        parser.error('Informe S6 nuevo en tests/evidence; no se sobrescribe evidencia')
    began = datetime.now(UTC).isoformat()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(
        unittest.defaultTestLoader.loadTestsFromModule(cases))
    paths = ('infra/runtime_target.py', 'infra/backup_restore.py', 'infra/windows_dpapi.py',
        'infra/tests/test_s6_recovery.py', 'infra/test_s6_recovery.py')
    body = {'status': 'COMPROBADO' if result.wasSuccessful() and not result.skipped else 'FALLIDO' if not result.wasSuccessful() else 'PENDIENTE',
        'started_at': began, 'finished_at': datetime.now(UTC).isoformat(),
        'runtime': {'platform': platform.system(), 'python': platform.python_version()},
        'command': 'py -3.12 -X utf8 infra/test_s6_recovery.py --report ' + str(args.report),
        'tests': result.testsRun, 'passed': sum(item['status'] == 'COMPROBADO' for item in result.cases),
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'cases': result.cases,
        'executed_code_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
        'docker_or_active_database_mutated': False,
        'native_windows': 'Actual CryptProtectData/CryptUnprotectData and ACL; private temporary packages cleaned',
        'mocks': 'Target collisions/lifecycle simulate Docker and PostgreSQL; these do not prove integrated restoration',
        'integrated_backup_restore': 'Requires separate real S6 backup/restore evidence'}
    with report.open('x', encoding='utf-8') as handle:
        json.dump(body, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({key: body[key] for key in ('status', 'tests', 'passed', 'failures', 'errors', 'skipped')}))
    return 0 if result.wasSuccessful() and not result.skipped else 2


if __name__ == '__main__':
    raise SystemExit(main())
