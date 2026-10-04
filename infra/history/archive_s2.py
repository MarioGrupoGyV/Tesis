"""Respaldo histórico privado y restauración aislada; nunca borra el origen."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, UTC

ROOT = Path(__file__).resolve().parents[2]

def run(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, **kwargs)

def main():
    if "name: riesgo-escolar-demo" not in (ROOT / "compose.yaml").read_text():
        raise SystemExit("Herramienta historica: no ejecutar sobre el entorno actual.")
    destination = ROOT / '.local/backups' / datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    destination.mkdir(parents=True)
    # Copia privada de configuración, sin modificar los secretos originales.
    shutil.copy2(ROOT / 'compose.yaml', destination / 'compose.previous.yaml')
    shutil.copytree(ROOT / '.local/secrets', destination / 'secrets')
    inventory = json.loads(subprocess.check_output(['docker', 'inspect', 'riesgo-escolar-demo-db-1'], text=True))[0]
    mounts = [{'name': m.get('Name'), 'destination': m['Destination']} for m in inventory['Mounts'] if m['Type'] == 'volume']
    # Pausa escritores antes de obtener el par consistente base/archivos.
    run('compose', 'stop', 'web', 'api')
    dump = destination / 'database.dump'
    with dump.open('wb') as output:
        run('exec', 'riesgo-escolar-demo-db-1', 'pg_dump', '-U', 'riesgo_owner', '-d', 'riesgo_escolar_demo', '-Fc', stdout=output)
    with (destination / 'imports.tar').open('wb') as output:
        run('run', '--rm', '-v', 'riesgo-escolar-demo_import_data:/source:ro', 'postgres:17.6-bookworm', 'tar', '-C', '/source', '-cf', '-', '.', stdout=output)
    name = 'riesgo-restore-' + destination.name.lower()
    password_file = destination / 'secrets/owner-password'
    run('run', '-d', '--name', name, '--mount', f'type=bind,source={password_file},target=/run/secrets/password,readonly',
        '-e', 'POSTGRES_PASSWORD_FILE=/run/secrets/password', '-e', 'POSTGRES_USER=riesgo_owner', '-e', 'POSTGRES_DB=restore_check', 'postgres:17.6-bookworm', stdout=subprocess.DEVNULL)
    import time
    for _ in range(30):
        if subprocess.run(['docker','exec',name,'pg_isready','-h','127.0.0.1','-U','riesgo_owner','-d','restore_check'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0:
            break
        time.sleep(1)
    run('exec', name, 'psql', '-U', 'riesgo_owner', '-d', 'restore_check', '-v', 'ON_ERROR_STOP=1', '-c', 'CREATE ROLE riesgo_app NOLOGIN;', stdout=subprocess.DEVNULL)
    with dump.open('rb') as source:
        run('exec', '-i', name, 'pg_restore', '-U', 'riesgo_owner', '-d', 'restore_check', '--exit-on-error', stdin=source)
    query = "SELECT table_name FROM information_schema.tables WHERE table_schema='risk_school' ORDER BY table_name"
    def sql(container, database, statement):
        return subprocess.check_output(['docker','exec',container,'psql','-U','riesgo_owner','-d',database,'-At','-c',statement],text=True).strip()
    tables = sql(name, 'restore_check', query).splitlines()
    counts = {}
    for table in tables:
        statement = f"SELECT count(*), md5(coalesce(string_agg(row_to_json(t)::text, '' ORDER BY id),'')) FROM risk_school.{table} t"
        before = sql('riesgo-escolar-demo-db-1', 'riesgo_escolar_demo', statement)
        assert before == sql(name, 'restore_check', statement), table
        counts[table] = int(before.split('|')[0])
    run('exec', name, 'mkdir', '/restored-imports')
    with (destination / 'imports.tar').open('rb') as source:
        run('exec', '-i', name, 'tar', '-C', '/restored-imports', '-xf', '-', stdin=source)
    # Comparación binaria del archivo reconstruido; tar preserva metadatos y contenido.
    restored = subprocess.check_output(['docker','exec',name,'tar','-C','/restored-imports','-cf','-','.'])
    assert hashlib.sha256(restored).digest() == hashlib.sha256((destination / 'imports.tar').read_bytes()).digest()
    origins = {table: sql(name,'restore_check',f'SELECT data_origin,count(*) FROM risk_school.{table} GROUP BY data_origin') for table in ('academic_periods','students','model_versions')}
    run('stop', name, stdout=subprocess.DEVNULL)
    run('compose', 'stop', 'db')
    report = {'status':'COMPROBADO','initial_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'backup_private_path':str(destination), 'previous_database':'riesgo_escolar_demo','volumes':mounts + [{'name':'riesgo-escolar-demo_import_data','destination':'/var/lib/riesgo/imports'}],
        'restoration_container':name,'tables_identical':len(tables),'counts':counts,'origins':origins,'csv_restored_identical':True,
        'hashes':{f:hashlib.sha256((destination/f).read_bytes()).hexdigest() for f in ('database.dump','imports.tar')}}
    (ROOT/'tests/evidence/s2-1-backup.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Respaldo y restauración comprobados; entorno anterior detenido. Ruta privada: '+str(destination))

if __name__ == '__main__':
    main()
