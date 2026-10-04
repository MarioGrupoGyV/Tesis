"""Respaldo DPAPI propio y restauración S6 aislada. No restaura el activo."""
import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from uuid import uuid4

from runtime_target import (ROOT, Target, TABLES, SECRET_FILES, code_identity, create,
    digest, docker, private_directory, write_new)
from windows_dpapi import protect, unprotect

MAX_PACKAGE=512*1024*1024
MAX_FILE=128*1024*1024
MAX_MEMBERS=10000


def location():
    if os.name!='nt': raise RuntimeError('WINDOWS_DPAPI_REQUIRED')
    return private_directory(Path(os.environ['LOCALAPPDATA'])/'SeguimientoEscolar/Backups')


def safe_member(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or '\0' in name:
        raise RuntimeError('BACKUP_PATH_INVALID')
    parts=PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '.' in parts.parts or str(parts)!=name:
        raise RuntimeError('BACKUP_PATH_INVALID')
    if not re.fullmatch(r'[A-Za-z0-9._/-]+',name): raise RuntimeError('BACKUP_PATH_INVALID')
    return name


def validate_archive(content):
    if len(content)>MAX_PACKAGE: raise RuntimeError('BACKUP_SIZE_LIMIT')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members=archive.infolist()
            if not 1<=len(members)<=MAX_MEMBERS: raise RuntimeError('BACKUP_MEMBER_LIMIT')
            names=set()
            total=0
            for item in members:
                safe_member(item.orig_filename)
                name=safe_member(item.filename)
                if name in names: raise RuntimeError('BACKUP_DUPLICATE_MEMBER')
                names.add(name)
                mode=item.external_attr>>16
                if item.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0,stat.S_IFREG)):
                    raise RuntimeError('BACKUP_LINK_OR_MEMBER_INVALID')
                if item.flag_bits & 1: raise RuntimeError('BACKUP_ENCRYPTED_MEMBER_INVALID')
                total+=item.file_size
                if item.file_size>MAX_FILE or total>MAX_PACKAGE: raise RuntimeError('BACKUP_SIZE_LIMIT')
            if 'manifest.json' not in names: raise RuntimeError('BACKUP_MANIFEST_MISSING')
            manifest=json.loads(archive.read('manifest.json'))
            if not isinstance(manifest,dict): raise RuntimeError('BACKUP_MANIFEST_INVALID')
            if manifest.get('version')!=1 or manifest.get('origin')!='SYNTHETIC' or manifest.get('migration')!='0004_followup':
                raise RuntimeError('BACKUP_VERSION_INCOMPATIBLE')
            inventory=manifest.get('inventory',{})
            if not isinstance(inventory,dict): raise RuntimeError('BACKUP_INVENTORY_INVALID')
            required={'database.dump',*(f'config/{name}' for name in SECRET_FILES),'volumes/ml_data/.internal-key'}
            if not required<=names or set(inventory)!=names-{'manifest.json'}:
                raise RuntimeError('BACKUP_INVENTORY_INCOMPLETE')
            database=manifest.get('database',{})
            if not isinstance(database,dict) or not isinstance(database.get('counts'),dict) or set(database['counts'])!=set(TABLES):
                raise RuntimeError('BACKUP_DATABASE_COVERAGE_INVALID')
            for item in members:
                if item.filename=='manifest.json': continue
                if not (item.filename=='database.dump' or item.filename.startswith(('config/','volumes/import_data/','volumes/ml_data/'))):
                    raise RuntimeError('BACKUP_MEMBER_UNEXPECTED')
                expected=inventory[item.filename]
                if not isinstance(expected,dict): raise RuntimeError('BACKUP_INVENTORY_INVALID')
                data=archive.read(item.filename)
                if type(expected.get('size'))!=int or item.file_size!=expected['size'] or hashlib.sha256(data).hexdigest()!=expected.get('sha256'):
                    raise RuntimeError('BACKUP_FILE_INTEGRITY_FAILED')
            return manifest
    except (zipfile.BadZipFile,KeyError,ValueError,OSError):
        raise RuntimeError('BACKUP_ARCHIVE_INVALID') from None


