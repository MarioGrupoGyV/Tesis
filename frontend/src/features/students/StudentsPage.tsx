import { useState, type FormEvent, type MouseEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Period, type StudentFilters, type User } from '../../lib/api';
import { numberLabel, timestampLabel } from '../../lib/format';
import { EmptyState, ErrorState, EvaluationBadge, LoadingState, PageHeader, Pagination, RiskBadge } from '../../components/ui';
import './features.css';
import { Catalogs, NewStudent } from './ManualForms';

type Props = { user: User; period: Period | null; sectionId: string | null; onNavigate: (path: string) => void };
type RiskFilter = '' | 'LOW' | 'MEDIUM' | 'HIGH';
type Sort = 'anon_code' | 'risk_desc' | 'updated_desc';
type Filters = { search: string; risk: RiskFilter; sort: Sort; pageSize: number };
const initialFilters: Filters = { search: '', risk: '', sort: 'anon_code', pageSize: 20 };

export function StudentsPage(props: Props) {
  const [mode, setMode] = useState<'list' | 'new' | 'periods' | 'sections'>('list');
  const cache = useQueryClient();
  if (props.user.role === 'RESEARCHER') return <EmptyState title="Consulta no disponible para tu rol"><p>Los registros individuales están reservados al personal autorizado.</p></EmptyState>;
  return <div className="students-feature">{props.user.role === 'ADMIN' && <div className="student-detail-actions" aria-label="Administración académica"><button type="button" className="button primary" disabled={!props.period || props.period.is_locked} onClick={() => setMode('new')}>Nuevo estudiante</button><button type="button" className="button secondary" onClick={() => setMode('periods')}>Periodos</button><button type="button" className="button secondary" onClick={() => setMode('sections')}>Secciones</button>{mode !== 'list' && <button type="button" className="button secondary" onClick={() => setMode('list')}>Ver listado</button>}</div>}
    {mode === 'periods' || mode === 'sections' ? <Catalogs kind={mode} period={props.period} close={() => setMode('list')} /> : mode === 'new' && props.period ? <NewStudent period={props.period} cancel={() => setMode('list')} done={id => { void cache.invalidateQueries(); props.onNavigate(`/estudiantes/${id}?period_id=${props.period!.id}`); }} /> : props.period ? <StudentListing key={`${props.user.id}:${props.user.role}:${props.period.id}:${props.sectionId ?? 'all'}`} {...props} period={props.period} /> : <><PageHeader title="Estudiantes" description="Registro académico y mediciones por alumno." /><EmptyState title="Todavía no hay periodos disponibles"><p>{props.user.role === 'ADMIN' ? 'Empieza en Periodos. Después crea una sección y registra al primer estudiante.' : 'El administrador debe configurar un periodo y asignar las secciones.'}</p></EmptyState></>}
  </div>;
}

