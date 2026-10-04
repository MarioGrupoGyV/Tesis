import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type Alert, type Period, type ProcessingStatus, type ReportFilters, type Student, type User } from '../../lib/api';
import { EmptyState, ErrorState, EvaluationBadge, LoadingState, PageHeader, Pagination, RiskBadge } from '../../components/ui';
import { reasonLabel, timestampLabel } from '../../lib/format';
import { AlertStatusBadge } from '../alerts/labels';
import { ReportSummaryView } from './ReportSummaryView';
import './features.css';

type Props = { user: User; period: Period | null; sectionId: string; processing: ProcessingStatus | null; onNavigate: (path: string) => void };
type Filters = { search: string; risk: '' | NonNullable<Student['risk_level']>; evaluation: '' | Student['evaluation_status']; status: '' | Alert['status']; pageSize: number };
const initial: Filters = { search: '', risk: '', evaluation: '', status: '', pageSize: 20 };
export function ReportsPage(props: Props) {
  if (props.user.role === 'RESEARCHER') return <EmptyState title="Consulta no disponible para tu rol"><p>Los reportes y exportaciones están reservados al personal autorizado.</p></EmptyState>;
  if (!props.period) return <><PageHeader title="Reportes" /><EmptyState title="Selecciona un periodo"><p>El resumen corresponde al estado actual del contexto autorizado.</p></EmptyState></>;
  if (props.period.data_origin !== 'SYNTHETIC') return <><PageHeader title="Reportes" /><EmptyState title="Reporte institucional bloqueado"><p>En esta etapa solo se consulta el estudio sintético registrado.</p></EmptyState></>;
  return <ReportListing key={`${props.user.id}:${props.user.role}:${props.period.id}:${props.sectionId}`} {...props} period={props.period} />;
}

