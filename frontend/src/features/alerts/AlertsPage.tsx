import { useState, type FormEvent, type MouseEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type Alert, type AlertFilters, type FollowupResult, type Period, type ProcessingStatus, type User } from '../../lib/api';
import { EmptyState, ErrorState, LoadingState, PageHeader, Pagination, RiskBadge } from '../../components/ui';
import { timestampLabel, reasonLabel } from '../../lib/format';
import { AlertStatusBadge } from './labels';
import { FollowupCounts } from './FollowupCounts';
import { useFollowupWrite } from './formState';
import './features.css';

type Props = { user: User; period: Period | null; sectionId: string; processing: ProcessingStatus | null; onNavigate: (path: string) => void };
type Filters = { search: string; status: '' | Alert['status']; severity: '' | Alert['severity']; sort: 'anon_code' | 'severity_desc' | 'updated_desc'; pageSize: number };
const initial: Filters = { search: '', status: '', severity: '', sort: 'updated_desc', pageSize: 20 };

export function AlertsPage(props: Props) {
  if (props.user.role === 'RESEARCHER') return <EmptyState title="Consulta no disponible para tu rol"><p>El seguimiento está reservado al personal autorizado.</p></EmptyState>;
  if (!props.period) return <><PageHeader title="Alertas" /><EmptyState title="Selecciona un periodo"><p>Consulta los casos dentro de un contexto autorizado.</p></EmptyState></>;
  if (props.period.data_origin !== 'SYNTHETIC') return <><PageHeader title="Alertas" /><EmptyState title="Seguimiento institucional bloqueado"><p>En esta etapa solo se consulta el estudio sintético registrado.</p></EmptyState></>;
  return <AlertListing key={`${props.user.id}:${props.user.role}:${props.period.id}:${props.sectionId}`} {...props} period={props.period} />;
}

