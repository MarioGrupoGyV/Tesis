"""PowerShell entrypoint, explicit S6 target, current Windows ADMIN credential.

Only sends the authorized package and an aggregate source audit through stdin.
Never puts passwords into argv, files, logs or environment variables.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys

from runtime_target import ROOT, Target
from windows_credentials import read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--document-python', type=Path)
    parser.add_argument('--evaluate', action='store_true')
    args = parser.parse_args()
    target = Target.load(args.target)
    target.assert_resources()
    credentials = read('ADMIN')
    if not credentials:
        raise RuntimeError('CURRENT_WINDOWS_ADMIN_CREDENTIAL_REQUIRED')
    audit = None
    if args.source:
        if not args.document_python or not args.document_python.is_file():
            raise RuntimeError('DOCUMENTARY_PYTHON_REQUIRED')
        result = subprocess.run([str(args.document_python), str(ROOT / 'infra/audit_retrospective_source.py'),
                                 '--source', str(args.source), '--package', str(args.package)],
                                capture_output=True, text=True, cwd=ROOT)
        if result.returncode:
            raise RuntimeError('RETROSPECTIVE_SOURCE_AUDIT_FAILED')
        audit = json.loads(result.stdout)
    code = "import sys\nfrom app.retrospective_cli import main\nsys.argv=['retrospective','--stdin'" + (",'--evaluate'" if args.evaluate else '') + "]\nmain()"
    payload = {**credentials, 'authorized_local_processing': True, 'source_audit': audit,
               'package_base64': base64.b64encode(args.package.read_bytes()).decode()}
    result = target.api_python(code, payload)
    print(json.dumps({'project': target.project, 'database': target.database, **result}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('RETROSPECTIVE_REGISTRATION_FAILED: revisar destino, credencial ADMIN y auditoría; sin publicar secretos.') from None
