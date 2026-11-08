import { useState, type FormEvent, type MouseEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type Period, type RealSetCut, type RealSetPage as RealSet, type User } from '../../lib/api';
import { numberLabel } from '../../lib/format';
import { EmptyState, ErrorState, LoadingState, PageHeader, RiskBadge } from '../../components/ui';
import { CommandErrors, useCommand } from '../students/ManualForms';
import './realset.css';

// Bloque 10 (ADR 015): el conjunto real se consulta aquí, aparte de los registros de demostración. Solo lectura.
type Props = { user: User; periods: Period[]; initialPeriodId: string; onNavigate: (path: string) => void };
const CASE_LABELS: Record<string, string> = { OPEN: 'Abierto', IN_REVIEW: 'En revisión', RESOLVED: 'Concluido', DISMISSED: 'Descartado' };

export function RealSetPage({ user, periods, initialPeriodId, onNavigate }: Props) {
  const real = periods.filter(item => item.data_origin === 'REAL');
  const [chosen, setChosen] = useState(() => real.find(item => item.id === initialPeriodId)?.id ?? real[0]?.id ?? '');
  if (user.role === 'RESEARCHER') return <EmptyState title="Consulta no disponible para tu rol"><p>Los registros individuales están reservados al personal autorizado.</p></EmptyState>;
  if (!real.length) return <><PageHeader eyebrow="CONJUNTO REAL" title="Estudio real" /><EmptyState title="No hay un periodo real disponible"><p>Cuando exista un periodo con datos reales del estudio, se consultará aquí.</p></EmptyState></>;
  const period = real.find(item => item.id === chosen) ?? real[0];
  return <div className="realset-feature">
    <PageHeader eyebrow="CONJUNTO REAL · SOLO CONSULTA" title="Estudio real" description={`Periodo ${period.code}: los estudiantes del estudio, sus revisiones de mitad de bimestre y sus resultados. Los registros de demostración no aparecen aquí.`} />
    {real.length > 1 && <div className="realset-period"><label htmlFor="realset-period">Periodo real</label><select id="realset-period" value={period.id} onChange={event => setChosen(event.target.value)}>{real.map(item => <option key={item.id} value={item.id}>{item.code}</option>)}</select></div>}
    <RealSetView key={period.id} user={user} period={period} onNavigate={onNavigate} />
  </div>;
}

function RealSetView({ user, period, onNavigate }: { user: User; period: Period; onNavigate: (path: string) => void }) {
  const data = useQuery({ queryKey: [user.id, user.role, 'real-set', period.id], queryFn: ({ signal }) => api.realSet(period.id, signal), retry: false });
  const [search, setSearch] = useState('');
  const [applied, setApplied] = useState('');
  if (data.isPending) return <LoadingState label="Consultando el conjunto real…" />;
  if (data.isError) return <ErrorState error={data.error} onRetry={() => void data.refetch()} />;
  const set = data.data;
  const rows = applied ? set.items.filter(item => item.anon_code.toLowerCase().includes(applied.toLowerCase())) : set.items;
  function apply(event: FormEvent) { event.preventDefault(); setApplied(search.trim()); }
  function open(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(path); }
  }
  return <>
    <LockStatus user={user} period={period} set={set} />
    <section className="realset-summary" aria-label="Resumen del conjunto real">
      <article className="panel"><p className="eyebrow">ESTUDIANTES</p><strong className="realset-figure">{set.students}</strong><p className="muted">{set.alerts} con caso de seguimiento</p></article>
      {set.summary.map(level => <article className="panel" key={level.bimester}><p className="eyebrow">{level.bimester} · {level.cuts} revisiones</p>
        <p><span className="realset-row-label">Modelo{set.model_algorithm ? ` (${set.model_algorithm.toUpperCase()})` : ''}</span> {counts(level.predicted_low, level.predicted_medium, level.predicted_high)}{level.predicted_missing > 0 && <span className="muted"> · {level.predicted_missing} sin estimación</span>}</p>
        <p><span className="realset-row-label">Referencia</span> {counts(level.reference_low, level.reference_medium, level.reference_high)}</p></article>)}
    </section>
    <section className="panel" aria-label="Estudiantes del conjunto real">
      <form className="realset-filter" onSubmit={apply}><div><label htmlFor="realset-search">Buscar código</label><input id="realset-search" type="search" maxLength={40} value={search} onChange={event => setSearch(event.target.value)} /></div><button className="button primary" type="submit">Buscar</button>{applied && <button className="button secondary" type="button" onClick={() => { setSearch(''); setApplied(''); }}>Ver todos</button>}</form>
      <p className="muted realset-legend" role="status">{rows.length} de {set.total} estudiantes. «Modelo»: nivel que estimó el modelo en la revisión de mitad de bimestre. «Referencia»: nivel de la regla RIESGO_V2 al fin del bimestre.</p>
      {rows.length === 0 ? <EmptyState title="No hay estudiantes con ese código"><p>Revisa el código o vuelve a ver todos.</p></EmptyState> :
      <div className="table-container realset-table" tabIndex={0} role="region" aria-label="Tabla del conjunto real; desplazamiento horizontal disponible">
        <table><caption>Conjunto real del periodo {set.period_code}</caption>
          <thead><tr><th scope="col" rowSpan={2}>Código</th><th scope="col" rowSpan={2}>Grado / sección</th>{set.bimesters.map(b => <th scope="colgroup" colSpan={6} key={b} className="realset-group">{b}</th>)}<th scope="col" rowSpan={2}>Caso</th></tr>
            <tr>{set.bimesters.map(b => <Columns key={b} />)}</tr></thead>
          <tbody>{rows.map(item => { const path = `/estudiantes/${item.student_id}?period_id=${encodeURIComponent(set.period_id)}`; return <tr key={item.student_id}>
            <td><a className="student-code-link" href={path} onClick={event => open(event, path)} aria-label={`Ver ficha de ${item.anon_code}`}>{item.anon_code}</a></td><td>{item.grade} / {item.section_code}</td>
            {set.bimesters.map(b => <Cut key={b} cut={item.cuts.find(cut => cut.bimester === b)} />)}
            <td>{item.alert_status ? CASE_LABELS[item.alert_status] : 'Sin caso'}</td></tr>; })}</tbody>
        </table>
      </div>}
    </section>
  </>;
}

