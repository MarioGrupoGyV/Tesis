"""Revisión autorizada de cuatro rutas nuevas; conserva usuarios y registros activos."""
import json
from uuid import uuid4
from review_accounts import credentials
from review_endpoints import Client, BASE, MISSING, probe, EVIDENCE
from runtime_snapshot import ROOT, SCHOOL, snapshot, school_unchanged


def main():
    before=snapshot()
    paths=['/models',f'/models/{MISSING}',f'/predictions/{MISSING}']
    client=Client()
    for path in paths: probe(client,'ANONYMOUS','GET',path,401,label='Sin sesión')
    probe(client,'ANONYMOUS','POST','/predictions/run',401,label='Sin sesión')
    for role,account in credentials().items():
        client=Client()
        login=probe(client,role,'POST','/auth/login',200,body=account,headers={'Origin':BASE},label='Acceso existente')
        csrf={'X-CSRF-Token':login['csrf_token']}
        for path in paths:
            expected=(200 if path=='/models' else 404) if role=='ADMIN' else (404 if path.startswith('/predictions') and role!='RESEARCHER' else 403)
            result=probe(client,role,'GET',path,expected,label='Permiso y recurso inexistente')
            if path=='/models' and role=='ADMIN':
                assert result['items']==[] and result['total']==0
        body={'period_id':MISSING,'as_of':'2026-10-04T05:00:00Z'}
        for headers in (None,{'X-CSRF-Token':'invalid'}):
            probe(client,role,'POST','/predictions/run',403,body=body,headers=headers,label='CSRF ausente/incorrecto o rol')
        probe(client,role,'POST','/predictions/run',422 if role=='ADMIN' else 403,body=body,headers=csrf,
              label='Bloqueo institucional antes de consultar periodo',
              code='INSTITUTIONAL_PROCESSING_NOT_READY' if role=='ADMIN' else 'FORBIDDEN')
        old=list(client.jar)
        probe(client,role,'POST','/auth/logout',204,headers=csrf,label='Revocación')
        for cookie in old: client.jar.set_cookie(cookie)
        probe(client,role,'GET','/models',401,label='Sesión revocada')
    after=snapshot()
    assert school_unchanged(before,after) and before['users']==after['users']
    assert before['fingerprints']['app_users']==after['fingerprints']['app_users']
    report={'status':'COMPROBADO','contract_version':'0.3.0','environment':'active_local',
        'school_and_artifacts_unchanged':True,'accounts_and_password_hashes_unchanged':True,
        'school_counts':{t:after['counts'][t] for t in SCHOOL},'cases':EVIDENCE}
    (ROOT/'tests/evidence/s3-active-endpoints.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'COMPROBADO: {len(EVIDENCE)} peticiones; sin modelos, predicciones ni registros escolares nuevos.')


if __name__=='__main__':
    main()
