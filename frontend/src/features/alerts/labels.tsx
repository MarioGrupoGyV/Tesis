import type { Alert, Intervention } from '../../lib/api';

export const alertStatusLabels: Record<Alert['status'], string> = { OPEN: 'Abierta', IN_REVIEW: 'En revisión', RESOLVED: 'Concluida', DISMISSED: 'Descartada' };
export const interventionStatusLabels: Record<Intervention['status'], string> = { PLANNED: 'Planificada', DONE: 'Realizada', CANCELLED: 'Cancelada' };
export const interventionKindLabels: Record<Intervention['kind'], string> = { TUTORING: 'Tutoría', REINFORCEMENT: 'Refuerzo', FAMILY_MEETING: 'Reunión familiar simulada', OTHER: 'Otra actividad' };

export function AlertStatusBadge({ status }: { status: Alert['status'] }) {
  return <span className={`badge followup-status-${status.toLowerCase()}`}>{status === 'OPEN' ? '○' : status === 'IN_REVIEW' ? '◐' : status === 'RESOLVED' ? '✓' : '—'} {alertStatusLabels[status]}</span>;
}
export function InterventionStatusBadge({ status }: { status: Intervention['status'] }) {
  return <span className={`badge followup-status-${status.toLowerCase()}`}>{status === 'PLANNED' ? '○' : status === 'DONE' ? '✓' : '—'} {interventionStatusLabels[status]}</span>;
}

/** datetime-local is interpreted explicitly in Lima, never in the host zone. */
export function limaInputTimestamp(value: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null;
  const date = new Date(`${value}:00-05:00`);
  return Number.isNaN(date.getTime()) || timestampLimaInput(date.toISOString()) !== value ? null : date.toISOString();
}
export function timestampLimaInput(value: string): string {
  const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date(value));
  const part = (name: string) => parts.find(item => item.type === name)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`;
}
