"""Proyectar al contrato el Bloque 3B-1: protocolo REAL (interruptor técnico de ADMIN)."""
import os
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(APP_ENV='test',DATABASE_URL='postgresql+psycopg://unused:unused@localhost/contract_test',
    CSRF_SECRET='contract-generation-only-not-a-runtime-secret')
from app.main import app
from app.schemas import protocol as schemas

NAMES={name for name,value in vars(schemas).items() if isinstance(value,type) and getattr(value,'__module__','')==schemas.__name__}
ROLES=['ADMIN']
ERRORS={401:'Sesión requerida',403:'Solo ADMIN; CSRF u Origin no autorizado',404:'Protocolo o periodo inexistente',
        409:'El periodo ya tiene un protocolo con otros parámetros',422:'Periodo no REAL, bimestres fuera del periodo o parámetros inválidos',
        503:'Servicio no disponible'}


def main():
    path=ROOT/'docs/planning/Contrato_API.yaml'
    contract=yaml.safe_load(path.read_text(encoding='utf-8'))
    runtime=app.openapi()
    contract['info']['version']=runtime['info']['version']
    contract['info']['description']=('S6, M1 y Bloques 1–2 conservados. Bloque 3B-1: protocolo REAL (crear, confirmar y revocar la autorización '
        'técnica de un ADMIN). No guarda consentimientos, documentos, autorizadores ni fechas de permiso y NO habilita operaciones: '
        'REAL continúa bloqueado con INSTITUTIONAL_PROCESSING_NOT_READY.')
    for name,value in runtime['components']['schemas'].items():
        if name in NAMES:
            contract['components']['schemas'][name]=value
    for raw,methods in runtime['paths'].items():
        route=raw.removeprefix('/api/v1')
        if not route.startswith('/processing-protocols'):
            continue
        for method,operation in methods.items():
            operation['x-stage']='B3B-1'
            operation['x-roles']=ROLES
            operation['security']=[{'sessionCookie':[]}]
            for parameter in operation.get('parameters',[]):
                if parameter.get('name')=='X-CSRF-Token':
                    parameter.update(required=True,schema={'type':'string'})
            for status,text in ERRORS.items():
                operation['responses'][str(status)]={'description':text,
                    'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}}
            operation['description']=('ADMIN con CSRF y Origin. Idempotente: repetir el mismo estado no cambia nada ni audita. Auditoría con actor '
                'e instante UTC y solo identificadores. En 3B-1 confirmar el protocolo NO desbloquea ninguna operación REAL.')
            contract['paths'].setdefault(route,{})[method]=operation
    if {'name':'protocols'} not in contract['tags']:
        contract['tags'].append({'name':'protocols'})
    path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
    print('Contrato B3B-1',contract['info']['version'])


if __name__=='__main__':
    main()
