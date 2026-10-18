"""Proyectar al contrato el Bloque 3B-2: cadena REAL (indicadores por origen/bimestre, modelos con alcance, estado de periodo)."""
import os
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(APP_ENV='test',DATABASE_URL='postgresql+psycopg://unused:unused@localhost/contract_test',
    CSRF_SECRET='contract-generation-only-not-a-runtime-secret')
from app.main import app

SCHEMAS=('Period','Model','ProcessingStatus','Nia','IndicatorsResponse','StudentIndicator','IndicatorContext','ReportSummary','Summary','ModelMetrics','ValidatedDetection','Spread','DetectionCounts')
# Contrato endurecido a mano (p. ej. probabilidades solo null): solo se añaden las propiedades nuevas, sin reemplazar el resto.
MERGE=('Prediction','AlertCase')
OPERATIONS=('indicators','indicatorStudents','exportIndicatorsCsv')


def main():
    path=ROOT/'docs/planning/Contrato_API.yaml'
    contract=yaml.safe_load(path.read_text(encoding='utf-8'))
    runtime=app.openapi()
    contract['info']['version']=runtime['info']['version']
    contract['info']['description']=('S6, M1, Bloques 1–3B-1 conservados. Bloque 5.1: detección validada (fuera de muestra) del modelo activo, por bimestre y '
        'total, con media y desviación entre repeticiones (`validated_detection`; `NO_OUT_OF_SAMPLE_REPORT` si falta). Bloque 3B-3: PDER y CRA por corte (predicción de cada bimestre), métricas REAL fuera de muestra '
        '(validación cruzada del informe del modelo activo; `metric_basis`). Bloque 3B-2: cadena REAL local. Con un protocolo REAL confirmado que cubra el '
        'periodo se habilitan importación del CSV canónico, comparación exploratoria, evaluación retrospectiva, alertas, reportes e '
        'indicadores por bimestre; sin protocolo todo REAL sigue con INSTITUTIONAL_PROCESSING_NOT_READY. Los datos REAL son análisis '
        'exploratorio local: no demuestran eficacia escolar. El estudio institucional, su comparación y la activación del modelo se '
        'administran por CLI.')
    for name in SCHEMAS:
        contract['components']['schemas'][name]=runtime['components']['schemas'][name]
    for name in MERGE:
        target=contract['components']['schemas'][name]
        for prop,definition in runtime['components']['schemas'][name]['properties'].items():
            if prop not in target['properties']:
                target['properties'][prop]=definition
                if prop in runtime['components']['schemas'][name].get('required',[]):
                    target.setdefault('required',[]).append(prop)
    for route,methods in runtime['paths'].items():
        for method,operation in methods.items():
            if operation.get('operationId') not in OPERATIONS:
                continue
            target=contract['paths'][route.removeprefix('/api/v1')][method]
            known={p['name'] for p in target.get('parameters',[])}
            for parameter in operation.get('parameters',[]):
                if parameter['name']=='bimester' and 'bimester' not in known:
                    parameter['description']='Código de bimestre del protocolo REAL; solo aplica a periodos REAL.'
                    target.setdefault('parameters',[]).append(parameter)
    path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True,width=105),encoding='utf-8')
    print('Contrato B3B-2',contract['info']['version'])


if __name__=='__main__':
    main()
