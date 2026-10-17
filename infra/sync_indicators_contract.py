"""Proyectar al contrato el Bloque 2: indicadores de la tesis (solo lectura, SYNTHETIC)."""
import os
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(APP_ENV='test',DATABASE_URL='postgresql+psycopg://unused:unused@localhost/contract_test',
    CSRF_SECRET='contract-generation-only-not-a-runtime-secret')
from app.main import app
from app.schemas import indicators as schemas

NAMES={name for name,value in vars(schemas).items() if isinstance(value,type) and getattr(value,'__module__','')==schemas.__name__}
ROLES=['ADMIN','TUTOR','DIRECTOR','RESEARCHER']
ERRORS={401:'Sesión requerida',403:'Rol sin acceso',404:'Periodo o sección ajena o inexistente',
        422:'as_of futuro o procesamiento institucional no habilitado (INSTITUTIONAL_PROCESSING_NOT_READY)',
        503:'Servicio no disponible'}


def main():
    path=ROOT/'docs/planning/Contrato_API.yaml'
    contract=yaml.safe_load(path.read_text(encoding='utf-8'))
    runtime=app.openapi()
    contract['info']['version']=runtime['info']['version']
    contract['info']['description']=('S6, M1 y Bloque 1 conservados. Bloque 2: indicadores de la tesis (PRV, CRA, PDER, NIA, '
        'intervención oportuna, métricas del modelo, rendimiento) por periodo y sección; solo lectura, SYNTHETIC. '
        'REAL continúa bloqueado con INSTITUTIONAL_PROCESSING_NOT_READY.')
    for name,value in runtime['components']['schemas'].items():
        if name in NAMES:
            contract['components']['schemas'][name]=value
    for raw,methods in runtime['paths'].items():
        route=raw.removeprefix('/api/v1')
        if not route.startswith('/indicators'):
            continue
        for method,operation in methods.items():
            operation['x-stage']='B2'
            operation['x-roles']=ROLES
            operation['security']=[{'sessionCookie':[]}]
            for status,text in ERRORS.items():
                operation['responses'][str(status)]={'description':text,
                    'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}}
            operation['description']=('Cálculo con corte as_of explícito (reproducible). TUTOR solo ve sus secciones; sin riesgo de '
                'referencia almacenado el indicador es null con motivo REFERENCE_NOT_AVAILABLE. Solo códigos anónimos.')
            contract['paths'].setdefault(route,{})[method]=operation
    if {'name':'indicators'} not in contract['tags']:
        contract['tags'].append({'name':'indicators'})
    path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
    print('Contrato B2',contract['info']['version'])


if __name__=='__main__':
    main()
