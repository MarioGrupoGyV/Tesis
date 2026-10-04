"""PowerShell: estudio explícito con credencial Windows ADMIN, nunca contraseña en args."""
import argparse
import base64
from datetime import UTC,datetime
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from uuid import uuid4
from operator_profiles import SessionClient, admin_account

ROOT=Path(__file__).resolve().parents[1]

CSV_HEADERS=('student_code','grade','section','cutoff_at','target_date','available_at',
    'window_start','average_grade','attendance_pct','activities_pct','participation_level',
    'behavior_incidents','age_years')


def export_destination(output):
    """Destino explícito: no permite nombres especiales, enlaces o un checkout Git."""
    path=Path(output)
    if not path.is_absolute() or '..' in path.parts:
        raise RuntimeError('CSV_OUTPUT_PATH_INVALID')
    if (re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.csv',path.name) is None
        or path.stem.upper().split('.')[0] in {'CON','PRN','AUX','NUL',
            *(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}):
        raise RuntimeError('CSV_OUTPUT_NAME_INVALID')
    if any(part.is_symlink() for part in (path,*path.parents)):
        raise RuntimeError('CSV_OUTPUT_LINK_FORBIDDEN')
    try:
        parent=path.parent.resolve(strict=True)
    except OSError:
        raise RuntimeError('CSV_OUTPUT_DIRECTORY_REQUIRED') from None
    if not parent.is_dir():
        raise RuntimeError('CSV_OUTPUT_DIRECTORY_REQUIRED')
    if parent.is_relative_to(ROOT.resolve()) or any((part/'.git').exists() for part in (parent,*parent.parents)):
        raise RuntimeError('CSV_OUTPUT_INSIDE_GIT')
    if path.exists():
        raise RuntimeError('CSV_OUTPUT_EXISTS')
    return parent/path.name


def export_csv(account,study_id,output,*,loader=None,target=None):
    """CSV de entrada únicamente; datos privados del comando quedan en memoria."""
    path=export_destination(output)
    exported=(loader or (lambda command,account,**values: internal(command,account,target=target,**values)))(
        'export-csv',account,study_id=study_id)
    digest=exported.get('csv_sha256','')
    if not isinstance(digest,str) or re.fullmatch(r'[0-9a-f]{64}',digest) is None:
        raise RuntimeError('CSV_EXPORT_HASH_REQUIRED')
    try:
        content=base64.b64decode(exported['csv_base64'],validate=True)
        header=content.decode('utf-8').splitlines()[0]
    except (KeyError,ValueError,UnicodeError,IndexError):
        raise RuntimeError('CSV_EXPORT_INVALID') from None
    if not content or len(content)>5*1024*1024 or header!=','.join(CSV_HEADERS):
        raise RuntimeError('CSV_EXPORT_INVALID')
    if hashlib.sha256(content).hexdigest()!=digest:
        raise RuntimeError('CSV_EXPORT_HASH_MISMATCH')
    # O_EXCL evita incluso la carrera entre comprobación y creación. No se
    # sobrescribe ningún archivo; los errores no incluyen rutas ni contenido.
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0)
    try:
        descriptor=os.open(path,flags,0o600)
    except FileExistsError:
        raise RuntimeError('CSV_OUTPUT_EXISTS') from None
    except OSError:
        raise RuntimeError('CSV_OUTPUT_NOT_WRITABLE') from None
    try:
        with os.fdopen(descriptor,'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        # El archivo creado por esta llamada no es una exportación completa.
        path.unlink(missing_ok=True)
        raise RuntimeError('CSV_EXPORT_WRITE_FAILED') from None
    return {'study_id':study_id,'period_id':exported['period_id'],
        'file_name':path.name,'csv_sha256':digest,'bytes_written':len(content)}


def internal(command,account,*,target=None,**values):
    if target is None:
        raise RuntimeError('EXPLICIT_TARGET_REQUIRED')
    target.assert_identity()
    return target.api_command('app.synthetic_cli',command,{**account,**values})


def multipart(client,period_id,content,csrf):
    boundary='study-'+uuid4().hex
    data=(f'--{boundary}\r\nContent-Disposition: form-data; name="period_id"\r\n\r\n{period_id}\r\n'
          f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic-study.csv"\r\nContent-Type: text/csv\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
    base=getattr(client,'base_url',None)
    if not base:
        raise RuntimeError('EXPLICIT_TARGET_REQUIRED')
    client.target.assert_identity()
    req=urllib.request.Request(base+'/api/v1/imports/preview',data=data,method='POST',
        headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-CSRF-Token':csrf})
    try:
        response=client.opener.open(req,timeout=30)
    except urllib.error.HTTPError as error:
        response=error
    return response.status,json.loads(response.read())


def authenticated(account,callback,*,target):
    target.assert_identity()
    client=SessionClient(target)
    csrf=None
    try:
        code,login=client.request('POST','/auth/login',account,{'Origin':target.web_url})
        if code!=200 or not isinstance(login,dict):
            raise RuntimeError('ADMIN_AUTHENTICATION_REQUIRED')
        csrf=login.get('csrf_token')
        if login.get('user',{}).get('role')!='ADMIN' or not csrf:
            raise RuntimeError('ADMIN_AUTHENTICATION_REQUIRED')
        target.assert_identity()
        return callback(client,csrf)
    finally:
        if csrf:
            code,_=client.request('POST','/auth/logout',headers={'X-CSRF-Token':csrf})
            if code!=204:
                raise RuntimeError('ADMIN_LOGOUT_FAILED')


def import_study(account,study_id,*,target):
    export=internal('export-csv',account,target=target,study_id=study_id)
    content=base64.b64decode(export['csv_base64'])
    def run(client,csrf):
        code,batch=multipart(client,export['period_id'],content,csrf)
        if code not in (200,201) or batch['status'] not in ('READY','COMMITTED'):
            raise RuntimeError(batch.get('code','IMPORT_PREVIEW_FAILED'))
        detail_code,detail=client.request('GET','/imports/'+batch['id'])
        if detail_code!=200 or detail['file_sha256']!=batch['file_sha256']:
            raise RuntimeError('IMPORT_DETAIL_FAILED')
        code,result=client.request('POST','/imports/'+batch['id']+'/commit',
            {'expected_preview_version':batch['preview_version']},{'X-CSRF-Token':csrf})
        if code!=200:
            raise RuntimeError(result.get('code','IMPORT_COMMIT_FAILED'))
        return {'preview':{'id':batch['id'],'status':batch['status'],'data_origin':batch['data_origin'],
                'total_rows':batch['total_rows'],'preview_version':batch['preview_version']},
            'detail_status':detail_code,'commit':result,'period_id':export['period_id']}
    return authenticated(account,run,target=target)


def run_predictions(account,period_id,as_of=None,*,target):
    def run(client,csrf):
        code,result=client.request('POST','/predictions/run',{'period_id':period_id,
            'as_of':as_of or datetime.now(UTC).isoformat()},{'X-CSRF-Token':csrf})
        if code!=200:
            raise RuntimeError(result.get('code','PREDICTION_RUN_FAILED'))
        return result
    return authenticated(account,run,target=target)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Estudio con datos sintéticos; REAL permanece bloqueado.')
    parser.add_argument('command',choices=['generate','import','compare','register','activate','run','status','export-csv'])
    parser.add_argument('--target',type=Path,required=True,help='Descriptor privado del destino identificado; sin fallback al activo')
    access=parser.add_mutually_exclusive_group(required=True)
    access.add_argument('--admin-credential',choices=['ADMIN'],help='Leer SOLO ADMIN de las cuentas locales S2.2')
    access.add_argument('--operator-profile',help='Perfil ADMIN registrado contra este destino en Windows')
    parser.add_argument('--study-id'); parser.add_argument('--model-id'); parser.add_argument('--period-id')
    parser.add_argument('--seed',type=int,default=1729); parser.add_argument('--students',type=int)
    parser.add_argument('--tutor-id'); parser.add_argument('--config',type=Path)
    parser.add_argument('--algorithm',choices=['DUMMY','RANDOM_FOREST','SVM','XGBOOST'])
    parser.add_argument('--as-of')
    parser.add_argument('--output',type=Path,help='CSV nuevo: ruta absoluta fuera de Git, directorio existente')
    args=parser.parse_args(argv)
    if args.command=='export-csv' and (not args.study_id or args.output is None):
        parser.error('export-csv requiere --study-id y --output')
    try:
        if args.command=='export-csv':
            export_destination(args.output)
        from runtime_target import Target
        target=Target.load(args.target)
        target.assert_identity()
        account=admin_account(target,admin_credential=args.admin_credential,operator_profile=args.operator_profile)
        if args.command=='generate':
            config=json.loads(args.config.read_text(encoding='utf-8')) if args.config else None
            result=internal('generate',account,target=target,seed=args.seed,student_count=args.students,tutor_id=args.tutor_id,config=config)
        elif args.command=='status':
            result=internal('status',account,target=target)
        elif args.command=='export-csv':
            result=export_csv(account,args.study_id,args.output,target=target)
        elif args.command=='import':
            if not args.study_id: parser.error('import requiere --study-id')
            result=import_study(account,args.study_id,target=target)
        elif args.command=='run':
            if not args.period_id: parser.error('run requiere --period-id')
            result=run_predictions(account,args.period_id,args.as_of,target=target)
        elif args.command=='activate':
            if not args.model_id: parser.error('activate requiere --model-id')
            result=internal('activate',account,target=target,model_id=args.model_id)
        else:
            if not args.study_id: parser.error('compare/register requiere --study-id')
            result=internal(args.command,account,target=target,study_id=args.study_id,algorithm=args.algorithm)
        print(json.dumps(result,ensure_ascii=True,indent=2,allow_nan=False))
    except (RuntimeError,OSError,ValueError) as error:
        code=str(error)
        if re.fullmatch(r'[A-Z0-9_]{1,100}',code) is None:
            code='SYNTHETIC_COMMAND_FAILED'
        print(json.dumps({'code':code})); return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
