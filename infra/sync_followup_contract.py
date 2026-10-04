"""Genera esquemas públicos S5 del código y documenta ocho operaciones efectivas."""
import json
from pathlib import Path
import subprocess
import yaml
from sync_study_contract import flatten

ROOT = Path(__file__).resolve().parents[1]
CODE = """
import inspect,json
from pydantic import BaseModel
from app.schemas import s5
from app.schemas.ml import PredictionRunResult
from app.schemas.processing import ProcessingStatus
classes=[c for _,c in inspect.getmembers(s5,inspect.isclass)
         if issubclass(c,BaseModel) and c.__module__==s5.__name__]
classes += [PredictionRunResult,ProcessingStatus]
print(json.dumps({c.__name__:c.model_json_schema(mode='serialization') for c in classes}))
"""

def response(schema,description):
    return {'description':description,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/'+schema}}}}

def parameter(name,schema,required=False,where='query'):
    return {'name':name,'in':where,'required':required,'schema':schema}

def nullable_enums(value):
    if isinstance(value,list):
        return [nullable_enums(v) for v in value]
    if not isinstance(value,dict):
        return value
    value={k:nullable_enums(v) for k,v in value.items()}
    if isinstance(value.get('type'),list) and 'null' in value['type'] and 'enum' in value:
        value['enum'] = list(dict.fromkeys([*value['enum'],None]))
    return value

def main():
    generated=json.loads(subprocess.check_output(['docker','run','--rm','--network','none',
        '--mount',f'type=bind,source={ROOT / "backend/app"},target=/app/app,readonly',
        'riesgo-escolar-api','python','-c',CODE],cwd=ROOT,text=True,encoding='utf-8'))
    path=ROOT/'docs/planning/Contrato_API.yaml'
    contract=yaml.safe_load(path.read_text(encoding='utf-8'))
    contract['info']['version']='0.5.0'
    contract['info']['description']='S5: seguimiento y reportes operativos del estudio SYNTHETIC registrado. REAL bloqueado. Sin eficacia escolar, S6 ni entrenamiento/activación HTTP.'
    components=contract['components']['schemas']
    for name,schema in generated.items():
        if name.endswith(('Patch','Create','Input')):
            # Omitido y null son distintos en PATCH. Evitar que el generador
            # trate defaults opcionales como campos obligatorios del cliente.
            for key,definition in schema.get('properties',{}).items():
                if key not in schema.get('required',[]):
                    definition.pop('default',None)
        definitions=schema.pop('$defs',{})
        for key,value in {**definitions,name:schema}.items():
            if key in components and key not in generated and key!='ProcessingOperations':
                continue  # Conserva invariantes públicos anteriores (probabilidades, etc.).
            components[key]=json.loads(json.dumps(nullable_enums(flatten(value))).replace('#/$defs/','#/components/schemas/'))
    uuid={'type':'string','format':'uuid'}
    pagination=[parameter('page',{'type':'integer','minimum':1,'maximum':10000,'default':1}),
        parameter('page_size',{'type':'integer','minimum':1,'maximum':100,'default':20})]
    common=[parameter('period_id',uuid,True),parameter('section_id',uuid),
            parameter('search',{'type':'string','maxLength':40})]
    report_filters=common+[
        parameter('risk_level',{'type':'string','enum':['LOW','MEDIUM','HIGH']}),
        parameter('evaluation_status',{'type':'string','enum':['EVALUATED','NOT_EVALUATED','INSUFFICIENT_DATA']}),
        parameter('alert_status',{'type':'string','enum':['OPEN','IN_REVIEW','RESOLVED','DISMISSED']})]
    def operation(id,schema,roles,description,params=None,input=None,csv=False):
        out={'operationId':id,'summary':description.split('.')[0],'tags':['reports' if id.startswith(('report','export')) else 'followup'],
             'x-stage':'S5','x-roles':roles,'description':description,'parameters':params or [],
             'responses':{'200':response(schema,'Resultado público actual del estudio sintético'),
              '401':response('Error','SESSION_INVALID; sin sesión válida'),
              '403':response('Error','FORBIDDEN o CSRF_INVALID; rol/CSRF antes del cuerpo'),
              '404':response('Error','Recurso no disponible; ajeno e inexistente indistinguibles'),
              '409':response('Error','VERSION_CONFLICT, CREATION_KEY_CONFLICT, PERIOD_LOCKED, INVALID_TRANSITION o MODEL_NOT_AVAILABLE; sin escrituras parciales'),
              '422':response('Error','VALIDATION_ERROR, INSTITUTIONAL_PROCESSING_NOT_READY o procedencia/fechas no admitidas'),
              '503':response('Error','SERVICE_UNAVAILABLE sanitizado; conflictos de integridad conservan 409'),
              '500':response('Error','Error interno sanitizado')}}
        if input:
            out['parameters'].append(parameter('X-CSRF-Token',{'type':'string','minLength':32},True,'header'))
            out['requestBody']={'required':True,'content':{'application/json':{'schema':{'$ref':'#/components/schemas/'+input}}}}
        if csv:
            out['responses']['200']={'description':'UTF-8 con BOM; una fila por matrícula del conjunto filtrado completo, null celda vacía. Textos con prefijos de fórmula se neutralizan con apóstrofo y controles eliminados en proyección. No notas/etiquetas/ML privado.',
                'headers':{'Content-Disposition':{'schema':{'type':'string'},'description':'attachment; filename="seguimiento-escolar-reporte.csv"'},
                           'Cache-Control':{'schema':{'type':'string','const':'no-store'}}},
                'content':{'text/csv':{'schema':{'type':'string'}}}}
        return out
    readers=['ADMIN','TUTOR','DIRECTOR']; writers=['ADMIN','TUTOR']
    idparam=[parameter('id',uuid,True,'path')]
    contract['paths']['/alerts/sync']={'post':operation('syncAlerts','FollowupResult',['ADMIN'],
        'Sincronizar seguimiento actual con followup-policy-v1. No reentrena ni reconstruye pasado. Solo último corte/revisión disponible y modelo activo compatible registrado. created casos nuevos; updated fuente; retained_low señal LOW conservada; no_alert LOW sin caso; reused decisiones persistentes; ignored_stale predicciones históricas omitidas; skipped_missing matrícula sin evaluación actual. Transacción única y lock por matrícula; predicción repetida no duplica evidencia.',input='SyncInput')}
    contract['paths']['/alerts']={'get':operation('listAlerts','AlertPage',readers,
        'Consultar casos autorizados del periodo. Alcance servidor; periodos bloqueados admiten lectura. Orden estable con UUID desempate. Estado/severidad pertenecen al caso; riesgo actual puede ser null o LOW y nunca cierra el caso automáticamente.',
        common+[parameter('status',{'type':'string','enum':['OPEN','IN_REVIEW','RESOLVED','DISMISSED']}),
         parameter('severity',{'type':'string','enum':['MEDIUM','HIGH']}),
         parameter('sort',{'type':'string','enum':['anon_code','severity_desc','updated_desc'],'default':'updated_desc'})]+pagination)}
    contract['paths']['/alerts/{id}']={
        'get':operation('alertDetail','AlertDetail',readers,'Consultar caso con fuente, evaluación actual, actividades, capacidades y últimos 100 eventos auditados. Fuente antigua no se atribuye al último corte. Tutor público por nombre o null. Ajeno/inexistente: mismo404.',idparam.copy()),
        'patch':operation('updateAlert','AlertDetail',writers,'Cambiar estado de caso con expected_version entero estricto. OPEN permite IN_REVIEW/RESOLVED/DISMISSED; IN_REVIEW permite cierre; cerrado terminal. Cierre exige motivo no vacío, closed_at servidor. No completa/cancela actividades. Cambio efectivo y auditoría atómicos, una versión; no-op no incrementa.',idparam.copy(),input='AlertPatch')}
    contract['paths']['/interventions']={'post':operation('createIntervention','InterventionCreateResult',writers,
        'Planificar actividad de simulación en caso activo autorizado. expected_alert_version estricto, creation_key UUID y payload original canonicalizado incluyendo versión. Mismo actor/clave/payload reutiliza aun si la actividad luego cambió; otra carga409. Deriva matrícula/origen/actor; PLANNED y performed_at null. Periodo bloqueado rechaza toda escritura.',input='InterventionCreate')}
    creation_responses=contract['paths']['/interventions']['post']['responses']
    creation_responses['200']['description']='Resultado ya existente, reused_result=true; sin nueva actividad/auditoría'
    creation_responses['201']=response('InterventionCreateResult','Actividad PLANNED creada, reused_result=false')
    contract['paths']['/interventions/{id}']={'patch':operation('updateIntervention','InterventionView',writers,
        'Editar actividad PLANNED con expected_version estricto. DONE exige performed_at con zona no futuro del servidor; CANCELLED conserva null. DONE/CANCELLED terminales. Puede completar/cancelar una actividad previamente planificada después del cierre del caso; no permite nuevas allí. Digest original no cambia. Cambio/auditoría atómicos.',idparam.copy(),input='InterventionPatch')}
    contract['paths']['/reports/summary']={'get':operation('reportSummary','ReportSummary',readers,
        'Resumen ACTUAL del conjunto filtrado autorizado, unidad matrícula. Total=evaluated+not_evaluated+insufficient_data; evaluated=LOW+MEDIUM+HIGH. Porcentajes de riesgo sobre evaluados con denominador y null si cero. Casos/actividades agregados antes de unir; DONE única actividad realizada. generated_at servidor y rango de últimos cortes. items paginados; agregados cubren conjunto completo. Lectura consistente, sin eficacia ni métricas ML.',report_filters+pagination)}
    contract['paths']['/reports/export.csv']={'get':operation('exportReportCsv','ReportSummary',readers,
        'Solicitar CSV completo del mismo conjunto actual y filtros de resumen. Orden código/UUID, una matrícula por fila. Alcance/origen/periodo/generated_at públicos; no notas, narraciones, etiquetas, métricas privadas. Attachment/no-store; errores JSON Error. Audita solicitud/actor/filtros/alcance/instante/conteo, no apertura/guardado del archivo.',report_filters,csv=True)}
    for tag in ('followup','reports'):
        if not any(t['name']==tag for t in contract['tags']): contract['tags'].append({'name':tag})
    previous=contract['paths']['/predictions/run']['post']['description'].split(' S5: predicciones, followup-policy-v1',1)[0]
    previous=previous.replace('No usa etiquetas de reserva ni crea alertas.', 'No usa etiquetas de reserva.')
    contract['paths']['/predictions/run']['post']['description']=previous+' S5: predicciones, followup-policy-v1 y auditoría se confirman juntos. followup refleja solo predicciones seleccionadas que siguen actuales; las históricas se cuentan ignored_stale. Reutilizar predicciones puede crear seguimiento inicial. No commit previo a la sincronización.'
    contract['paths']['/predictions/run']['post']['x-stage']='S5'
    count=sum(m in ('get','post','patch','put','delete') for ops in contract['paths'].values() for m in ops)
    assert count==27,count
    path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
    print('OpenAPI 0.5.0: 27 operaciones efectivas; esquemas S5 generados.')

if __name__=='__main__': main()
