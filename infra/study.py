"""PowerShell: estudio explícito con credencial Windows ADMIN, nunca contraseña en args."""
import argparse
import base64
from datetime import UTC,datetime
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
from uuid import uuid4
from review_accounts import credentials
from review_endpoints import Client,BASE

ROOT=Path(__file__).resolve().parents[1]


def internal(command,account,**values):
    result=subprocess.run(['docker','compose','exec','-T','api','python','-m','app.synthetic_cli',command],
        cwd=ROOT,input=json.dumps({**account,**values}),text=True,encoding='utf-8',capture_output=True)
    try:
        body=json.loads(result.stdout)
    except ValueError:
        raise RuntimeError('El comando privado no devolvió un resultado sanitizado.') from None
    if result.returncode:
        raise RuntimeError(body.get('code','SYNTHETIC_COMMAND_FAILED'))
    return body


def multipart(client,period_id,content,csrf):
    boundary='study-'+uuid4().hex
    data=(f'--{boundary}\r\nContent-Disposition: form-data; name="period_id"\r\n\r\n{period_id}\r\n'
          f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic-study.csv"\r\nContent-Type: text/csv\r\n\r\n').encode()+content+f'\r\n--{boundary}--\r\n'.encode()
    req=urllib.request.Request(BASE+'/api/v1/imports/preview',data=data,method='POST',
        headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-CSRF-Token':csrf})
    try:
        response=client.opener.open(req,timeout=30)
    except urllib.error.HTTPError as error:
        response=error
    return response.status,json.loads(response.read())


def authenticated(account,callback):
    client=Client()
    code,login=client.request('POST','/auth/login',account,{'Origin':BASE})
    if code!=200 or login['user']['role']!='ADMIN':
        raise RuntimeError('ADMIN_AUTHENTICATION_REQUIRED')
    csrf=login['csrf_token']
    try:
        return callback(client,csrf)
    finally:
        client.request('POST','/auth/logout',headers={'X-CSRF-Token':csrf})


def import_study(account,study_id):
    export=internal('export-csv',account,study_id=study_id)
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
    return authenticated(account,run)


def run_predictions(account,period_id,as_of=None):
    def run(client,csrf):
        code,result=client.request('POST','/predictions/run',{'period_id':period_id,
            'as_of':as_of or datetime.now(UTC).isoformat()},{'X-CSRF-Token':csrf})
        if code!=200:
            raise RuntimeError(result.get('code','PREDICTION_RUN_FAILED'))
        return result
    return authenticated(account,run)


def main():
    parser=argparse.ArgumentParser(description='Estudio con datos sintéticos; REAL permanece bloqueado.')
    parser.add_argument('command',choices=['generate','import','compare','register','activate','run','status'])
    parser.add_argument('--admin-credential',required=True,choices=['ADMIN'],help='ADMIN explícito de las cuentas locales S2.2')
    parser.add_argument('--study-id'); parser.add_argument('--model-id'); parser.add_argument('--period-id')
    parser.add_argument('--seed',type=int,default=1729); parser.add_argument('--students',type=int)
    parser.add_argument('--tutor-id'); parser.add_argument('--config',type=Path)
    parser.add_argument('--algorithm',choices=['DUMMY','RANDOM_FOREST','SVM','XGBOOST'])
    parser.add_argument('--as-of')
    args=parser.parse_args()
    account=credentials()[args.admin_credential]
    try:
        if args.command=='generate':
            config=json.loads(args.config.read_text(encoding='utf-8')) if args.config else None
            result=internal('generate',account,seed=args.seed,student_count=args.students,tutor_id=args.tutor_id,config=config)
        elif args.command=='status':
            result=internal('status',account)
        elif args.command=='import':
            if not args.study_id: parser.error('import requiere --study-id')
            result=import_study(account,args.study_id)
        elif args.command=='run':
            if not args.period_id: parser.error('run requiere --period-id')
            result=run_predictions(account,args.period_id,args.as_of)
        elif args.command=='activate':
            if not args.model_id: parser.error('activate requiere --model-id')
            result=internal('activate',account,model_id=args.model_id)
        else:
            if not args.study_id: parser.error('compare/register requiere --study-id')
            result=internal(args.command,account,study_id=args.study_id,algorithm=args.algorithm)
        print(json.dumps(result,ensure_ascii=True,indent=2,allow_nan=False))
    except RuntimeError as error:
        print(json.dumps({'code':str(error)})); return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
