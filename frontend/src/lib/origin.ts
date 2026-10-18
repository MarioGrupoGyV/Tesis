import type { Period, ProcessingStatus, User } from './api';

export const REAL_NOTICE = 'Datos reales locales — análisis exploratorio, no demuestra eficacia escolar.';
export const RETROSPECTIVE_LABEL = 'simulación retrospectiva';
/** Rótulo visible de todo periodo SYNTHETIC (la demostración en vivo): lo que se registre ahí no es un dato del colegio. */
export const DEMO_LABEL = 'Registro de demostración, no es dato del colegio';

/** Periodo REAL cuyo protocolo está confirmado (solo informativo: el servidor valida cada operación). */
export function realOpen(period: Period | null | undefined): boolean {
  return period?.data_origin === 'REAL' && period.real_processing_enabled === true;
}

/** SYNTHETIC siempre; REAL solo con protocolo confirmado. */
export function processingOpen(period: Period | null | undefined): boolean {
  return period?.data_origin === 'SYNTHETIC' || realOpen(period);
}

export function originName(origin: Period['data_origin'] | undefined): string {
  return origin === 'REAL' ? 'Datos reales locales' : 'Datos sintéticos';
}

type OperationKey = keyof ProcessingStatus['operations'];
const ADMIN_ONLY: OperationKey[] = ['import', 'predict', 'sync_alerts'];
const WRITES: OperationKey[] = ['import', 'predict', 'sync_alerts', 'write_followup'];

/** Disponibilidad de una operación: SYNTHETIC según el estado de procesamiento; REAL según rol y bloqueo del periodo. */
export function periodOperation(period: Period, processing: ProcessingStatus | null, key: OperationKey, user: User): { available: boolean; reason: string | null } {
  if (period.data_origin === 'SYNTHETIC') {
    const operation = processing?.operations[key];
    return { available: Boolean(operation?.available), reason: operation?.reason ?? null };
  }
  if (!realOpen(period)) return { available: false, reason: 'INSTITUTIONAL_PROCESSING_NOT_READY' };
  if (ADMIN_ONLY.includes(key) && user.role !== 'ADMIN') return { available: false, reason: 'ROLE_RESTRICTED' };
  if (key === 'write_followup' && user.role !== 'ADMIN' && user.role !== 'TUTOR') return { available: false, reason: 'ROLE_RESTRICTED' };
  if (WRITES.includes(key) && period.is_locked) return { available: false, reason: 'PERIOD_LOCKED' };
  return { available: true, reason: null };
}
