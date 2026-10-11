"""Live browser runner with explicit destination; credentials remain in memory."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from runtime_target import ROOT, Target
from windows_credentials import read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--evidence-prefix', default='retro')
    args = parser.parse_args()
    target = Target.load(args.target)
    target.assert_resources()
    import re
    if not re.fullmatch('[a-z0-9-]+', args.evidence_prefix):
        raise RuntimeError('INVALID_EVIDENCE_PREFIX')
    if (ROOT / 'tests/evidence' / (args.evidence_prefix + '-playwright.json')).exists():
        raise RuntimeError('EVIDENCE_ALREADY_EXISTS')
    environment = {**os.environ, 'E2E_BASE_URL': target.web_url, 'RETROSPECTIVE_EVIDENCE_PREFIX': args.evidence_prefix,
                   'E2E_ACCOUNTS': json.dumps({role: read(role) for role in ('ADMIN','TUTOR','DIRECTOR','RESEARCHER')})}
    command = ['npx.cmd', 'playwright', 'test', '--config', 'playwright.retrospective.config.ts']
    result = subprocess.run(command, cwd=ROOT, env=environment)
    # Never serialize environment, credentials, cookies or private CSV rows.
    print(json.dumps({'status': 'COMPROBADO' if result.returncode == 0 else 'FALLIDO',
                      'project': target.project, 'browser_exit_code': result.returncode}))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
