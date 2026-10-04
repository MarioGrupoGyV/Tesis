"""Destinos S6 explícitos. Biblioteca estándar; nunca hay fallback al activo."""
import argparse
from datetime import UTC, datetime
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SECRET_FILES = ('owner-password', 'app-password', 'csrf-secret', 'app-database-url', 'owner-database-url')
LABEL = 'seguimiento.s6.target_id'
VOLUMES = ('db_data', 'import_data', 'ml_data')
TABLES = ('academic_periods','academic_snapshots','alerts','app_users','audit_events','user_sessions',
          'enrollments','followup_decisions','grade_sections','import_batches','interventions',
          'model_versions','predictions','students','synthetic_studies')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def docker(*args, **kwargs):
    result = subprocess.run(['docker', *map(str,args)], cwd=ROOT, capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError('TARGET_DOCKER_COMMAND_FAILED')
    return result


def private_directory(path, *, infrastructure=False):
    path = Path(path).absolute()
    if (path.is_relative_to(ROOT) and not (infrastructure and path.is_relative_to(ROOT/'.local/s6-runtime'))) or any(p.is_symlink() for p in (path,*path.parents)):
        raise RuntimeError('PRIVATE_DIRECTORY_INVALID')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'nt':
        sid = subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,text=True,check=True).stdout
        match = re.search(r'S-1-5-[0-9-]+',sid)
        if not match:
            raise RuntimeError('WINDOWS_USER_SID_UNAVAILABLE')
        result = subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r',
            '*'+match.group(0)+':(OI)(CI)F'],capture_output=True)
        if result.returncode:
            raise RuntimeError('PRIVATE_DIRECTORY_ACL_FAILED')
    return path


def write_new(path, content):
    with open(path,'xb') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def code_identity():
    names = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    hashes = {name:digest(ROOT/name) for name in sorted(set(names))
              if (ROOT/name).is_file() and not name.startswith('tests/evidence/')}
    locks = {name:value for name,value in hashes.items() if name.endswith(('requirements.txt','requirements-dev.txt',
        'requirements-s0.txt','package-lock.json'))}
    return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'files':hashes,'locks':locks,'tree_sha256':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()}


def validate_descriptor(data):
    if not isinstance(data,dict): raise RuntimeError('TARGET_DESCRIPTOR_INVALID')
    if data.get('version') != 1 or data.get('kind') not in ('INSTALL','RESTORE','ACTIVE'):
        raise RuntimeError('TARGET_VERSION_OR_KIND_INVALID')
    project, database = data.get('project',''), data.get('database','')
    if data['kind']=='ACTIVE':
        if project!='riesgo-escolar' or database!='riesgo_escolar':
            raise RuntimeError('ACTIVE_TARGET_IDENTITY_INVALID')
        expected = {v:'riesgo-escolar_'+v for v in VOLUMES}
    else:
        suffix = data['kind'].lower()
        if not re.fullmatch('s6-'+suffix+'-[0-9a-f]{12}',project) or database!=project.replace('-','_'):
            raise RuntimeError('ISOLATED_TARGET_IDENTITY_INVALID')
        expected = {v:project+'_'+v for v in VOLUMES}
    if data.get('volumes')!=expected or len(set(expected.values()))!=3:
        raise RuntimeError('TARGET_VOLUME_IDENTITY_INVALID')
    if not re.fullmatch(r'[0-9a-f-]{36}',data.get('target_id','')):
        raise RuntimeError('TARGET_ID_REQUIRED')
    ports = data.get('ports',{})
    if not isinstance(ports,dict): raise RuntimeError('TARGET_PORTS_INVALID')
    if set(ports)!= {'web','api','db'} or len(set(ports.values()))!=3 or any(type(p)!=int or not 1024<=p<=65535 for p in ports.values()):
        raise RuntimeError('TARGET_PORTS_INVALID')
    if data.get('web_url')!='http://localhost:'+str(ports['web']) or data.get('api_url')!='http://localhost:'+str(ports['api']):
        raise RuntimeError('TARGET_ORIGINS_INVALID')
    images=data.get('images',{})
    if not isinstance(images,dict) or set(images) != {'api','web','db'} or any(not isinstance(i,str) or not re.fullmatch('sha256:[0-9a-f]{64}',i) for i in images.values()):
        raise RuntimeError('TARGET_IMAGES_INVALID')
    return data


