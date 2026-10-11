"""Add only the retrospective contract, keeping existing operations unchanged."""
import json
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.schemas.retrospective import (RetrospectiveDetail, RetrospectivePage,
    RetrospectivePartialInput, RetrospectivePartialResult)


def main():
    path = ROOT / 'docs/planning/Contrato_API.yaml'
    contract = yaml.safe_load(path.read_text(encoding='utf-8'))
    contract['info']['version'] = '0.6.0'
    contract['info']['description'] = ('S6 integrado para simulación SYNTHETIC; procesamiento institucional operativo bloqueado. '
        'Evaluación retrospectiva separada ADMIN de paquete local previamente registrado/autorizado. '
        'No reentrena, activa, envía notificaciones ni crea intervenciones.')
    if {'name': 'retrospective'} not in contract['tags']:
        contract['tags'].append({'name': 'retrospective'})
    for schema in (RetrospectiveDetail, RetrospectivePage, RetrospectivePartialInput, RetrospectivePartialResult):
        generated = schema.model_json_schema()
        definitions = generated.pop('$defs', {})
        for name, value in {**definitions, schema.__name__: generated}.items():
            contract['components']['schemas'][name] = json.loads(json.dumps(value).replace('#/$defs/', '#/components/schemas/'))
    def response(schema, description):
        return {'description': description, 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/' + schema}}}}
    def operation(identifier, schema, description, params=None, body=None, write=False, csv=False):
        out = {'operationId': identifier, 'summary': description, 'description': description,
               'tags': ['retrospective'], 'x-stage': 'S6', 'x-roles': ['ADMIN'], 'parameters': params or [],
               'responses': {'200': response(schema, 'Resultado retrospectivo separado del contexto operativo'),
                   **{str(code): response('Error', message) for code, message in {
                       401: 'SESSION_INVALID', 403: 'FORBIDDEN o CSRF_INVALID', 404: 'RETROSPECTIVE_NOT_FOUND',
                       409: 'Integridad, paquete o artefacto incompatible', 422: 'Fechas, entradas o escalas no válidas',
                       503: 'Almacenamiento o base no disponibles', 500: 'Error interno sanitizado'}.items()}}}
        if write:
            out['parameters'].append({'name': 'X-CSRF-Token', 'in': 'header', 'required': True, 'schema': {'type': 'string'}})
        if body:
            out['requestBody'] = {'required': True, 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/' + body}}}}
        if csv:
            out['responses']['200'] = {'description': 'CSV UTF-8 con BOM, 60 filas numeradas sin códigos/nombres. Fecha real, riesgo, referencia y propuesta separados de notificación/intervención.',
                                      'content': {'text/csv': {'schema': {'type': 'string'}}}}
        return out
    id_param = [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'string', 'format': 'uuid'}}]
    pagination = [{'name': name, 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'maximum': maximum, 'default': default}}
                  for name, maximum, default in [('page', 10000, 1), ('page_size', 100, 10)]]
    contract['paths']['/retrospective/evaluations'] = {
        'get': operation('retrospectiveHistory', 'RetrospectivePage', 'Historial ADMIN firmado, paginado, con métricas agregadas; sin registro devuelve available false.', pagination),
        'post': operation('runRetrospective', 'RetrospectiveDetail', 'Nueva ejecución con fecha real y actor; artefacto congelado B1, 60 registros B2. Escalador incluido; sin fit. Registro y auditoría en un único sobre privado firmado e inmutable. Conserva advertencias entre versiones y discrepancias.', write=True)}
    contract['paths']['/retrospective/evaluations/{id}'] = {'get': operation('retrospectiveDetail', 'RetrospectiveDetail', 'Resultado retrospectivo ADMIN, 60 filas anonimizadas y verificación temporal declarada, sin acreditar autenticidad.', id_param.copy())}
    contract['paths']['/retrospective/evaluations/{id}/report.csv'] = {'get': operation('exportRetrospectiveCsv', 'Error', 'Reporte retrospectivo ADMIN de una ejecución persistida.', id_param.copy(), csv=True)}
    contract['paths']['/retrospective/partial-prediction'] = {'post': operation('retrospectivePartialPrediction', 'RetrospectivePartialResult', 'Ensayo parcial ADMIN no persistido como caso. Tres variables y disponibilidad por variable <= corte B1/B2 a las 00:00 Lima; sin etiquetas en X, sin propuestas operativas.', body='RetrospectivePartialInput', write=True)}
    path.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True, width=105), encoding='utf-8')
    print('OpenAPI 0.6.0: 32 operaciones, 30 paths')


if __name__ == '__main__':
    main()
