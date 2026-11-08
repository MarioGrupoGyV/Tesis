"""Proyectar al contrato el Bloque 10 (ADR 015): consulta de solo lectura del conjunto real."""
import os
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(APP_ENV='test',DATABASE_URL='postgresql+psycopg://unused:unused@localhost/contract_test',
    CSRF_SECRET='contract-generation-only-not-a-runtime-secret')
from app.main import app
from app.schemas import real_set as schemas

NAMES={name for name,value in vars(schemas).items() if isinstance(value,type) and getattr(value,'__module__','')==schemas.__name__}
ROLES=['ADMIN','TUTOR','DIRECTOR']
ERRORS={401:'Sesión requerida',403:'Rol sin acceso',404:'Periodo no REAL, ajeno o inexistente; sección ajena',
        422:'Origen no admitido',503:'Servicio no disponible'}


def main():
    path=ROOT/'docs/planning/Contrato_API.yaml'
    contract=yaml.safe_load(path.read_text(encoding='utf-8'))
    runtime=app.openapi()
    contract['info']['version']=runtime['info']['version']
    for name,value in runtime['components']['schemas'].items():
        if name in NAMES:
            contract['components']['schemas'][name]=value
    for raw,methods in runtime['paths'].items():
        route=raw.removeprefix('/api/v1')
        if not route.startswith('/real-set'):
            continue
        for method,operation in methods.items():
            operation['x-stage']='B10'
            operation['x-roles']=ROLES
            operation['security']=[{'sessionCookie':[]}]
            for status,text in ERRORS.items():
                operation['responses'][str(status)]={'description':text,
                    'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}}
            operation['description']=('Conjunto real de solo lectura: por estudiante y bimestre, la revisión de mitad de bimestre que '
                'usó la referencia RIESGO_V2, el nivel del modelo REAL activo y el de referencia; is_locked indica si el periodo está '
                'cerrado. TUTOR solo ve sus secciones. Solo códigos; nunca nombres. No escribe ni evalúa.')
            contract['paths'].setdefault(route,{})[method]=operation
    if {'name':'real-set'} not in contract['tags']:
        contract['tags'].append({'name':'real-set'})
    path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
    print('Contrato B10',contract['info']['version'])


if __name__=='__main__':
    main()
