"""No existe todavía un protocolo institucional aprobado e implementado."""
from app.core.errors import AppError


def ml_readiness():
    return {'ready': False, 'code': 'INSTITUTIONAL_PROCESSING_NOT_READY',
            'missing': ['procedencia autorizada', 'escalas y criterio de referencia',
                        'etiquetas futuras verificables', 'calendario y protocolo',
                        'política de elegibilidad y faltantes', 'migración de activación'],
            'institutional_training': False, 'activation': False, 'institutional_inference': False}


def require_ml_protocol():
    raise AppError(422, 'INSTITUTIONAL_PROCESSING_NOT_READY',
        'Entrenamiento e inferencia institucional pendientes de protocolo, datos autorizados y activación. No se procesaron registros.')


def require_processing_protocol():
    # Sin interruptor de configuración: habilitar exige otra iteración revisada.
    raise AppError(422, 'INSTITUTIONAL_PROCESSING_NOT_READY',
        'La importación institucional está pendiente de autorización de procedencia, escala, periodo, ventanas temporales y reglas de calidad. No se guardó el archivo.')
