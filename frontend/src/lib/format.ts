export function dateLabel(value: string | null | undefined): string {
  if (!value) return 'Sin fecha';
  const [year, month, day] = value.split('-').map(Number);
  return new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'America/Lima' }).format(new Date(Date.UTC(year, month - 1, day, 17)));
}
export function timestampLabel(value: string | null | undefined): string {
  if (!value) return 'Sin fecha';
  return new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'America/Lima' }).format(new Date(value)) + ' · Lima';
}
export function numberLabel(value: number | null | undefined, suffix = ''): string {
  return value == null ? 'Sin dato' : new Intl.NumberFormat('es-PE', { maximumFractionDigits: 2 }).format(value) + suffix;
}
export function reasonLabel(code: string | null | undefined): string {
  const labels: Record<string, string> = {
    FORBIDDEN: 'Esta acción no está disponible para tu rol.',
    INSTITUTIONAL_PROCESSING_NOT_READY: 'El procesamiento de información real permanece bloqueado.',
    SYNTHETIC_STUDY_NOT_READY: 'El administrador debe preparar el estudio sintético autorizado.',
    SYNTHETIC_IMPORT_REQUIRED: 'Primero debe completarse la importación del archivo registrado.',
    SYNTHETIC_COMPARISON_REQUIRED: 'Falta completar la comparación técnica mediante el procedimiento administrativo.',
    MODEL_NOT_AVAILABLE: 'Modelo no disponible. El administrador debe revisar su preparación.',
    MODEL_INCOMPATIBLE: 'El modelo y el contexto seleccionado no son compatibles.',
    PERIOD_LOCKED: 'Este periodo está bloqueado para nuevas escrituras.',
    UNREGISTERED_SYNTHETIC_FILE: 'El archivo no coincide con un CSV registrado del generador autorizado.',
    IMPORT_PREVIEW_STALE: 'La vista previa cambió. Revisa el archivo nuevamente antes de confirmar.',
    INSUFFICIENT_DATA: 'Faltan datos necesarios para estimar el riesgo.',
    REQUIRED_FEATURE_MISSING: 'Falta una variable requerida para la estimación.',
    MISSING_FRACTION_EXCEEDED: 'Hay demasiadas variables sin datos para estimar el riesgo.',
    NOT_ELIGIBLE: 'El corte no cumple las condiciones de evaluación del estudio sintético.',
    ALERT_TERMINAL: 'El caso ya está cerrado. Conserva su evidencia y no admite nuevas actividades.',
    CASE_CLOSED: 'El caso ya está cerrado. Conserva su evidencia y no admite nuevas actividades.',
    ALERT_CLOSED: 'El caso ya está cerrado. Conserva su evidencia y no admite nuevas actividades.',
    ROLE_RESTRICTED: 'Tu rol permite consultar este seguimiento, sin modificarlo.',
    INTERVENTION_TERMINAL: 'La actividad ya está realizada o cancelada y no admite nuevas ediciones.',
    ALERT_VERSION_CONFLICT: 'El caso cambió. Revisa su información actualizada antes de enviar el borrador.',
    INTERVENTION_VERSION_CONFLICT: 'La actividad cambió. Revisa la información actualizada antes de enviar el borrador.',
  };
  return code ? labels[code] ?? 'La acción está bloqueada por una condición del servidor. Consulta al administrador.' : 'La acción no está disponible en este momento.';
}
