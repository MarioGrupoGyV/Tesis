"""Persistencia real S6: reinicio de copia propia, comparación completa y parada."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from backup_restore import db_snapshot, file_inventory
from runtime_target import Target, private_directory, write_new


def check(target):
    if target.kind not in ('RESTORE', 'INSTALL'):
        raise RuntimeError('PERSISTENCE_ONLY_ISOLATED_S6')
    target.assert_identity()
    started = datetime.now(UTC).isoformat()
    with tempfile.TemporaryDirectory(prefix='s6-persistence-', dir=target.path.parent) as directory:
        private_directory(directory)
        before = db_snapshot(target)
        files_before = file_inventory(target, Path(directory))
        try:
            target.compose('stop', capture_output=True)
            # Reuses guarded existing containers/volumes. No migrate or stamp.
            target.compose('up', '-d', '--wait', capture_output=True)
            target.assert_identity()
            after = db_snapshot(target)
            files_after = file_inventory(target, Path(directory))
            if before != after or files_before != files_after:
                raise RuntimeError('PERSISTENCE_SNAPSHOT_CHANGED')
            return {'status': 'COMPROBADO', 'kind': target.kind, 'project': target.project,
                    'database': target.database, 'images': target.data['images'],
                    'counts_before': before['counts'], 'counts_after': after['counts'],
                    'all_15_tables_alembic_schema_roles_exact': True,
                    'all_private_files_exact': True, 'private_file_count': len(files_before),
                    'alembic': after['alembic'], 'schema_md5': after['schema_md5'],
                    'fingerprints': after['fingerprints'],
                    'files_inventory_sha256': hashlib.sha256(json.dumps(files_after, sort_keys=True).encode()).hexdigest(),
                    'started_at': started, 'finished_at': datetime.now(UTC).isoformat(),
                    'stopped_and_preserved': True, 'active_database_restarted': False,
                    'migration_or_generator_executed': False}
        finally:
            target.compose('stop', capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('El informe debe ser nuevo')
    try:
        report = check(Target.load(args.target))
        write_new(args.report, json.dumps(report, indent=2).encode())
        print(json.dumps({'status': report['status'], 'project': report['project'], 'stopped_and_preserved': True}))
        return 0
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError):
        write_new(args.report, json.dumps({'status': 'FALLIDO', 'code': 'S6_PERSISTENCE_FAILED'}).encode())
        print(json.dumps({'code': 'S6_PERSISTENCE_FAILED'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