function StudentListing({ user, period, sectionId, onNavigate }: Props & { period: Period }) {
  const [draft, setDraft] = useState<Filters>(initialFilters);
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [page, setPage] = useState(1);
  const params: StudentFilters = { period_id: period.id, section_id: sectionId ?? undefined, search: filters.search || undefined,
    risk_level: filters.risk || undefined, sort: filters.sort, page, page_size: filters.pageSize };
  const students = useQuery({ queryKey: [user.id, user.role, 'students', period.id, sectionId, params],
    queryFn: ({ signal }) => api.students(params, signal), retry: false });
  const filtered = Boolean(filters.search || filters.risk);
  function apply(event: FormEvent) { event.preventDefault(); setFilters({ ...draft, search: draft.search.trim() }); setPage(1); }
  function clear() { setDraft(initialFilters); setFilters(initialFilters); setPage(1); }
  function navigate(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(path); }
  }
  return <div className="students-feature">
    <PageHeader title="Estudiantes" eyebrow="REGISTROS DEL PERIODO" description={`Periodo ${period.code} · ${sectionId ? 'Sección seleccionada' : 'Secciones autorizadas'}. Los valores sin información se muestran como “Sin dato”.`} />
    <section className="panel student-filters" aria-label="Filtros de estudiantes">
      <form onSubmit={apply}>
        <div className="student-filter-grid">
          <div className="student-search"><label htmlFor="student-search">Buscar código o nombre</label><input id="student-search" type="search" maxLength={160} value={draft.search} onChange={event => setDraft({ ...draft, search: event.target.value })} placeholder="Código o nombre del estudiante" /></div>
          <div><label htmlFor="student-risk">Riesgo estimado</label><select id="student-risk" value={draft.risk} onChange={event => setDraft({ ...draft, risk: event.target.value as RiskFilter })}><option value="">Todos</option><option value="LOW">Bajo</option><option value="MEDIUM">Medio</option><option value="HIGH">Alto</option></select></div>
          <div><label htmlFor="student-sort">Orden</label><select id="student-sort" value={draft.sort} onChange={event => setDraft({ ...draft, sort: event.target.value as Sort })}><option value="anon_code">Código</option><option value="risk_desc">Riesgo mayor primero</option><option value="updated_desc">Corte más reciente</option></select></div>
          <div><label htmlFor="student-page-size">Registros por página</label><select id="student-page-size" value={draft.pageSize} onChange={event => setDraft({ ...draft, pageSize: Number(event.target.value) })}>{[20, 50, 100].map(value => <option key={value} value={value}>{value}</option>)}</select></div>
        </div>
        <div className="student-filter-actions"><button className="button primary" type="submit">Aplicar filtros</button><button className="button secondary" type="button" onClick={clear}>Limpiar filtros</button></div>
      </form>
    </section>
    {students.isPending ? <LoadingState label="Consultando registros…" /> : students.isError ? <ErrorState error={students.error} onRetry={() => void students.refetch()} /> : students.data.items.length === 0 ?
      <EmptyState title={filtered ? 'No hay registros con estos filtros' : 'Este contexto todavía no tiene registros'}><p>{filtered ? 'Modifica el código, nombre o riesgo para ampliar la consulta.' : 'Registra un estudiante desde Nuevo estudiante. También se conserva la importación CSV autorizada.'}</p>{filtered && <button className="button secondary" type="button" onClick={clear}>Limpiar filtros</button>}</EmptyState> :
      <section className="panel student-list-panel" aria-label="Resultados de estudiantes">
        <div className="student-results-heading"><h2>Registros del periodo</h2><p className="muted" role="status">{students.data.total} {students.data.total === 1 ? 'registro' : 'registros'} {filtered ? 'con los filtros aplicados' : 'en este contexto'}</p></div>
        <div className="table-container student-table" tabIndex={0} role="region" aria-label="Tabla de estudiantes; desplazamiento horizontal disponible">
          <table><caption>Registros de estudiantes del periodo {period.code}</caption><thead><tr><th scope="col">Código</th><th scope="col">Grado / sección</th><th scope="col">Promedio</th><th scope="col">Asistencia</th><th scope="col">Último corte</th><th scope="col">Evaluación</th><th scope="col">Riesgo estimado</th></tr></thead>
            <tbody>{students.data.items.map(student => { const path = `/estudiantes/${student.id}?period_id=${encodeURIComponent(period.id)}${sectionId ? `&section_id=${encodeURIComponent(sectionId)}` : ''}`; return <tr key={student.id}><td><a className="student-code-link" href={path} onClick={event => navigate(event, path)} aria-label={`Ver registro de ${student.anon_code}`}>{student.anon_code}</a><small className="m1-name">{student.full_name ?? 'Nombre no informado'}{student.is_active === false && ' · Inactivo'}</small></td><td>{student.grade} / {student.section_code}</td><td>{numberLabel(student.average_grade)}</td><td>{numberLabel(student.attendance_pct, ' %')}</td><td className="student-cutoff">{timestampLabel(student.latest_cutoff_at)}</td><td><EvaluationBadge status={student.evaluation_status} /></td><td><RiskBadge risk={student.risk_level} /></td></tr>; })}</tbody>
          </table>
        </div>
        <Pagination page={students.data.page} pageSize={students.data.page_size} total={students.data.total} onPageChange={setPage} />
        <p className="muted student-list-note">El riesgo es una estimación del modelo. Un registro sin evaluación conserva ese estado hasta obtener un resultado válido.</p>
      </section>}
  </div>;
}