def db_snapshot(target):
    counts=' UNION ALL '.join("SELECT '"+t+"' AS name,count(*) AS count,md5(coalesce(string_agg(row_to_json(r)::text,'' ORDER BY id),'')) AS fingerprint FROM risk_school."+t+' r' for t in TABLES)
    schema="""SELECT 'constraint' AS kind,c.conrelid::regclass::text AS object,c.conname AS name,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='risk_school'
UNION ALL SELECT 'index',schemaname||'.'||tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='risk_school'
UNION ALL SELECT 'trigger',t.tgrelid::regclass::text,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='risk_school' AND NOT t.tgisinternal
UNION ALL SELECT 'function',n.nspname,p.proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='risk_school'
UNION ALL SELECT 'column',table_schema||'.'||table_name,column_name,data_type||':'||is_nullable||':'||coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='risk_school'
UNION ALL SELECT 'grant',table_schema||'.'||table_name,grantee,privilege_type FROM information_schema.role_table_grants WHERE table_schema='risk_school'"""
    sql="SET timezone='UTC'; SELECT json_build_object('counts',(SELECT json_object_agg(name,count ORDER BY name) FROM ("+counts+") x),'fingerprints',(SELECT json_object_agg(name,fingerprint ORDER BY name) FROM ("+counts+") x),'alembic',(SELECT json_agg(version_num ORDER BY version_num) FROM public.alembic_version),'roles',(SELECT json_agg(json_build_object('name',rolname,'superuser',rolsuper,'createdb',rolcreatedb,'createrole',rolcreaterole,'settings',rolconfig) ORDER BY rolname) FROM pg_roles WHERE rolname IN ('riesgo_owner','riesgo_app')),'tables',(SELECT json_agg(table_name ORDER BY table_name) FROM information_schema.tables WHERE table_schema='risk_school'),'schema_md5',md5((SELECT string_agg(row_to_json(x)::text,'' ORDER BY kind,object,name,definition) FROM ("+schema+") x)));"
    # Alembic intentionally has no API grant. Owner is used only for recovery
    # diagnostics/dump, never for application actions; db_command guards app identity.
    result=subprocess.run(target.db_command('psql','-XqAt','-v','ON_ERROR_STOP=1','-U','riesgo_owner','-d',target.database,
        '-c',sql),cwd=ROOT,capture_output=True,text=True)
    if result.returncode: raise RuntimeError('BACKUP_DATABASE_SNAPSHOT_FAILED')
    value=json.loads(result.stdout)
    if value['alembic']!=['0004_followup'] or set(value['counts'])!=set(TABLES) or value['tables']!=sorted(TABLES):
        raise RuntimeError('BACKUP_SCHEMA_INCOMPATIBLE')
    return value


VOLUME_EXPORT='''import os,sys,tarfile
from pathlib import Path
root=Path('/private')
paths=sorted(root.rglob('*'))
for p in paths:
 s=p.lstat()
 if p.is_symlink() or (p.is_file() and s.st_nlink!=1) or not (p.is_dir() or p.is_file()):
  raise SystemExit('PRIVATE_LINK_OR_SPECIAL_FILE_FORBIDDEN')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|',format=tarfile.PAX_FORMAT) as t:
 for p in paths:
  if p.is_file(): t.add(p,arcname=str(p.relative_to(root)),recursive=False)
'''


def volume_tar(target,name,output):
    target.assert_resources()
    with open(output,'xb') as handle:
        result=subprocess.run(['docker','run','--rm','--network','none','--read-only','--user','0',
            '--label','com.docker.compose.project=seguimiento-s6-storage-'+target.target_id,
            '--label','com.docker.compose.service=storage','--label','com.docker.compose.oneoff=True',
            '--mount',f'type=volume,source={target.data["volumes"][name]},target=/private,readonly',
            '--entrypoint','python',target.data['images']['api'],'-c',VOLUME_EXPORT],cwd=ROOT,
            stdout=handle,stderr=subprocess.PIPE)
    if result.returncode: raise RuntimeError('BACKUP_VOLUME_EXPORT_FAILED')


