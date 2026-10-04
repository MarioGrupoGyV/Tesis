"""Recorrido real S3.1; cuatro roles, evidencia sanitizada y sin contraseñas/etiquetas."""
import argparse
from datetime import UTC,datetime
import base64
import json
import os
from pathlib import Path
from uuid import uuid4
from review_accounts import credentials
from review_endpoints import Client,BASE,sanitized
from runtime_snapshot import snapshot,school_unchanged
from study import internal,multipart

ROOT=Path(__file__).resolve().parents[1]


def public(value):
    value=sanitized(value)
    if isinstance(value,dict):
        return {k:'[SYNTHETIC_CODE]' if k=='anon_code' else public(v) for k,v in value.items()}
    if isinstance(value,list): return [public(v) for v in value]
    return value


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--admin-credential',required=True,choices=['ADMIN'])
    parser.add_argument('--tutor-id',required=True)
    args=parser.parse_args()
    accounts=credentials()
    before=snapshot()
    cases=[]
    report={'status':'FALLIDO','contract_version':'0.4.0','scope':'SYNTHETIC_STUDY','cases':cases}
    prefix=os.environ.get('STUDY_REPORT_PREFIX','s3-1-active')
    if not prefix.replace('-','').isalnum(): raise ValueError('Prefijo inválido')
    def probe(client,role,method,path,expected,body=None,headers=None):
        code,response=client.request(method,path,body,headers)
        cases.append({'role':role,'method':method,'path':'/api/v1'+path,'expected_status':expected,
            'status':code,'response':public(response),'result':'COMPROBADO' if code==expected else 'FALLIDO'})
        assert code==expected, f'{role} {method} {path}: {code}, esperado {expected}'
        return response
    clients=[]
    try:
        anonymous=Client()
        probe(anonymous,'ANONYMOUS','GET','/processing/status',401)
        admin=accounts['ADMIN']
        generated=internal('generate',admin,seed=1729,tutor_id=args.tutor_id)
        report['generation']=generated
        study_id,period_id=generated['study_id'],generated['period_id']
        # Un acceso ADMIN conserva sesión durante todas las operaciones HTTP del recorrido.
        client=Client()
        login=probe(client,'ADMIN','POST','/auth/login',200,admin,{'Origin':BASE})
        csrf={'X-CSRF-Token':login['csrf_token']}
        clients.append((client,csrf))
        probe(client,'ADMIN','GET','/processing/status',200)
        exported=internal('export-csv',admin,study_id=study_id)
        code,batch=multipart(client,period_id,base64.b64decode(exported['csv_base64']),login['csrf_token'])
        cases.append({'role':'ADMIN','method':'POST','path':'/api/v1/imports/preview','expected_status':201 if code==201 else 200,
            'status':code,'response':public(batch),'result':'COMPROBADO' if code in (200,201) else 'FALLIDO'})
        assert code in (200,201) and batch['status'] in ('READY','COMMITTED')
        preview_snapshot=snapshot()
        if not generated['reused']:
            assert all(before['counts'][t]==preview_snapshot['counts'][t] for t in ('students','enrollments','academic_snapshots'))
        probe(client,'ADMIN','GET','/imports/'+batch['id'],200)
        committed=probe(client,'ADMIN','POST','/imports/'+batch['id']+'/commit',200,
            {'expected_preview_version':batch['preview_version']},csrf)
        report['commit']=committed
        report['comparison']=internal('compare',admin,study_id=study_id)
        model=internal('register',admin,study_id=study_id)
        report['registration']=model
        report['activation']=internal('activate',admin,model_id=model['model_id'])
        probe(client,'ADMIN','GET','/models',200)
        probe(client,'ADMIN','GET','/models/'+model['model_id'],200)
        probe(client,'ADMIN','POST','/predictions/run',403,{'period_id':period_id,'as_of':datetime.now(UTC).isoformat()})
        as_of=datetime.now(UTC).isoformat()
        payload={'period_id':period_id,'as_of':as_of}
        first=probe(client,'ADMIN','POST','/predictions/run',200,payload,csrf)
        repeated=probe(client,'ADMIN','POST','/predictions/run',200,payload,csrf)
        assert repeated['created']==0 and repeated['reused']==first['created']+first['reused']
        report['inference']={'as_of':as_of,'selected':first['selected'],'created':first['created'],
            'reused':first['reused'],'abstentions':len(first['abstentions']),'repeat_created':repeated['created'],
            'repeat_reused':repeated['reused']}
        all_students=probe(client,'ADMIN','GET',f'/students?period_id={period_id}&page_size=100',200)
        records=all_students['items']
        evaluated=next(r for r in records if r['evaluation_status']=='EVALUATED')
        insufficient=next(r for r in records if r['evaluation_status']=='INSUFFICIENT_DATA')
        assert insufficient['risk_level'] is None
        detail=probe(client,'ADMIN','GET',f"/students/{evaluated['id']}?period_id={period_id}",200)
        prediction=detail['latest_prediction']
        assert prediction and not prediction['probabilities_calibrated']
        assert all(prediction[n] is None for n in ('probability_low','probability_medium','probability_high'))
        probe(client,'ADMIN','GET',f"/students/{evaluated['id']}/timeline?period_id={period_id}",200)
        probe(client,'ADMIN','GET','/processing/status',200)
        after_walk=snapshot()
        for role in ('TUTOR','DIRECTOR','RESEARCHER'):
            other=Client()
            login=probe(other,role,'POST','/auth/login',200,accounts[role],{'Origin':BASE})
            other_csrf={'X-CSRF-Token':login['csrf_token']}
            clients.append((other,other_csrf))
            state=probe(other,role,'GET','/processing/status',200)
            assert state['institutional_ready'] is False
            probe(other,role,'GET','/models',403)
            probe(other,role,'POST','/predictions/run',403,payload,other_csrf)
            restricted=role=='RESEARCHER'
            listing=probe(other,role,'GET',f'/students?period_id={period_id}&page_size=100',403 if restricted else 200)
            probe(other,role,'GET','/periods',403 if restricted else 200)
            if role=='TUTOR':
                own_ids={r['id'] for r in listing['items']}
                assert 0<len(own_ids)<all_students['total']
                foreign=next(r for r in records if r['id'] not in own_ids and r['evaluation_status']=='EVALUATED')
                foreign_detail=client.request('GET',f"/students/{foreign['id']}?period_id={period_id}")[1]
                foreign_prediction=foreign_detail['latest_prediction']['id']
                probe(other,role,'GET',f'/predictions/{foreign_prediction}',404)
                probe(other,role,'GET',f'/predictions/{uuid4()}',404)
                own=next(r for r in listing['items'] if r['evaluation_status']=='EVALUATED')
                own_detail=probe(other,role,'GET',f"/students/{own['id']}?period_id={period_id}",200)
                probe(other,role,'GET','/predictions/'+own_detail['latest_prediction']['id'],200)
            elif role=='DIRECTOR':
                assert listing['total']==60
                probe(other,role,'GET','/predictions/'+prediction['id'],200)
            else:
                assert all(not op['available'] for op in state['operations'].values())
                probe(other,role,'GET','/predictions/'+prediction['id'],403)
                probe(other,role,'GET','/periods',403,headers={'X-Role':'ADMIN'})
        after_review=snapshot()
        assert school_unchanged(after_walk,after_review)
        assert before['fingerprints']['app_users']==after_review['fingerprints']['app_users']
        report['users_password_hashes_preserved']=True
        report['counts']=after_review['counts']
        report['status']='COMPROBADO'
    finally:
        for client,csrf in clients:
            old=list(client.jar)
            probe(client,'AUTHENTICATED','POST','/auth/logout',204,headers=csrf)
            for cookie in old: client.jar.set_cookie(cookie)
            probe(client,'REVOKED','GET','/auth/me',401)
        (ROOT/f'tests/evidence/{prefix}-endpoints.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'requests':len(cases),'scope':'SYNTHETIC_STUDY',
        'inference':report.get('inference'),'comparison_selected':report.get('comparison',{}).get('selected_algorithm')},indent=2))


if __name__=='__main__': main()
