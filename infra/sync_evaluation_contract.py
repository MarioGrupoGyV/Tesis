"""Proyectar al contrato el Bloque 1: evaluación individual de mediciones manuales (SYNTHETIC)."""
import os
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(APP_ENV='test',DATABASE_URL='postgresql+psycopg://unused:unused@localhost/contract_test',
    CSRF_SECRET='contract-generation-only-not-a-runtime-secret')
from app.main import app

AFFECTED={'StudentEvaluation'}
ERRORS={401:'Sesión requerida',403:'Rol, CSRF u Origin no autorizado',404:'Estudiante ajeno o inexistente',
        409:'Periodo bloqueado, modelo no disponible o conflicto de integridad (MODEL_NOT_AVAILABLE si no hay modelo activo)',
        422:'Sin medición, estudio no preparado o procesamiento institucional no habilitado (INSTITUTIONAL_PROCESSING_NOT_READY)',
        503:'Servicio no disponible'}


def main():
    path=ROOT/'docs/planning/Contrato_API.yaml'
    contract=yaml.safe_load(path.read_text(encoding='utf-8'))
    runtime=app.openapi()
    contract['info']['version']=runtime['info']['version']
    contract['info']['description']=('S6 y M1 conservados. Bloque 1: ADMIN evalúa la última medición de una matrícula SYNTHETIC '
        'con el modelo activo del estudio (simulación). REAL continúa bloqueado con INSTITUTIONAL_PROCESSING_NOT_READY.')
    for name,value in runtime['components']['schemas'].items():
        if name in AFFECTED:
            contract['components']['schemas'][name]=value
    # Prediction conserva sus reglas de probabilidades; solo cambia la fecha objetivo (null en MANUAL).
    prediction=contract['components']['schemas']['Prediction']
    nullable_date={'type':['string','null'],'format':'date'}
    prediction['properties']['target_date']=dict(nullable_date,description='Fecha objetivo observada (CSV). Null en mediciones MANUAL.')
    prediction['properties']['model_horizon_date']=dict(nullable_date,description='Solo MANUAL: corte (America/Lima) + horizonte del modelo; derivado, no es un dato observado.')
    prediction['required']=[name for name in prediction['required'] if name!='target_date']
    route='/students/{id}/evaluate'
    operation=runtime['paths']['/api/v1'+route]['post']
    operation['x-stage']='B1'
    operation['x-roles']=['ADMIN']
    operation['security']=[{'sessionCookie':[]}]
    for parameter in operation.get('parameters',[]):
        if parameter.get('name')=='X-CSRF-Token':
            parameter.update(required=True,schema={'type':'string'})
    for status,text in ERRORS.items():
        operation['responses'][str(status)]={'description':text,
            'content':{'application/json':{'schema':{'$ref':'#/components/schemas/Error'}}}}
    operation['description']=('Evalúa solo la última revisión de la medición de la matrícula con el modelo activo del estudio, '
        'persiste la predicción y sincroniza el seguimiento de esa predicción en una sola transacción. Idempotente por '
        'medición y modelo. El horizonte del modelo de una medición MANUAL se deriva y no se guarda como fecha objetivo.')
    contract['paths'].setdefault(route,{})['post']=operation
    path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
    print('Contrato B1',contract['info']['version'])


if __name__=='__main__':
    main()
