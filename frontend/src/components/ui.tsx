import type { ReactNode } from 'react';
import { ApiError, errorMessage, type Student } from '../lib/api';
export function PageHeader({ title, description, eyebrow, action }: { title: string; description?: string; eyebrow?: string; action?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1 tabIndex={-1}>{title}</h1>{description && <p className="muted">{description}</p>}</div>{action && <div className="page-action">{action}</div>}</header>;
}
export function LoadingState({ label = 'Cargando información…' }: { label?: string }) {
  return <div className="state-message" role="status"><span className="spinner" aria-hidden="true" /><p>{label}</p></div>;
}
export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <section className="empty-state" role="status"><span className="empty-symbol" aria-hidden="true">◇</span><h2>{title}</h2>{children && <div className="muted">{children}</div>}{action}</section>;
}
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const expected = error instanceof ApiError && [403, 404, 409, 422].includes(error.status);
  return <section className={`notice ${expected ? '' : 'error'}`} role={expected ? 'status' : 'alert'}><strong>{expected ? 'Revisa esta condición' : 'No pudimos completar la consulta'}</strong><p>{errorMessage(error)}</p>{error instanceof ApiError && error.details.length > 0 && <ul>{error.details.map((detail, i) => <li key={i}>{detail.row ? `Fila ${detail.row} · ` : ''}{detail.field ? `${detail.field}: ` : ''}{detail.message}</li>)}</ul>}{error instanceof ApiError && error.requestId && <small className="support-reference">Referencia de soporte: {error.requestId}</small>}{onRetry && <button className="button secondary" type="button" onClick={onRetry}>Volver a intentar</button>}</section>;
}
export function Pagination({ page, pageSize, total, onPageChange }: { page: number; pageSize: number; total: number; onPageChange: (value: number) => void }) {
  const last = Math.max(1, Math.ceil(total / pageSize));
  return <nav className="pagination" aria-label="Paginación"><p role="status">{total === 0 ? '0 resultados' : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} de ${total}`}<span> · Página {page} de {last}</span></p><div><button className="button secondary" type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>← Anterior</button><button className="button secondary" type="button" disabled={page >= last} onClick={() => onPageChange(page + 1)}>Siguiente →</button></div></nav>;
}
export function RiskBadge({ risk }: { risk: Student['risk_level'] }) {
  return <span className={`badge risk-${risk?.toLowerCase() ?? 'none'}`}><span aria-hidden="true">{risk === 'HIGH' ? '▲' : risk === 'MEDIUM' ? '◆' : risk === 'LOW' ? '●' : '—'}</span> {risk === 'HIGH' ? 'Alto' : risk === 'MEDIUM' ? 'Medio' : risk === 'LOW' ? 'Bajo' : 'Sin estimación'}</span>;
}
export function EvaluationBadge({ status }: { status: Student['evaluation_status'] }) {
  return <span className={`badge evaluation-${status.toLowerCase()}`}>{status === 'EVALUATED' ? '✓ Evaluado' : status === 'INSUFFICIENT_DATA' ? '◇ Datos insuficientes' : '○ Sin evaluar'}</span>;
}
