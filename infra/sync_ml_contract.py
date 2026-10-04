"""Sincroniza únicamente el contrato público de las cuatro operaciones S3."""
import json
from pathlib import Path
import subprocess
import yaml

ROOT=Path(__file__).resolve().parents[1]
code="""import sys,json
sys.path.insert(0,'/workspace/backend')
from app.schemas.ml import Model,ModelPage,PredictionRunInput,PredictionRunResult
print(json.dumps({c.__name__:c.model_json_schema() for c in (Model,ModelPage,PredictionRunInput,PredictionRunResult)}))
"""
generated=json.loads(subprocess.check_output(['docker','run','--rm','--network','none',
    'riesgo-escolar-tests-tester','python','-c',code],cwd=ROOT,text=True,encoding='utf-8'))
path=ROOT/'docs/planning/Contrato_API.yaml'
contract=yaml.safe_load(path.read_text(encoding='utf-8'))
contract['info']['version']='0.3.0'
contract['info']['description']='S3: infraestructura predictiva comprobable aisladamente. Importación, entrenamiento, inferencia institucional y activación bloqueados. Solo operaciones implementadas.'
if {'name':'ml'} not in contract['tags']: contract['tags'].append({'name':'ml'})
for name,schema in generated.items():
    definitions=schema.pop('$defs',{})
    for key,value in {**definitions,name:schema}.items():
        value=json.loads(json.dumps(value).replace('#/$defs/','#/components/schemas/'))
        contract['components']['schemas'][key]=value
def response(schema,description):
    return {'description':description,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/'+schema}}}}
errors={str(status):response('Error',description) for status,description in {
    401:'SESSION_INVALID: sesión requerida o revocada.',403:'FORBIDDEN o CSRF_INVALID; permisos comprobados en servidor.',
    404:'Recurso inexistente o no accesible en la sección; no revela casos ajenos.',
    409:'PERIOD_LOCKED, MODEL_NOT_AVAILABLE, MODEL_INCOMPATIBLE, PREDICTION_CONFLICT o INTEGRITY_CONFLICT. Reutilización snapshot/model devuelve resultado existente, no error.',
    422:'Validación, NOT_ELIGIBLE o INSTITUTIONAL_PROCESSING_NOT_READY; sin escrituras académicas.',
    503:'Base no disponible: Error sanitizado, sin consultas, parámetros ni secretos; nunca para integridad.',
    500:'Error interno inesperado sanitizado.'}.items()}
id_parameter={'name':'id','in':'path','required':True,'schema':{'type':'string','format':'uuid'}}
page_parameters=[{'name':name,'in':'query','schema':{'type':'integer','minimum':1,'maximum':maximum,'default':default}}
                 for name,maximum,default in [('page',10000,1),('page_size',100,25)]]
for path_name,method,operation,schema,roles,parameters,description in [
    ('/models','get','listModels','ModelPage',['ADMIN'],page_parameters,'Modelos paginados; orden created_at descendente e id ascendente. Lista vacía en activo. Sin hashes, rutas, particiones ni métricas privadas.'),
    ('/models/{id}','get','modelDetail','Model',['ADMIN'],[id_parameter],'Metadatos públicos sanitizados. No activa ni descarga modelos.'),
    ('/predictions/{id}','get','predictionDetail','Prediction',['ADMIN','TUTOR','DIRECTOR'],[id_parameter],'TUTOR solo su sección. Inexistente o ajena devuelve 404. No sustituye riesgo faltante por LOW.'),
    ('/predictions/run','post','runPredictions','PredictionRunResult',['ADMIN'],[{'name':'X-CSRF-Token','in':'header','required':True,'schema':{'type':'string'}}],
     'Orden: sesión, rol, CSRF, protocolo, cuerpo, periodo/modelo. En S3 devuelve bloqueo 422 incluso con cuerpo inválido después de CSRF; nunca procesa información institucional. Núcleo aislado: última revisión incorporada/disponible hasta as_of, abstención sin fila, reutilización snapshot/model y auditoría atómica. Modelo no disponible: 409 posterior al protocolo. Sin entrenamiento HTTP ni alertas.')]:
    spec={'operationId':operation,'summary':operation,'tags':['ml'],'x-stage':'S3','x-roles':roles,
          'description':description,'parameters':parameters,'responses':{'200':response(schema,'Resultado de la operación implementada; ejecución institucional bloqueada en S3.'),**errors}}
    if method=='post':
        spec['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/PredictionRunInput'}}}}
    contract['paths'][path_name]={method:spec}
path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
print('OpenAPI 0.3.0: 18 operaciones; solo cuatro rutas nuevas.')