function ReportListing({ user, period, sectionId, processing, onNavigate }: Props & { period: Period }) {
  const [draft, setDraft] = useState(initial);
  const [filters, setFilters] = useState(initial);
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<unknown>(null);
  const [exportNotice, setExportNotice] = useState('');
  const controller = useRef<AbortController | null>(null);
  const alive = useRef(true);
  const busy = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); }; }, []);
  const params: ReportFilters = { period_id: period.id, section_id: sectionId || undefined, search: filters.search || undefined, risk_level: filters.risk || undefined, evaluation_status: filters.evaluation || undefined, alert_status: filters.status || undefined, page, page_size: filters.pageSize };
  const report = useQuery({ queryKey: [user.id, user.role, 'report', period.id, sectionId, params], queryFn: ({ signal }) => api.reportSummary(params, signal), retry: false });
  const operation = processing?.operations.export_reports;
  const canExport = Boolean(operation?.available);
  const filtered = Boolean(filters.search || filters.risk || filters.evaluation || filters.status);
  function apply(event: FormEvent) { event.preventDefault(); controller.current?.abort(); setExporting(false); busy.current = false; setExportNotice(''); setExportError(null); setFilters({ ...draft, search: draft.search.trim() }); setPage(1); }
  function clear() { controller.current?.abort(); setExporting(false); busy.current = false; setDraft(initial); setFilters(initial); setPage(1); setExportError(null); setExportNotice(''); }
  function open(event: MouseEvent<HTMLAnchorElement>, path: string) { if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey) { event.preventDefault(); onNavigate(path); } }
  async function download() {
    if (!canExport || busy.current) return;
    busy.current = true; const request = new AbortController(); controller.current = request;
    setExporting(true); setExportError(null); setExportNotice('');
    try {
      const { page: _page, page_size: _pageSize, ...allFilters } = params;
      const blob = await api.exportReportCsv(allFilters, request.signal);
      if (!alive.current || request.signal.aborted) return;
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
      anchor.href = url; anchor.download = 'seguimiento-escolar-reporte.csv'; document.body.append(anchor); anchor.click(); anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 0);
      setExportNotice('Respuesta CSV recibida. Se solicitó la descarga del conjunto filtrado completo; el sistema no confirma que se abrió o guardó el archivo.');
    } catch (error) { if (alive.current && !request.signal.aborted && !(error instanceof DOMException && error.name === 'AbortError')) setExportError(error); }
    finally { if (controller.current === request) { busy.current = false; if (alive.current && !request.signal.aborted) setExporting(false); } }
  }
  return <div className="reports-feature"><PageHeader title="Reportes" eyebrow="RESUMEN OPERATIVO" description={`Estado actual del periodo ${period.code}. Los indicadores y el CSV se calculan sobre todas las matrículas autorizadas con los filtros aplicados.`} action={<button className="button primary" type="button" disabled={!canExport || exporting || report.isPending || report.isError} onClick={() => void download()}>{exporting ? 'Obteniendo CSV…' : 'Descargar CSV'}</button>} />
    {!canExport && <p className="notice" role="status">{processing ? reasonLabel(operation?.reason) : 'No pudimos consultar la disponibilidad de exportación. Actualiza el estado del sistema antes de descargar.'}</p>}{Boolean(exportError) && <ErrorState error={exportError} />}{exportNotice && <p className="notice success" role="status">{exportNotice}</p>}
    <section className="panel" aria-label="Filtros de reportes"><form onSubmit={apply}><div className="report-filters"><div><label htmlFor="report-search">Buscar código</label><input id="report-search" type="search" maxLength={40} value={draft.search} onChange={event => setDraft({ ...draft, search: event.target.value })} placeholder="Código sintético" /></div><div><label htmlFor="report-risk">Riesgo actual</label><select id="report-risk" value={draft.risk} onChange={event => setDraft({ ...draft, risk: event.target.value as Filters['risk'] })}><option value="">Todos</option><option value="LOW">Bajo</option><option value="MEDIUM">Medio</option><option value="HIGH">Alto</option></select></div><div><label htmlFor="report-evaluation">Estado de evaluación</label><select id="report-evaluation" value={draft.evaluation} onChange={event => setDraft({ ...draft, evaluation: event.target.value as Filters['evaluation'] })}><option value="">Todos</option><option value="EVALUATED">Evaluado</option><option value="NOT_EVALUATED">Sin evaluar</option><option value="INSUFFICIENT_DATA">Datos insuficientes</option></select></div><div><label htmlFor="report-case-status">Estado de caso registrado</label><select id="report-case-status" value={draft.status} onChange={event => setDraft({ ...draft, status: event.target.value as Filters['status'] })}><option value="">Todos</option><option value="OPEN">Abierto</option><option value="IN_REVIEW">En revisión</option><option value="RESOLVED">Concluido</option><option value="DISMISSED">Descartado</option></select></div></div><div className="report-filter-actions"><button className="button primary" type="submit">Aplicar filtros</button><button className="button secondary" type="button" onClick={clear}>Limpiar filtros</button><div><label htmlFor="report-page-size">Matrículas por página</label><select id="report-page-size" value={draft.pageSize} onChange={event => setDraft({ ...draft, pageSize: Number(event.target.value) })}>{[20, 50, 100].map(value => <option key={value} value={value}>{value}</option>)}</select></div></div></form><p className="muted report-note">Los filtros cambian el conjunto completo del resumen y CSV. El filtro de caso considera los casos registrados, incluidos los cerrados; la columna “caso activo” muestra solo el actual.</p></section>
    {report.isPending ? <LoadingState label="Calculando resumen autorizado…" /> : report.isError ? <ErrorState error={report.error} onRetry={() => void report.refetch()} /> : <><ReportSummaryView report={report.data} />{report.data.total === 0 ? <EmptyState title={filtered ? 'No hay matrículas con estos filtros' : 'No hay matrículas en este contexto'}><p>Los porcentajes sin denominador se muestran como no estimables. No significan riesgo bajo.</p>{filtered && <button className="button secondary" type="button" onClick={clear}>Limpiar filtros</button>}</EmptyState> : <section className="panel"><div className="report-summary-heading"><h2>Estado por matrícula</h2><span className="badge">{report.data.total} en el conjunto completo</span></div><p className="report-scroll-help muted">↔ Desplaza la tabla para consultar la evaluación, los casos y las actividades.</p><div className="table-container report-rows-table" tabIndex={0} role="region" aria-label="Tabla del reporte; desplazamiento horizontal disponible"><table><caption>Una fila por matrícula autorizada, en orden de código</caption><thead><tr><th scope="col">Código</th><th scope="col">Grado / sección</th><th scope="col">Último corte</th><th scope="col">Evaluación / riesgo</th><th scope="col">Caso activo</th><th scope="col">Casos A / R / C / D</th><th scope="col">Actividades P / R / C</th></tr></thead><tbody>{report.data.items.map(row => { const studentPath = `/estudiantes/${row.student_id}?period_id=${encodeURIComponent(period.id)}&section_id=${encodeURIComponent(row.section_id)}`; const casePath = row.active_alert_id ? `/alertas/${row.active_alert_id}?period_id=${encodeURIComponent(period.id)}&section_id=${encodeURIComponent(row.section_id)}` : ''; return <tr key={row.enrollment_id}><td><a className="text-link" href={studentPath} onClick={event => open(event, studentPath)}>{row.anon_code}</a></td><td>{row.grade}.º / {row.section_code}</td><td>{timestampLabel(row.latest_cutoff_at)}</td><td><EvaluationBadge status={row.evaluation_status} /><div className="report-risk"><RiskBadge risk={row.risk_level} /></div></td><td>{row.active_alert_status && casePath ? <a href={casePath} className="text-link" aria-label={`Ver caso activo de ${row.anon_code}`} onClick={event => open(event, casePath)}><AlertStatusBadge status={row.active_alert_status} /></a> : 'Sin caso activo'}</td><td>{row.cases_open} / {row.cases_in_review} / {row.cases_resolved} / {row.cases_dismissed}</td><td>{row.interventions_planned} / {row.interventions_done} / {row.interventions_cancelled}</td></tr>; })}</tbody></table></div><Pagination page={report.data.page} pageSize={report.data.page_size} total={report.data.total} onPageChange={setPage} /><p className="muted report-note">Casos: Abiertos / en Revisión / Concluidos / Descartados. Actividades: Planificadas / Realizadas / Canceladas. Descargar CSV incluye todas las filas del conjunto filtrado, sin el límite de esta página.</p></section>}<p className="muted report-note">CSV UTF-8 para Windows, celdas vacías para valores ausentes y textos neutralizados para que no se interpreten como fórmulas. No incluye notas, motivos libres ni métricas privadas del modelo.</p></>}
  </div>;
}