function counts(low: number, medium: number, high: number) {
  return <span className="realset-counts"><span className="risk-text risk-low">● Bajo {low}</span><span className="risk-text risk-medium">◆ Medio {medium}</span><span className="risk-text risk-high">▲ Alto {high}</span></span>;
}

function Columns() {
  return <><th scope="col" className="realset-group">Promedio</th><th scope="col">Asistencia</th><th scope="col">Actividades</th><th scope="col">Incidencias</th><th scope="col">Modelo</th><th scope="col">Referencia</th></>;
}

function Cut({ cut }: { cut: RealSetCut | undefined }) {
  if (!cut) return <><td className="realset-group" colSpan={6}><span className="muted">Sin revisión</span></td></>;
  return <><td className="realset-group">{numberLabel(cut.average_grade)}</td><td>{numberLabel(cut.attendance_pct, ' %')}</td><td>{numberLabel(cut.activities_pct, ' %')}</td><td>{numberLabel(cut.behavior_incidents)}</td>
    <td><RiskBadge risk={cut.predicted_risk} /></td><td><RiskBadge risk={cut.reference_risk} /></td></>;
}

function LockStatus({ user, period, set }: { user: User; period: Period; set: RealSet }) {
  const cache = useQueryClient();
  const command = useCommand();
  const [confirming, setConfirming] = useState(false);
  if (set.is_locked) return <p className="notice success realset-lock" role="status"><strong>🔒 Conjunto cerrado.</strong> No admite estudiantes nuevos, mediciones, evaluaciones, importaciones ni cambios de seguimiento. Solo se consulta.</p>;
  async function close() {
    await command.run(async () => {
      await api.updatePeriod(period.id, { code: period.code, school_year: period.school_year, start_date: period.start_date, end_date: period.end_date,
        data_origin: period.data_origin, creation_key: command.key, is_locked: true, expected_version: period.version });
      setConfirming(false);
      await cache.invalidateQueries();
    });
  }
  return <div className="notice error realset-lock" role="status"><strong>🔓 Conjunto abierto.</strong> Todavía admite cambios. Ciérralo para que nadie lo modifique durante la demostración.
    {user.role === 'ADMIN' && <><CommandErrors command={command} />{confirming ? <div className="realset-confirm"><p>¿Cerrar {period.code}? Solo un administrador podrá reabrirlo desde Estudiantes → Periodos.</p><button className="button primary" type="button" disabled={command.busy} onClick={() => void close()}>{command.busy ? 'Cerrando…' : 'Confirmar cierre'}</button><button className="button secondary" type="button" disabled={command.busy} onClick={() => setConfirming(false)}>Cancelar</button></div> : <div><button className="button primary" type="button" onClick={() => setConfirming(true)}>Cerrar conjunto</button></div>}</>}
  </div>;
}