class Target:
    def __init__(self,data,path=None):
        self.data=validate_descriptor(data)
        self.path=Path(path).absolute() if path else None
        for name in ('project','database','web_url','api_url','kind','target_id'):
            setattr(self,name,data[name])

    @classmethod
    def load(cls,path):
        path=Path(path).absolute()
        if not path.is_file() or path.is_symlink() or path.stat().st_size>1024*1024:
            raise RuntimeError('TARGET_DESCRIPTOR_INVALID')
        return cls(json.loads(path.read_text(encoding='utf-8')),path)

    def command(self,*args):
        return ['docker','compose','-p',self.project,'-f',self.data['compose_file'],*map(str,args)]

    def configuration(self):
        path=Path(self.data['compose_file'])
        if path.is_symlink() or digest(path)!=self.data['compose_sha256']:
            raise RuntimeError('TARGET_COMPOSE_CHANGED')
        result=subprocess.run(self.command('config','--format','json'),cwd=ROOT,capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError('TARGET_CONFIG_INVALID')
        config=json.loads(result.stdout)
        if config['name']!=self.project or set(config['services'])!={'web','api','db'}:
            raise RuntimeError('TARGET_SERVICES_INVALID')
        if {k:v['name'] for k,v in config.get('volumes',{}).items()}!=self.data['volumes']:
            raise RuntimeError('TARGET_VOLUME_CONFIG_INVALID')
        for service,port in (('web',5173),('api',8000),('db',5432)):
            ports=config['services'][service].get('ports',[])
            if len(ports)!=1 or ports[0].get('host_ip')!='127.0.0.1' or int(ports[0]['published'])!=self.data['ports'][service] or ports[0]['target']!=port:
                raise RuntimeError('TARGET_BINDING_INVALID')
        if config['services']['db']['environment']['POSTGRES_DB']!=self.database:
            raise RuntimeError('TARGET_DATABASE_CONFIG_INVALID')
        allowed=config['services']['api']['environment'].get('ALLOWED_ORIGINS','')
        if set(allowed.split(','))!={self.web_url,self.web_url.replace('localhost','127.0.0.1')}:
            raise RuntimeError('TARGET_ORIGIN_CONFIG_INVALID')
        return config

    def containers(self):
        ids=docker('ps','-aq','--filter','label=com.docker.compose.project='+self.project,text=True).stdout.split()
        return json.loads(docker('inspect',*ids,text=True).stdout) if ids else []

    def assert_resources(self, *, fresh=False):
        self.configuration()
        containers=self.containers()
        if fresh and containers:
            raise RuntimeError('TARGET_PROJECT_EXISTS')
        known=docker('volume','ls','--format','{{.Name}}',text=True).stdout.splitlines()
        for volume in self.data['volumes'].values():
            if fresh and volume in known:
                raise RuntimeError('TARGET_VOLUME_EXISTS')
            if volume in known and self.kind!='ACTIVE':
                info=json.loads(docker('volume','inspect',volume,text=True).stdout)[0]
                if (info.get('Labels') or {}).get(LABEL)!=self.target_id:
                    raise RuntimeError('TARGET_VOLUME_OWNER_INVALID')
        for container in containers:
            labels=container['Config']['Labels'] or {}
            service=labels.get('com.docker.compose.service')
            if service not in ('api','web','db') or labels.get('com.docker.compose.oneoff','False').lower()=='true':
                raise RuntimeError('TARGET_UNEXPECTED_CONTAINER')
            if self.kind!='ACTIVE' and labels.get(LABEL)!=self.target_id:
                raise RuntimeError('TARGET_CONTAINER_OWNER_INVALID')
            if container['Image']!=self.data['images'][service]:
                raise RuntimeError('TARGET_RUNTIME_IMAGE_CHANGED')
            mounted={m['Name'] for m in container.get('Mounts',[]) if m['Type']=='volume'}
            expected=({self.data['volumes']['db_data']} if service=='db' else
                {self.data['volumes']['import_data'],self.data['volumes']['ml_data']} if service=='api' else set())
            if mounted!=expected:
                raise RuntimeError('TARGET_RUNTIME_MOUNTS_INVALID')
            for bindings in (container['HostConfig'].get('PortBindings') or {}).values():
                for binding in bindings or []:
                    if binding['HostIp']!='127.0.0.1' or int(binding['HostPort'])!=self.data['ports'][service]:
                        raise RuntimeError('TARGET_RUNTIME_BINDING_INVALID')
        if fresh:
            for port in self.data['ports'].values():
                with socket.socket() as probe:
                    try: probe.bind(('127.0.0.1',port))
                    except OSError: raise RuntimeError('TARGET_PORT_IN_USE') from None
        return containers

    def compose(self,*args,capture_output=False):
        self.assert_resources()
        if any(str(a) in ('--force','--force-recreate','-v','--volumes','down','build') for a in args):
            raise RuntimeError('TARGET_DESTRUCTIVE_COMMAND_FORBIDDEN')
        if not args or args[0] not in ('up','create','stop','start','restart','ps'):
            raise RuntimeError('TARGET_COMMAND_FORBIDDEN')
        if args and args[0] in ('stop','restart') and self.kind=='ACTIVE' and ('db' in args or len(args)==1):
            raise RuntimeError('ACTIVE_DATABASE_STOP_FORBIDDEN')
        return subprocess.run(self.command(*args),cwd=ROOT,check=True,capture_output=capture_output,
            text=capture_output,encoding='utf-8' if capture_output else None)

    def api_python(self,code,payload=None):
        self.assert_resources()
        guard = "from sqlalchemy import text\nfrom app.core.config import Settings\nfrom app.core.database import Database\n_d=Database(Settings())\nwith _d.engine.connect() as _c:\n assert _c.scalar(text('SELECT current_user'))=='riesgo_app'\n assert _c.scalar(text('SELECT current_database()'))=="+repr(self.database)+"\n_d.engine.dispose()\n"
        result=subprocess.run(self.command('exec','-T','api','python','-c',guard+code),cwd=ROOT,
            input=json.dumps(payload or {}),capture_output=True,text=True,encoding='utf-8')
        try: body=json.loads(result.stdout)
        except ValueError: raise RuntimeError('TARGET_API_COMMAND_FAILED') from None
        if result.returncode:
            error=body.get('code','TARGET_API_COMMAND_FAILED')
            raise RuntimeError(error if re.fullmatch('[A-Z0-9_]{1,100}',str(error)) else 'TARGET_API_COMMAND_FAILED')
        return body

    def api_command(self,module,command,payload):
        if module not in ('app.synthetic_cli','app.ml.cli'):
            raise RuntimeError('TARGET_MODULE_FORBIDDEN')
        return self.api_python('import runpy,sys\nsys.argv=['+repr(module)+','+repr(command)+']\nrunpy.run_module('+repr(module)+",run_name='__main__')",payload)

    def assert_identity(self):
        return self.api_python("import json\nprint(json.dumps({'database':"+repr(self.database)+",'user':'riesgo_app','project':"+repr(self.project)+"}))")

    def db_command(self,*args,**kwargs):
        self.assert_resources()
        service=next((c for c in self.containers() if c['Config']['Labels'].get('com.docker.compose.service')=='db'),None)
        if not service or not service['State']['Running']:
            raise RuntimeError('TARGET_DB_NOT_RUNNING')
        identity=docker('exec',service['Id'],'psql','-XAt','-U','riesgo_app','-d',self.database,
            '-c','SELECT current_database()||\':\'||current_user',text=True).stdout.strip()
        if identity!=self.database+':riesgo_app':
            raise RuntimeError('TARGET_DATABASE_IDENTITY_INVALID')
        return ['docker','exec','-i',service['Id'],*map(str,args)]


def create(kind,output,ports,*,images=None):
    output=Path(output).absolute()
    if output.exists(): raise RuntimeError('TARGET_DESCRIPTOR_EXISTS')
    directory=private_directory(output.parent)
    suffix=uuid4().hex[:12]
    project='s6-'+kind.lower()+'-'+suffix
    database=project.replace('-','_')
    sid=str(uuid4())
    if images is None:
        images={key:docker('image','inspect',name,'--format','{{.Id}}',text=True).stdout.strip()
            for key,name in (('api','riesgo-escolar-api'),('web','riesgo-escolar-web'),('db','postgres:17.6-bookworm'))}
    # Docker Desktop in this installation shares the workspace, but AppData file
    # binds resolve to empty directories. Only infrastructure secrets live in an
    # explicitly ignored private subdirectory; backup/descriptor remain outside.
    secret_dir=ROOT/'.local/s6-runtime'/project
    private_directory(secret_dir,infrastructure=True)
    if subprocess.run(['git','check-ignore','-q',str(secret_dir)],cwd=ROOT).returncode:
        raise RuntimeError('INFRASTRUCTURE_SECRETS_MUST_BE_IGNORED')
    owner,app=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    for name,value in zip(SECRET_FILES,(owner,app,secrets.token_urlsafe(48),
        f'postgresql+psycopg://riesgo_app:{app}@db:5432/{database}',
        f'postgresql+psycopg://riesgo_owner:{owner}@db:5432/{database}')):
        write_new(secret_dir/name,value.encode())
    labels={LABEL:sid,'seguimiento.s6.kind':kind}
    web_url='http://localhost:'+str(ports['web'])
    secret_map={'owner_password':'owner-password','app_password':'app-password','csrf_secret':'csrf-secret',
        'app_database_url':'app-database-url','owner_database_url':'owner-database-url'}
    config={'name':project,'services':{
        'db':{'image':images['db'],'labels':labels,'environment':{'POSTGRES_DB':database,'POSTGRES_USER':'riesgo_owner',
            'POSTGRES_PASSWORD_FILE':'/run/secrets/owner_password','APP_DB_PASSWORD_FILE':'/run/secrets/app_password','TZ':'UTC','PGTZ':'UTC'},
            'secrets':['owner_password','app_password'],'volumes':['db_data:/var/lib/postgresql/data',
                str(ROOT/'infra/db/init-app-role.sh')+':/docker-entrypoint-initdb.d/10-app-role.sh:ro'],
            'ports':[f'127.0.0.1:{ports["db"]}:5432'],
            'healthcheck':{'test':['CMD-SHELL',f'pg_isready -U riesgo_owner -d {database}'],'interval':'2s','timeout':'3s','retries':30}},
        'api':{'image':images['api'],'labels':labels,'environment':{'DATABASE_URL_FILE':'/run/secrets/app_database_url',
            'CSRF_SECRET_FILE':'/run/secrets/csrf_secret','APP_ENV':'development',
            'ALLOWED_ORIGINS':web_url+','+web_url.replace('localhost','127.0.0.1'),'SESSION_COOKIE_SECURE':'false',
            'TZ':'UTC','DISPLAY_TIMEZONE':'America/Lima','IMPORT_STORAGE_DIR':'/var/lib/riesgo/imports','ML_STORAGE_DIR':'/var/lib/riesgo/ml'},
            'secrets':['app_database_url','csrf_secret'],'volumes':['import_data:/var/lib/riesgo/imports','ml_data:/var/lib/riesgo/ml'],
            'depends_on':{'db':{'condition':'service_healthy'}},'ports':[f'127.0.0.1:{ports["api"]}:8000'],
            'healthcheck':{'test':['CMD','python','-c',"import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/ready',timeout=2)"],
                'interval':'2s','timeout':'3s','retries':30}},
        'web':{'image':images['web'],'labels':labels,'environment':{'API_PROXY_TARGET':'http://api:8000'},
            'depends_on':{'api':{'condition':'service_healthy'}},'ports':[f'127.0.0.1:{ports["web"]}:5173'],
            'healthcheck':{'test':['CMD','node','-e',"fetch('http://localhost:5173').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"],
                'interval':'2s','timeout':'3s','retries':30}}},
        'volumes':{v:{'name':project+'_'+v,'labels':labels} for v in VOLUMES},
        'secrets':{key:{'file':str(secret_dir/name)} for key,name in secret_map.items()}}
    compose_file=directory/(project+'-compose.json')
    write_new(compose_file,json.dumps(config,indent=2).encode())
    data={'version':1,'target_id':sid,'kind':kind,'project':project,'database':database,
        'ports':ports,'web_url':web_url,'api_url':'http://localhost:'+str(ports['api']),
        'volumes':{v:project+'_'+v for v in VOLUMES},'images':images,'compose_file':str(compose_file),
        'compose_sha256':digest(compose_file),'secrets_dir':str(secret_dir),'created_at':datetime.now(UTC).isoformat()}
    target=Target(data,output)
    target.assert_resources(fresh=True)
    write_new(output,json.dumps(data,indent=2).encode())
    return target


def active(output):
    output=Path(output).absolute()
    private_directory(output.parent)
    ids=docker('compose','ps','-q',text=True).stdout.split()
    containers=json.loads(docker('inspect',*ids,text=True).stdout)
    images={c['Config']['Labels']['com.docker.compose.service']:c['Image'] for c in containers}
    data={'version':1,'target_id':str(uuid4()),'kind':'ACTIVE','project':'riesgo-escolar','database':'riesgo_escolar',
        'ports':{'web':15173,'api':18000,'db':55432},'web_url':'http://localhost:15173','api_url':'http://localhost:18000',
        'volumes':{v:'riesgo-escolar_'+v for v in VOLUMES},'images':images,'compose_file':str(ROOT/'compose.yaml'),
        'compose_sha256':digest(ROOT/'compose.yaml'),'secrets_dir':str(ROOT/'.local/runtime-secrets')}
    target=Target(data,output)
    target.assert_identity()
    write_new(output,json.dumps(data,indent=2).encode())
    return target


def migrate(target):
    if target.kind!='INSTALL': raise RuntimeError('MIGRATION_ONLY_NEW_INSTALLATION')
    target.assert_resources()
    config=target.configuration()
    config['services']['api']['environment']['MIGRATION_DATABASE_URL_FILE']='/run/secrets/owner_database_url'
    config['services']['api']['secrets'].append('owner_database_url')
    config['secrets']['owner_database_url']={'file':str(Path(target.data['secrets_dir'])/'owner-database-url')}
    override=Path(target.data['compose_file']).with_name(target.project+'-migration.json')
    # Derived ephemeral configuration, always checked against the guarded target.
    override.write_text(json.dumps(config),encoding='utf-8')
    result=subprocess.run(['docker','compose','-p',target.project,'-f',str(override),'run','--rm','--no-deps','api',
        'python','-m','alembic','-c','/app/alembic.ini','upgrade','head'],cwd=ROOT,capture_output=True,text=True)
    if result.returncode: raise RuntimeError('TARGET_MIGRATION_FAILED')


def cleanup(target):
    """El comando explícito elimina únicamente recursos propios S6, nunca el activo."""
    if target.kind not in ('INSTALL','RESTORE'):
        raise RuntimeError('CLEANUP_ONLY_ISOLATED_S6')
    containers=target.assert_resources()
    owned={c['Id'] for c in containers}
    ids=docker('ps','-aq',text=True).stdout.split()
    for item in json.loads(docker('inspect',*ids,text=True).stdout) if ids else []:
        used={m.get('Name') for m in item.get('Mounts',[]) if m['Type']=='volume'}
        if used & set(target.data['volumes'].values()) and item['Id'] not in owned:
            raise RuntimeError('CLEANUP_SHARED_VOLUME_FORBIDDEN')
    target.compose('stop',capture_output=True)
    target.assert_resources()
    if owned: docker('rm',*sorted(owned),text=True)
    known=docker('volume','ls','--format','{{.Name}}',text=True).stdout.splitlines()
    for volume in target.data['volumes'].values():
        if volume in known:
            info=json.loads(docker('volume','inspect',volume,text=True).stdout)[0]
            if (info.get('Labels') or {}).get(LABEL)!=target.target_id: raise RuntimeError('CLEANUP_VOLUME_OWNER_INVALID')
            docker('volume','rm',volume,text=True)
    networks=docker('network','ls','-q','--filter','label=com.docker.compose.project='+target.project,text=True).stdout.split()
    if networks: docker('network','rm',*networks,text=True)
    # Keep descriptor and private configuration for identification; no recursive
    # Windows deletion or package cleanup is performed by this command.


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['create','active','up','migrate','bootstrap-admin','configure','stop','identity','cleanup'])
    parser.add_argument('--target',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--kind',choices=['INSTALL','RESTORE'],default='INSTALL')
    parser.add_argument('--web-port',type=int,default=15273)
    parser.add_argument('--api-port',type=int,default=18100)
    parser.add_argument('--db-port',type=int,default=55462)
    args=parser.parse_args(argv)
    try:
        if args.command in ('create','active'):
            if not args.output: parser.error('--output requerido fuera del checkout')
            target=active(args.output) if args.command=='active' else create(args.kind,args.output,
                {'web':args.web_port,'api':args.api_port,'db':args.db_port})
        else:
            if not args.target: parser.error('--target requerido')
            target=Target.load(args.target)
            if args.command=='up':
                target.compose('up','-d','--wait','db')
                if target.kind=='INSTALL': migrate(target)
                target.compose('up','-d','--wait','api','web')
            elif args.command=='migrate': migrate(target)
            elif args.command=='stop': target.compose('stop')
            elif args.command=='cleanup': cleanup(target)
            elif args.command in ('bootstrap-admin','configure'):
                target.assert_identity()
                if target.kind!='INSTALL': raise RuntimeError('SETUP_ONLY_NEW_INSTALLATION')
                module='app.bootstrap_admin' if args.command=='bootstrap-admin' else 'app.configure_context'
                subprocess.run(target.command('exec','api','python','-m',module),cwd=ROOT,check=True)
            else: target.assert_identity()
        print(json.dumps({'status':'COMPROBADO','kind':target.kind,'project':target.project,'database':target.database,
            'web_url':target.web_url,'volumes':target.data['volumes']}))
    except (RuntimeError,OSError,ValueError,subprocess.CalledProcessError) as error:
        code=str(error) if isinstance(error,RuntimeError) else 'TARGET_OPERATION_FAILED'
        print(json.dumps({'code':code})); return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
