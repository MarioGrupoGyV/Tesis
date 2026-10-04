"""Contrato S3.1: cambio de origen y única ruta nueva efectiva."""
import json
from pathlib import Path
import subprocess
import yaml

ROOT=Path(__file__).resolve().parents[1]
code="""import json
from app.schemas.processing import ProcessingStatus
from app.schemas.ml import Model
print(json.dumps({c.__name__:c.model_json_schema(mode='serialization') for c in (ProcessingStatus,Model)}))
"""


def flatten(value):
    if isinstance(value,list): return [flatten(v) for v in value]
    if not isinstance(value,dict): return value
    value={k:flatten(v) for k,v in value.items()}
    choices=value.get('anyOf',[])
    if len(choices)==2 and any(v.get('type')=='null' for v in choices):
        base=next(v for v in choices if v.get('type')!='null')
        if 'type' in base:
            value={**base,**{k:v for k,v in value.items() if k!='anyOf'},'type':[base['type'],'null']}
    return value


def main():
    generated=json.loads(subprocess.check_output(['docker','run','--rm','--network','none','riesgo-escolar-api','python','-c',code],
        cwd=ROOT,text=True,encoding='utf-8'))
    path=ROOT/'docs/planning/Contrato_API.yaml'
    contract=yaml.safe_load(path.read_text(encoding='utf-8'))
    contract['info']['version']='0.4.0'
    contract['info']['description']='S3.1: Estudio con datos sintéticos explícitos. REAL bloqueado; sin entrenamiento/activación HTTP ni pantallas S4–S6. Cambio incompatible de origen público REAL/SYNTHETIC.'
    def origins(value):
        if isinstance(value,dict):
            if value.get('const')=='REAL':
                value.pop('const'); value['enum']=['REAL','SYNTHETIC']
            if value.get('enum')==['REAL']: value['enum']=['REAL','SYNTHETIC']
            for v in value.values(): origins(v)
        elif isinstance(value,list):
            for v in value: origins(v)
    origins(contract['components']['schemas'])
    for name,schema in generated.items():
        definitions=schema.pop('$defs',{})
        for key,value in {**definitions,name:schema}.items():
            value=json.loads(json.dumps(flatten(value)).replace('#/$defs/','#/components/schemas/'))
            contract['components']['schemas'][key]=value
    response=lambda schema,description:{'description':description,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/'+schema}}}}
    contract['paths']['/processing/status']={'get':{'operationId':'processingStatus','summary':'Preparación efectiva por alcance y rol',
        'tags':['processing'],'x-stage':'S3.1','x-roles':['ADMIN','TUTOR','DIRECTOR','RESEARCHER'],
        'description':'Autenticado. Estado general derivado de registro/configuración/archivos privados y política de escritura; no revela estudiantes, etiquetas, modelos ni rutas. REAL siempre false; health no habilita procesamiento.',
        'responses':{'200':response('ProcessingStatus','Estado público sanitizado'),
            '401':response('Error','SESSION_INVALID'), '503':response('Error','SERVICE_UNAVAILABLE sanitizado; sin consultas/secretos'),
            '500':response('Error','Error interno sanitizado')}}}
    if {'name':'processing'} not in contract['tags']: contract['tags'].append({'name':'processing'})
    for p in ('/imports/preview','/imports/{id}/commit'):
        contract['paths'][p]['post']['description']=('Sesión → ADMIN → CSRF → preparación del servidor → entrada → contexto/origen → procedencia exacta. '
          'REAL: 422 INSTITUTIONAL_PROCESSING_NOT_READY. SYNTHETIC: solo archivo/hash/contexto del estudio registrado, '
          'UNREGISTERED_SYNTHETIC_FILE 422 para modificado/no registrado. Sin flag de origen del cliente. '
          'Conserva parser, límites, expected_preview_version, stale 409, transacción, revisiones e idempotencia. '
          'Confirmación vincula etiquetas/resultados privados a cortes verificados sin exponerlos.')
    contract['paths']['/predictions/run']['post']['description']=('Sesión → ADMIN → CSRF → preparación del servidor → cuerpo → contexto/origen → modelo. '
      'REAL bloqueado con INSTITUTIONAL_PROCESSING_NOT_READY 422. Solo estudio SYNTHETIC registrado, modelo de simulación '
      'aprobado técnicamente y activo por CLI explícita. as_of no futuro; última revisión incorporada/disponible <= as_of. '
      '409 MODEL_NOT_AVAILABLE/MODEL_INCOMPATIBLE/PERIOD_LOCKED. Abstenciones no insertan riesgo; probabilidades null/no calibradas. '
      'INSERT único snapshot/model y auditoría atómica; repetición/concurrencia reutiliza resultado. No usa etiquetas de reserva ni crea alertas.')
    contract['paths']['/models']['get']['description']='ADMIN; modelos REAL históricos inactivos y SYNTHETIC de simulación; orden created_at DESC/id ASC. Origen explícito. APPROVED significa aprobación técnica de simulación para SYNTHETIC; nunca aprobación escolar. Sin artefactos, métricas individuales, particiones o etiquetas.'
    for p in ('/imports/preview','/imports/{id}/commit','/predictions/run'):
        contract['paths'][p]['post']['x-stage']='S3.1'
    path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
    print('OpenAPI 0.4.0: 19 operaciones, SYNTHETIC explícito y processing/status.')


if __name__=='__main__': main()