def tar_members(path):
    with tarfile.open(path,'r:') as archive:
        names=set()
        total=0
        for item in archive.getmembers():
            name=safe_member(item.name)
            if name in names: raise RuntimeError('BACKUP_DUPLICATE_MEMBER')
            names.add(name)
            if not item.isfile() or item.issym() or item.islnk(): raise RuntimeError('BACKUP_LINK_OR_MEMBER_INVALID')
            total+=item.size
            if item.size>MAX_FILE or total>MAX_PACKAGE or len(names)>MAX_MEMBERS: raise RuntimeError('BACKUP_SIZE_LIMIT')
            yield name,archive.extractfile(item).read()


def file_inventory(target,directory):
    inventory={}
    for name in ('import_data','ml_data'):
        path=directory/(uuid4().hex+'.tar')
        volume_tar(target,name,path)
        try:
            for relative,data in tar_members(path):
                inventory[name+'/'+relative]={'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        finally: path.unlink()
    return inventory


def check_writers(target):
    target.assert_identity()
    code="""import json,os
from pathlib import Path
bad=[]
for p in Path('/proc').glob('[0-9]*/cmdline'):
 if p.parent.name==str(os.getpid()): continue
 try: c=p.read_bytes().replace(b'\\0',b' ')
 except OSError: continue
 if any(x in c for x in (b'app.synthetic_cli',b'app.bootstrap_admin',b'app.configure_context',b'app.ml.cli',b'-m alembic')):
  bad.append(p.parent.name)
print(json.dumps({'commands_in_progress':len(bad)}))
"""
    if target.api_python(code)['commands_in_progress']:
        raise RuntimeError('BACKUP_WRITER_IN_PROGRESS')
    all_ids=docker('ps','-q',text=True).stdout.split()
    if all_ids:
        containers=json.loads(docker('inspect',*all_ids,text=True).stdout)
        for container in containers:
            volumes={m.get('Name') for m in container.get('Mounts',[]) if m['Type']=='volume'}
            if volumes & set(target.data['volumes'].values()) and container['Config']['Labels'].get('com.docker.compose.project')!=target.project:
                raise RuntimeError('BACKUP_SHARED_VOLUME_WRITER')


@contextmanager
def consistent_window(target):
    check_writers(target)
    running=[c['Config']['Labels']['com.docker.compose.service'] for c in target.containers()
        if c['State']['Running'] and c['Config']['Labels']['com.docker.compose.service'] in ('web','api')]
    connection=None
    start=datetime.now(UTC).isoformat()
    try:
        if running: target.compose('stop',*running,capture_output=True)
        # SHARE blocks external data writers while allowing the snapshot dump.
        connection=subprocess.Popen(target.db_command('psql','-XqAt','-v','ON_ERROR_STOP=1','-U','riesgo_owner','-d',target.database),
            cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        tables=','.join('risk_school.'+t for t in TABLES)+',public.alembic_version'
        connection.stdin.write("BEGIN ISOLATION LEVEL REPEATABLE READ; SET LOCAL lock_timeout='5s'; LOCK TABLE "+tables+" IN SHARE MODE; SELECT pg_export_snapshot();\n")
        connection.stdin.flush()
        snapshot=connection.stdout.readline().strip()
        if not re.fullmatch('[0-9A-Fa-f-]+',snapshot): raise RuntimeError('BACKUP_SNAPSHOT_LOCK_FAILED')
        yield {'start':start,'snapshot':snapshot,'services_paused':running}
    finally:
        if connection is not None:
            try:
                connection.communicate('COMMIT;\n',timeout=10)
            except (OSError,subprocess.TimeoutExpired):
                connection.kill(); connection.communicate()
        if running:
            target.compose('start',*running,capture_output=True)
            target.compose('up','-d','--wait','--no-deps',*running,capture_output=True)


def backup(target):
    if target.kind!='ACTIVE': raise RuntimeError('BACKUP_REQUIRES_EXPLICIT_ACTIVE_SOURCE')
    directory=location()
    identifier='s6-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:12]
    work=private_directory(directory/(identifier+'.partial'))
    attempt={'id':identifier,'status':'INCOMPLETO','started_at':datetime.now(UTC).isoformat(),
        'source':{'kind':target.kind,'project':target.project,'database':target.database}}
    write_new(work/'attempt.json',json.dumps(attempt,indent=2).encode())
    final=directory/(identifier+'.sebackup')
    try:
        with consistent_window(target) as window:
            before=db_snapshot(target)
            dump=work/'database.dump'
            with open(dump,'xb') as handle:
                result=subprocess.run(target.db_command('pg_dump','-U','riesgo_owner','-d',target.database,
                    '--format=custom','--snapshot='+window['snapshot']),cwd=ROOT,stdout=handle,stderr=subprocess.PIPE)
            if result.returncode: raise RuntimeError('BACKUP_DUMP_FAILED')
            payloads={'database.dump':dump.read_bytes()}
            for volume in ('import_data','ml_data'):
                path=work/(volume+'.tar')
                volume_tar(target,volume,path)
                for name,data in tar_members(path): payloads['volumes/'+volume+'/'+name]=data
            for name in SECRET_FILES:
                path=Path(target.data['secrets_dir'])/name
                if path.is_symlink() or not path.is_file(): raise RuntimeError('BACKUP_CONFIG_MISSING')
                payloads['config/'+name]=path.read_bytes()
            after=db_snapshot(target)
            check_files=file_inventory(target,work)
            recorded={k.removeprefix('volumes/'):{'size':len(v),'sha256':hashlib.sha256(v).hexdigest()}
                for k,v in payloads.items() if k.startswith('volumes/')}
            if before!=after or check_files!=recorded: raise RuntimeError('BACKUP_STATE_CHANGED')
            manifest={'version':1,'id':identifier,'origin':'SYNTHETIC','migration':'0004_followup',
                'created_at':datetime.now(UTC).isoformat(),'window':{**window,'end':datetime.now(UTC).isoformat()},
                'source':{k:target.data[k] for k in ('kind','project','database','volumes','ports','images')},
                'code':code_identity(),'database':before,'inventory':
                    {k:{'size':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in payloads.items()},
                'recovery':'Roles recreated by init-app-role.sh; full ownership/ACL restored; API riesgo_app. DPAPI user Windows.'}
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in payloads.items(): archive.writestr(name,data)
            archive.writestr('manifest.json',json.dumps(manifest,sort_keys=True).encode())
        content=buffer.getvalue()
        validate_archive(content)
        encrypted=protect(content)
        if unprotect(encrypted)!=content: raise RuntimeError('BACKUP_DPAPI_ROUNDTRIP_FAILED')
        write_new(final,encrypted)
        record={'version':1,'id':identifier,'file':final.name,'cipher_sha256':digest(final),'bytes':final.stat().st_size}
        write_new(directory/(identifier+'.registered.json'),json.dumps(record,indent=2).encode())
        attempt.update(status='COMPROBADO',finished_at=datetime.now(UTC).isoformat())
        report={'status':'COMPROBADO','backup_id':identifier,'backup_file':final.name,
            'cipher_sha256':record['cipher_sha256'],'bytes':record['bytes'],'origin':'SYNTHETIC',
            'source':manifest['source'],'window':manifest['window'],'database':before,
            'private_file_count':len(recorded),'file_inventory_sha256':hashlib.sha256(json.dumps(recorded,sort_keys=True).encode()).hexdigest(),
            'code':manifest['code'],'dpapi_round_trip':True,'writers_resumed':True}
        return report
    finally:
        # Only this invocation's private partial directory; retain sanitized attempt.
        for path in work.iterdir():
            if path.name!='attempt.json' and path.is_file(): path.unlink()
        (work/'attempt.json').write_text(json.dumps(attempt,indent=2),encoding='utf-8')


def verified_content(path):
    path=Path(path).absolute()
    directory=location()
    if path.parent!=directory or path.is_symlink() or not re.fullmatch(r's6-[A-Za-z0-9-]+\.sebackup',path.name):
        raise RuntimeError('BACKUP_NOT_REGISTERED_OWN_PACKAGE')
    registry=path.with_suffix('.registered.json')
    if not registry.is_file() or registry.is_symlink(): raise RuntimeError('BACKUP_NOT_REGISTERED_OWN_PACKAGE')
    record=json.loads(registry.read_text())
    if not isinstance(record,dict): raise RuntimeError('BACKUP_REGISTRATION_INVALID')
    if path.stat().st_size>MAX_PACKAGE: raise RuntimeError('BACKUP_SIZE_LIMIT')
    if record.get('version')!=1 or record.get('file')!=path.name or path.stat().st_size!=record.get('bytes') or digest(path)!=record.get('cipher_sha256'):
        raise RuntimeError('BACKUP_CIPHER_INTEGRITY_FAILED')
    content=unprotect(path.read_bytes())
    manifest=validate_archive(content)
    if manifest['id']!=record['id']: raise RuntimeError('BACKUP_REGISTRATION_MISMATCH')
    return content,manifest


VOLUME_RESTORE='''import os,sys,tarfile
from pathlib import Path
root=Path('/private')
if any(root.iterdir()): raise SystemExit('RESTORE_VOLUME_NOT_EMPTY')
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as t:
 for item in t:
  p=root/item.name
  if not item.isfile() or item.name.startswith('/') or '..' in Path(item.name).parts: raise SystemExit('RESTORE_MEMBER_INVALID')
  p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  with p.open('xb') as h: h.write(t.extractfile(item).read())
  os.chmod(p,0o600)
for p in [root,*root.rglob('*')]:
 os.chown(p,10001,10001)
 if p.is_dir(): os.chmod(p,0o700)
'''


def restore_files(target,archive,volume,work):
    path=work/(volume+'.tar')
    with tarfile.open(path,'w') as output:
        prefix='volumes/'+volume+'/'
        for item in archive.infolist():
            if item.filename.startswith(prefix):
                data=archive.read(item)
                entry=tarfile.TarInfo(safe_member(item.filename[len(prefix):]))
                entry.size=len(data); entry.mode=0o600
                output.addfile(entry,io.BytesIO(data))
    target.assert_resources()
    with open(path,'rb') as handle:
        result=subprocess.run(['docker','run','--rm','-i','--network','none','--read-only','--user','0',
            '--label','com.docker.compose.project=seguimiento-s6-storage-'+target.target_id,
            '--label','com.docker.compose.service=storage','--label','com.docker.compose.oneoff=True',
            '--mount',f'type=volume,source={target.data["volumes"][volume]},target=/private',
            '--entrypoint','python',target.data['images']['api'],'-c',VOLUME_RESTORE],cwd=ROOT,
            stdin=handle,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode: raise RuntimeError('RESTORE_VOLUME_FAILED')


def restore_check(path,output,ports):
    content,manifest=verified_content(path)
    current=code_identity()
    if manifest['code']['locks']!=current['locks']:
        raise RuntimeError('RESTORE_LOCKS_INCOMPATIBLE')
    # Restore the same application/DB images; no training, migration or signing.
    target=create('RESTORE',output,ports,images=manifest['source']['images'])
    target.assert_resources(fresh=True)
    target.compose('up','-d','--wait','db')
    work=private_directory(Path(output).parent/(target.project+'-restore.partial'))
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            dump=work/'database.dump'
            write_new(dump,archive.read('database.dump'))
            # Empty roles/database initialized, schema restored solely from dump.
            with open(dump,'rb') as handle:
                result=subprocess.run(target.db_command('pg_restore','-U','riesgo_owner','-d',target.database,'--exit-on-error'),
                    cwd=ROOT,stdin=handle,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if result.returncode: raise RuntimeError('RESTORE_PG_RESTORE_FAILED')
            # Volumes created with guarded project labels before filling, no API writer.
            target.compose('create','--no-recreate','api',capture_output=True)
            for volume in ('import_data','ml_data'): restore_files(target,archive,volume,work)
            # Original CSRF signing secret preserves restored sessions; DB passwords
            # and connection URLs stay new and bound to this isolated database.
            (Path(target.data['secrets_dir'])/'csrf-secret').write_bytes(archive.read('config/csrf-secret'))
        restored=db_snapshot(target)
        files=file_inventory(target,work)
        expected={k.removeprefix('volumes/'):v for k,v in manifest['inventory'].items() if k.startswith('volumes/')}
        if restored!=manifest['database'] or files!=expected: raise RuntimeError('RESTORE_SNAPSHOT_MISMATCH')
        target.compose('up','-d','--wait','api','web')
        target.assert_identity()
        trust=target.api_python("""import json
from sqlalchemy import select
from app.core.config import Settings
from app.core.database import Database
from app.models.ml import ModelVersion
from app.models.synthetic import SyntheticStudyRecord
from app.services.synthetic_study import compatible_model,selected_artifact
from app.ml.artifacts import ArtifactStore
s=Settings();d=Database(s)
with d.session_factory() as c:
 m=c.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
 st=c.get(SyntheticStudyRecord,m.study_id)
 compatible_model(s,st,m)
 manifest,key=selected_artifact(s,st)
 ArtifactStore(s.ml_storage_dir).load(key)
print(json.dumps({'hmac_verified':True,'model_compatible':True,'algorithm':m.algorithm,'regenerated':False}))
""")
        return {'status':'COMPROBADO','kind':target.kind,'target_id':target.target_id,'project':target.project,
            'database_name':target.database,'ports':target.data['ports'],'volumes':target.data['volumes'],
            'backup_id':manifest['id'],'before_login_exact_all_tables':True,'before_login_exact_all_files':True,
            'database':restored,'private_file_count':len(files),'trust':trust,
            'code':current,'target_descriptor':str(target.path)}
    except Exception:
        target.compose('stop',capture_output=True)
        raise
    finally:
        for child in work.iterdir():
            if child.is_file(): child.unlink()
        work.rmdir()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['backup','verify','restore-check'])
    parser.add_argument('--target',type=Path)
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--web-port',type=int,default=15274)
    parser.add_argument('--api-port',type=int,default=18101)
    parser.add_argument('--db-port',type=int,default=55463)
    args=parser.parse_args(argv)
    if args.report.exists(): parser.error('El informe debe ser nuevo')
    try:
        if args.command=='backup':
            if not args.target: parser.error('--target requerido')
            report=backup(Target.load(args.target))
        else:
            if not args.backup: parser.error('--backup requerido')
            if args.command=='restore-check':
                if not args.output: parser.error('--output descriptor privado nuevo requerido')
                report=restore_check(args.backup,args.output,{'web':args.web_port,'api':args.api_port,'db':args.db_port})
            else:
                _,m=verified_content(args.backup)
                report={'status':'COMPROBADO','backup_id':m['id'],'inventory_verified':True,
                    'members':len(m['inventory']),'database':m['database'],'dpapi_decrypted':True}
        write_new(args.report,json.dumps(report,indent=2).encode())
        print(json.dumps({k:v for k,v in report.items() if k in ('status','backup_id','backup_file','project','database_name','private_file_count')}))
    except (RuntimeError,OSError,ValueError,subprocess.CalledProcessError) as error:
        code=str(error) if isinstance(error,RuntimeError) else 'BACKUP_OPERATION_FAILED'
        if not args.report.exists(): write_new(args.report,json.dumps({'status':'FALLIDO','code':code}).encode())
        print(json.dumps({'code':code})); return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
