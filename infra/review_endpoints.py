"""Revisión activa S2.2: llamadas reales sanitizadas, sin registros escolares."""
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.request
from uuid import uuid4
from review_accounts import credentials
from runtime_snapshot import snapshot, school_unchanged, SCHOOL

ROOT=Path(__file__).resolve().parents[1]
BASE='http://localhost:15173'
MISSING='00000000-0000-4000-8000-000000000222'
EVIDENCE=[]

class Client:
    def __init__(self):
        self.jar=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(self.jar))
    def request(self,method,path,body=None,headers=None):
        data=None if body is None else json.dumps(body).encode()
        headers={**({'Content-Type':'application/json'} if data is not None else {}),**(headers or {})}
        request=urllib.request.Request(BASE+'/api/v1'+path,data=data,headers=headers,method=method)
        try:
            response=self.opener.open(request,timeout=15)
        except urllib.error.HTTPError as error:
            response=error
        content=response.read()
        return response.status, json.loads(content) if content else None

def sanitized(value):
    if isinstance(value,dict):
        return {key:('[REDACTED]' if key in ('password','csrf_token') else sanitized(item)) for key,item in value.items()}
    if isinstance(value,list):
        return [sanitized(item) for item in value]
    return value

def probe(client,role,method,path,expected,*,body=None,headers=None,label='',code=None):
    status,response=client.request(method,path,body,headers)
    EVIDENCE.append({'role':role,'method':method,'path':'/api/v1'+path,'case':label,
        'request':{'body':sanitized(body),'headers':{k:('[PRESENT]' if k.lower() in ('x-csrf-token','cookie') else v) for k,v in (headers or {}).items()}},
        'expected_status':expected,'status':status,'response':sanitized(response),
        'result':'COMPROBADO' if status==expected and (not code or response.get('code')==code) else 'FALLIDO'})
    assert status==expected, f'{role} {method} {path}: esperado {expected}, recibido {status}'
    if code: assert response.get('code')==code, f'Código inesperado: {label}'
    return response

def main():
    before=snapshot()
    accounts=credentials()
    anonymous=Client()
    read_routes=['/auth/me','/auth/csrf','/periods',f'/sections?period_id={MISSING}',
        f'/students?period_id={MISSING}',f'/students/{MISSING}?period_id={MISSING}',
        f'/students/{MISSING}/timeline?period_id={MISSING}',f'/imports/{MISSING}']
    try:
        for endpoint in ('/health/live','/health/ready'):
            probe(anonymous,'ANONYMOUS','GET',endpoint,200,label='Salud pública')
        for path in read_routes:
            probe(anonymous,'ANONYMOUS','GET',path,401,label='Sin sesión',code='SESSION_INVALID')
        for path,body in [('/auth/logout',None),('/imports/preview',None),(f'/imports/{MISSING}/commit',{'expected_preview_version':1})]:
            probe(anonymous,'ANONYMOUS','POST',path,401,body=body,label='Escritura sin sesión')
        for role,account in accounts.items():
            client=Client()
            probe(client,role,'POST','/auth/login',403,body=account,label='Origin ausente',code='ORIGIN_NOT_ALLOWED')
            probe(client,role,'POST','/auth/login',403,body=account,headers={'Origin':'http://untrusted.example.com'},label='Origin ajeno',code='ORIGIN_NOT_ALLOWED')
            login=probe(client,role,'POST','/auth/login',200,body=account,headers={'Origin':BASE},label='Credenciales privadas autorizadas')
            assert login['user']['role']==role
            csrf={'X-CSRF-Token':login['csrf_token']}
            for endpoint in ('/health/live','/health/ready','/auth/me','/auth/csrf'):
                probe(client,role,'GET',endpoint,200,label='Sesión vigente')
            restricted=role=='RESEARCHER'
            probe(client,role,'GET','/periods',403 if restricted else 200,label='Contexto según rol')
            for path in read_routes[3:7]:
                probe(client,role,'GET',path,403 if restricted else 404,label='UUID inexistente; autorización antes de recurso')
            probe(client,role,'GET',f'/imports/{MISSING}',404 if role=='ADMIN' else 403,label='Detalle de lote inexistente')
            for path in ('/sections','/students'):
                probe(client,role,'GET',path,422,label='Periodo obligatorio')
            for path,body in [('/imports/preview',None),(f'/imports/{MISSING}/commit',{'expected_preview_version':1})]:
                for token,label in [(None,'CSRF ausente'),({'X-CSRF-Token':'incorrecto'},'CSRF incorrecto')]:
                    probe(client,role,'POST',path,403,body=body,headers=token,label=label)
                probe(client,role,'POST',path,422 if role=='ADMIN' else 403,body=body,headers=csrf,
                      label='Bloqueo institucional o rol restringido',code='INSTITUTIONAL_PROCESSING_NOT_READY' if role=='ADMIN' else 'FORBIDDEN')
            probe(client,role,'POST','/auth/logout',403,label='Logout sin CSRF',code='CSRF_INVALID')
            probe(client,role,'POST','/auth/logout',403,headers={'X-CSRF-Token':'incorrecto'},label='Logout CSRF incorrecto')
            old=list(client.jar)
            probe(client,role,'POST','/auth/logout',204,headers=csrf,label='Logout válido')
            for cookie in old: client.jar.set_cookie(cookie)
            for path in ('/auth/me','/auth/csrf','/periods'):
                probe(client,role,'GET',path,401,label='Cookie anterior revocada',code='SESSION_INVALID')
        bad={**accounts['ADMIN'],'password':'incorrect-password-'+uuid4().hex}
        probe(Client(),'ANONYMOUS','POST','/auth/login',401,body=bad,headers={'Origin':BASE},label='Credenciales incorrectas',code='INVALID_CREDENTIALS')
    finally:
        after=snapshot()
        report={'status':'COMPROBADO' if all(r['result']=='COMPROBADO' for r in EVIDENCE) and school_unchanged(before,after) else 'FALLIDO',
            'contract_version':'0.2.0','environment':'active_local','school_and_files_unchanged':school_unchanged(before,after),
            'school_counts':{t:after['counts'][t] for t in SCHOOL},'cases':EVIDENCE}
        (ROOT/'tests/evidence/s2-2-endpoints.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert report['school_and_files_unchanged']
    print(f"COMPROBADO: {len(EVIDENCE)} peticiones sanitizadas; sin cambios escolares ni de archivos.")

if __name__=='__main__':
    main()
