"""Proyectar rutas/esquemas efectivos M1 conservando contratos ML/CSV."""
import os
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(APP_ENV='test',DATABASE_URL='postgresql+psycopg://unused:unused@localhost/contract_test',
    CSRF_SECRET='contract-generation-only-not-a-runtime-secret')
from app.main import app
from app.schemas import manual

AFFECTED={'Period','Section','Student','StudentPage','Snapshot','StudentDetail','MeasurementPage'} | {
    name for name,value in vars(manual).items() if isinstance(value,type) and getattr(value,'__module__','')==manual.__name__}


def main():
    path=ROOT/'docs/planning/Contrato_API.yaml'
    contract=yaml.safe_load(path.read_text(encoding='utf-8'))
    runtime=app.openapi()
    contract['info']['version']=runtime['info']['version']
    contract['info']['description']='S6 conservado. M1 registro académico manual REAL/SYNTHETIC local. Inferencia e importación REAL bloqueadas; sin integración predictiva de mediciones manuales.'
    # Las respuestas existentes son proyecciones efectivas compartidas por M1.
    for name,value in runtime['components']['schemas'].items():
        if name in AFFECTED:
            contract['components']['schemas'][name]=value
    for raw_path,methods in runtime['paths'].items():
        route=raw_path.removeprefix('/api/v1')
        for method,operation in methods.items():
            if 'manual' not in operation.get('tags',[]) and route not in ('/students','/students/{id}','/students/{id}/timeline','/periods','/sections'):
                continue
            operation['x-stage']='M1'
            operation['x-roles']=['ADMIN'] if method in ('post','patch') and not route.endswith('/measurements') or route in ('/student-identities','/catalogs/tutors') else ['ADMIN','TUTOR'] if method=='post' else ['ADMIN','TUTOR','DIRECTOR']
            operation['security']=[{'sessionCookie':[]}]
            for parameter in operation.get('parameters',[]):
                if parameter.get('name')=='X-CSRF-Token':
                    parameter.update(required=True,schema={'type':'string'})
            for status in (401,403,404,409,422,503):
                operation['responses'][str(status)]={'description':{401:'Sesión requerida',403:'Rol, CSRF u Origin no autorizado',404:'Recurso ajeno o inexistente',409:'Duplicado, versión, cierre o integridad',422:'Campos, escalas, origen o fechas inválidos',503:'Servicio no disponible'}[status],
                    'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}}
            operation['description']='M1: permisos y contexto verificados en servidor. Escrituras atómicas con auditoría e idempotencia por actor; expected_version/expected_revision en cambios. Sin predicción.'
            contract['paths'].setdefault(route,{})[method]=operation
    if {'name':'manual'} not in contract['tags']:
        contract['tags'].append({'name':'manual'})
    path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
    print('Contrato M1',contract['info']['version'])


if __name__=='__main__':
    main()
