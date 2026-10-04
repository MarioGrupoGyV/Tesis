"""No existe todavía un protocolo institucional aprobado e implementado."""
from app.core.errors import AppError


def require_processing_protocol():
    # Sin interruptor de configuración: habilitar exige otra iteración revisada.
    raise AppError(422, 'INSTITUTIONAL_PROCESSING_NOT_READY',
        'La importación institucional está pendiente de autorización de procedencia, escala, periodo, ventanas temporales y reglas de calidad. No se guardó el archivo.')