function AlertListing({ user, period, sectionId, processing, onNavigate }: Props & { period: Period }) {
  const [draft, setDraft] = useState(initial);
  const [filters, setFilters] = useState(initial);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<FollowupResult | null>(null);
  const sync = useFollowupWrite(user);
  const params: AlertFilters = { period_id: period.id, section_id: sectionId || undefined, status: filters.status || undefined, severity: filters.severity || undefined, search: filters.search || undefined, sort: filters.sort, page, page_size: filters.pageSize };
  const alerts = useQuery({ queryKey: [user.id, user.role, 'alerts', period.id, sectionId, params], queryFn: ({ signal }) => api.alerts(params, signal), retry: false });
  const filtered = Boolean(filters.search || filters.status || filters.severity);
  const operation = processing?.operations.sync_alerts;
  const canSync = user.role === 'ADMIN' && Boolean(operation?.available) && !period.is_locked;
  const blocked = period.is_locked ? reasonLabel('PERIOD_LOCKED') : !processing ? 'No pudimos consultar la disponibilidad. Actualiza el estado del sistema antes de sincronizar.' : !operation?.available ? reasonLabel(operation?.reason) : '';
  function apply(event: FormEvent) { event.preventDefault(); setFilters({ ...draft, search: draft.search.trim() }); setPage(1); }
  function clear() { setDraft(initial); setFilters(initial); setPage(1); }
  function open(event: MouseEvent<HTMLAnchorElement>, path: string) { if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(path); } }
  return <div className="followup-feature"><PageHeader title="Alertas" eyebrow="SEGUIMIENTO DEL ESTUDIO" description={`Periodo ${period.code}. Revisa los casos de las secciones autorizadas. La severidad explica qué motivó el caso; su evaluación actual puede haber cambiado.`} action={user.role === 'ADMIN' ? <button className="button primary" type="button" disabled={!canSync || sync.pending} onClick={() => { setResult(null); void sync.submit(signal => api.syncAlerts(period.id, signal), setResult); }}>{sync.pending ? 'Actualizando alertas…' : 'Actualizar alertas'}</button> : undefined} />
    {user.role === 'ADMIN' && blocked && <p className="notice" role="status">{blocked}</p>}
    {Boolean(sync.error) && <><ErrorState error={sync.error} />{sync.uncertain && <p className="notice">No recibimos la confirmación. Consulta la lista antes de repetir la sincronización; las decisiones ya registradas se reutilizan.</p>}</>}
    {result && <FollowupCounts result={result} />}
    <section className="panel" aria-label="Filtros de alertas"><form onSubmit={apply}><div className="followup-filters"><div><label htmlFor="alert-search">Buscar código</label><input id="alert-search" type="search" maxLength={40} value={draft.search} placeholder="Código sintético" onChange={event => setDraft({ ...draft, search: event.target.value })} /></div><div><label htmlFor="alert-status">Estado del caso</label><select id="alert-status" value={draft.status} onChange={event => setDraft({ ...draft, status: event.target.value as Filters['status'] })}><option value="">Todos</option><option value="OPEN">Abierta</option><option value="IN_REVIEW">En revisión</option><option value="RESOLVED">Concluida</option><option value="DISMISSED">Descartada</option></select></div><div><label htmlFor="alert-severity">Severidad que motivó el caso</label><select id="alert-severity" value={draft.severity} onChange={event => setDraft({ ...draft, severity: event.target.value as Filters['severity'] })}><option value="">Todas</option><option value="MEDIUM">Media</option><option value="HIGH">Alta</option></select></div><div><label htmlFor="alert-sort">Orden</label><select id="alert-sort" value={draft.sort} onChange={event => setDraft({ ...draft, sort: event.target.value as Filters['sort'] })}><option value="updated_desc">Actualización más reciente</option><option value="severity_desc">Severidad mayor primero</option><option value="anon_code">Código</option></select></div></div><div className="followup-actions"><button className="button primary" type="submit">Aplicar filtros</button><button className="button secondary" type="button" onClick={clear}>Limpiar filtros</button><div><label htmlFor="alert-page-size">Casos por página</label><select id="alert-page-size" value={draft.pageSize} onChange={event => setDraft({ ...draft, pageSize: Number(event.target.value) })}>{[20, 50, 100].map(value => <option key={value} value={value}>{value}</option>)}</select></div></div></form></section>
    {alerts.isPending ? <LoadingState label="Consultando casos autorizados…" /> : alerts.isError ? <ErrorState error={alerts.error} onRetry={() => void alerts.refetch()} /> : alerts.data.items.length === 0 ? <EmptyState title={filtered ? 'No hay casos con estos filtros' : 'Todavía no hay casos en este contexto'}><p>{filtered ? 'Amplía la búsqueda o cambia los estados seleccionados.' : 'Las evaluaciones medias o altas vigentes pueden generar seguimiento. Sin evaluación no se inventa una alerta.'}</p>{filtered && <button className="button secondary" type="button" onClick={clear}>Limpiar filtros</button>}</EmptyState> : <section className="panel"><div className="followup-toolbar"><h2>Casos de seguimiento</h2><p className="muted" role="status">{alerts.data.total} casos {filtered ? 'con los filtros aplicados' : 'en este contexto'}</p></div><p className="followup-scroll-help muted">↔ Desplaza la tabla para consultar el estado, responsable y actualización.</p><div className="table-container followup-table" tabIndex={0} role="region" aria-label="Tabla de casos; desplazamiento horizontal disponible"><table><caption>Casos del periodo {period.code} · secciones autorizadas</caption><thead><tr><th scope="col">Código</th><th scope="col">Grado / sección</th><th scope="col">Severidad del caso</th><th scope="col">Estado</th><th scope="col">Responsable</th><th scope="col">Actualización</th></tr></thead><tbody>{alerts.data.items.map(alert => { const path = `/alertas/${alert.id}?period_id=${encodeURIComponent(period.id)}${sectionId ? `&section_id=${encodeURIComponent(sectionId)}` : ''}`; return <tr key={alert.id}><td><a href={path} className="followup-link" aria-label={`Ver caso de ${alert.anon_code}`} onClick={event => open(event, path)}>{alert.anon_code}</a></td><td>{alert.grade}.º / {alert.section_code}</td><td><RiskBadge risk={alert.severity} /></td><td><AlertStatusBadge status={alert.status} /></td><td>{alert.assigned_display_name ?? 'Sin tutor asignado'}</td><td>{timestampLabel(alert.updated_at)}</td></tr>; })}</tbody></table></div><Pagination page={alerts.data.page} pageSize={alerts.data.page_size} total={alerts.data.total} onPageChange={setPage} /><p className="muted followup-note">Concluir un caso registra una decisión humana de simulación. No demuestra mejoría académica ni completa actividades pendientes.</p></section>}
  </div>;
}
