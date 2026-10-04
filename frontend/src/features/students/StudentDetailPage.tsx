import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError, type Period, type Prediction, type StudentDetail, type User } from '../../lib/api';
import { dateLabel, numberLabel, timestampLabel } from '../../lib/format';
import { EmptyState, ErrorState, EvaluationBadge, LoadingState, PageHeader, Pagination, RiskBadge } from '../../components/ui';
import './features.css';
import { AlertStatusBadge, InterventionStatusBadge, interventionKindLabels } from '../alerts/labels';
import '../alerts/features.css';

type Props = { user: User; period: Period | null; studentId: string; onNavigate: (path: string) => void };
const eventNames = { SNAPSHOT: 'Datos incorporados', PREDICTION: 'Evaluación registrada', ALERT: 'Alerta registrada', INTERVENTION: 'Intervención registrada' };
const eventIcons = { SNAPSHOT: '▤', PREDICTION: '◇', ALERT: '△', INTERVENTION: '✓' };

export function StudentDetailPage(props: Props) {
  if (props.user.role === 'RESEARCHER') return <EmptyState title="Consulta no disponible para tu rol"><p>Los registros individuales están reservados al personal autorizado.</p></EmptyState>;
  if (!props.period) return <div className="students-feature"><PageHeader title="Detalle del registro" /><EmptyState title="Selecciona un periodo"><p>El registro se consulta dentro de un periodo autorizado.</p></EmptyState></div>;
  return <StudentRecord key={`${props.user.id}:${props.user.role}:${props.period.id}:${props.studentId}`} {...props} period={props.period} />;
}

function StudentRecord({ user, period, studentId, onNavigate }: Props & { period: Period }) {
  const detail = useQuery({ queryKey: [user.id, user.role, 'student', period.id, studentId],
    queryFn: ({ signal }) => api.student(studentId, period.id, signal), retry: false });
  const backPath = `/estudiantes?period_id=${encodeURIComponent(period.id)}`;
  function back(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(backPath); }
  }
  const backAction = <a className="button secondary" href={backPath} onClick={back}>← Volver a estudiantes</a>;
  if (detail.isPending) return <div className="students-feature"><PageHeader title="Detalle del registro" action={backAction} /><LoadingState label="Consultando el registro…" /></div>;
  if (detail.isError) return <div className="students-feature"><PageHeader title="Detalle del registro" action={backAction} />{detail.error instanceof ApiError && [403, 404].includes(detail.error.status) ?
    <EmptyState title="Este registro no está disponible"><p>Consulta los registros autorizados del periodo seleccionado.</p></EmptyState> : <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />}</div>;
  const { student, latest_snapshot: snapshot, latest_prediction: latestPrediction } = detail.data;
  const prediction = snapshot && latestPrediction?.snapshot_id === snapshot.id ? latestPrediction : null;
  return <div className="students-feature">
    <PageHeader title={student.anon_code} eyebrow="REGISTRO DEL ESTUDIANTE" description={`Periodo ${period.code} · ${student.grade} / ${student.section_code}`} action={backAction} />
    <div className="student-detail-grid">
      <section className="panel student-detail-panel" aria-labelledby="student-context-title"><h2 id="student-context-title">Contexto del registro</h2><dl className="student-data"><div><dt>Código</dt><dd>{student.anon_code}</dd></div><div><dt>Periodo</dt><dd>{period.code}</dd></div><div><dt>Grado</dt><dd>{student.grade}</dd></div><div><dt>Sección</dt><dd>{student.section_code}</dd></div><div><dt>Origen</dt><dd>{student.data_origin === 'SYNTHETIC' ? 'Datos sintéticos' : 'Datos institucionales'}</dd></div><div><dt>Último corte</dt><dd>{timestampLabel(student.latest_cutoff_at)}</dd></div></dl></section>
      <section className="panel student-detail-panel" aria-labelledby="student-evaluation-title"><h2 id="student-evaluation-title">Última evaluación</h2><div className="student-evaluation-badges"><EvaluationBadge status={student.evaluation_status} /><RiskBadge risk={prediction?.risk_level ?? null} /></div>
        {prediction ? <PredictionFields prediction={prediction} /> : <p className="muted">{student.evaluation_status === 'INSUFFICIENT_DATA' ? 'Datos insuficientes para estimar el riesgo de este corte. Se conserva sin estimación.' : snapshot ? 'El corte actual está pendiente de evaluación. Una evaluación anterior no se aplica a esta revisión.' : 'Todavía no hay datos observados para evaluar este registro.'}</p>}
      </section>
    </div>
    <section className="panel student-detail-panel" aria-labelledby="student-observed-title"><h2 id="student-observed-title">Datos observados</h2>{snapshot ? <>
      <dl className="student-data"><div><dt>Promedio</dt><dd>{numberLabel(snapshot.average_grade)}</dd></div><div><dt>Asistencia</dt><dd>{numberLabel(snapshot.attendance_pct, ' %')}</dd></div><div><dt>Actividades</dt><dd>{numberLabel(snapshot.activities_pct, ' %')}</dd></div><div><dt>Participación · categoría registrada</dt><dd>{numberLabel(snapshot.participation_level)}</dd></div><div><dt>Incidencias</dt><dd>{numberLabel(snapshot.behavior_incidents)}</dd></div><div><dt>Edad registrada</dt><dd>{numberLabel(snapshot.age_years, ' años')}</dd></div></dl>
      <h3>Ventana de observación</h3><dl className="student-data"><div><dt>Inicio de ventana</dt><dd>{dateLabel(snapshot.window_start)}</dd></div><div><dt>Fecha de corte</dt><dd>{timestampLabel(snapshot.cutoff_at)}</dd></div><div><dt>Datos disponibles desde</dt><dd>{timestampLabel(snapshot.available_at)}</dd></div><div><dt>Fecha objetivo</dt><dd>{dateLabel(snapshot.target_date)}</dd></div><div><dt>Revisión</dt><dd>{snapshot.revision}</dd></div><div><dt>Variables sin dato</dt><dd>{numberLabel(snapshot.missing_fraction * 100, ' %')}</dd></div></dl>
      <p className="muted student-list-note">“Sin dato” indica que el valor no fue informado. Las horas se muestran en America/Lima; las fechas de ventana y objetivo conservan su día.</p>
    </> : <EmptyState title="Sin datos observados"><p>No hay un corte disponible para este registro en el periodo seleccionado.</p></EmptyState>}</section>
    <RelatedRecords detail={detail.data} period={period} user={user} onNavigate={onNavigate} />
    <StudentHistory user={user} period={period} studentId={studentId} onNavigate={onNavigate} />
  </div>;
}

function PredictionFields({ prediction }: { prediction: Prediction }) {
  const calibrated = prediction.probabilities_calibrated && prediction.probability_low !== null && prediction.probability_medium !== null && prediction.probability_high !== null;
  return <><dl className="student-data"><div><dt>Evaluación registrada</dt><dd>{timestampLabel(prediction.predicted_at)}</dd></div><div><dt>Corte evaluado</dt><dd>{timestampLabel(prediction.cutoff_at)}</dd></div><div><dt>Fecha objetivo</dt><dd>{dateLabel(prediction.target_date)}</dd></div></dl>
    {calibrated ? <><h3>Probabilidades calibradas</h3><dl className="student-data"><div><dt>Bajo</dt><dd>{numberLabel(prediction.probability_low! * 100, ' %')}</dd></div><div><dt>Medio</dt><dd>{numberLabel(prediction.probability_medium! * 100, ' %')}</dd></div><div><dt>Alto</dt><dd>{numberLabel(prediction.probability_high! * 100, ' %')}</dd></div></dl></> : <p className="muted student-list-note">Esta evaluación no dispone de probabilidades calibradas. El nivel estimado no expresa un porcentaje de certeza.</p>}
  </>;
}

function StudentHistory({ user, period, studentId, onNavigate }: { user: User; period: Period; studentId: string; onNavigate: (path: string) => void }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [predictionId, setPredictionId] = useState<string | null>(null);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const detailTrigger = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (predictionId) detailHeading.current?.focus(); }, [predictionId]);
  const timeline = useQuery({ queryKey: [user.id, user.role, 'timeline', period.id, studentId, page, pageSize],
    queryFn: ({ signal }) => api.timeline(studentId, { period_id: period.id, page, page_size: pageSize }, signal), retry: false });
  const historical = useQuery({ queryKey: [user.id, user.role, 'prediction', period.id, predictionId],
    queryFn: ({ signal }) => api.prediction(predictionId!, signal), enabled: predictionId !== null, retry: false });
  return <section className="panel student-detail-panel" aria-labelledby="student-history-title"><h2 id="student-history-title">Historial</h2><p className="muted">Cortes, evaluaciones y cambios efectivos de seguimiento, con sus fechas de registro. Una nueva revisión conserva la evidencia anterior.</p>
    <div className="student-history-page-size"><label htmlFor="student-history-page-size">Eventos por página</label><select id="student-history-page-size" value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1); setPredictionId(null); }}>{[5, 10, 20].map(value => <option key={value} value={value}>{value}</option>)}</select></div>
    {predictionId && <section className="student-historical-prediction" aria-label="Detalle de la evaluación del historial"><header><h3 ref={detailHeading} tabIndex={-1}>Evaluación del historial</h3><button className="button secondary" type="button" onClick={() => { setPredictionId(null); detailTrigger.current?.focus(); }}>Cerrar detalle</button></header>{historical.isPending ? <LoadingState label="Consultando evaluación…" /> : historical.isError ? historical.error instanceof ApiError && [403, 404].includes(historical.error.status) ? <p className="muted">Esta evaluación no está disponible para tu cuenta.</p> : <ErrorState error={historical.error} onRetry={() => void historical.refetch()} /> : <><RiskBadge risk={historical.data.risk_level} /><div className="student-prediction-fields"><PredictionFields prediction={historical.data} /></div><p className="muted student-list-note">Este resultado corresponde al corte indicado. No sustituye la evaluación de una revisión posterior.</p></>}</section>}
    {timeline.isPending ? <LoadingState label="Consultando historial…" /> : timeline.isError ? <ErrorState error={timeline.error} onRetry={() => void timeline.refetch()} /> : timeline.data.items.length === 0 ? <EmptyState title="El historial todavía está vacío"><p>Los eventos aparecerán cuando se registren datos o evaluaciones.</p></EmptyState> : <>
      <ol className="student-history-list">{timeline.data.items.map(event => <li key={event.id}><span className="student-history-icon" aria-hidden="true">{eventIcons[event.event_type]}</span><div className="student-history-body"><strong>{eventNames[event.event_type]}</strong><time dateTime={event.occurred_at}>{timestampLabel(event.occurred_at)}</time><p>{event.summary}</p>{event.event_type === 'PREDICTION' && <button className="button secondary" type="button" onClick={click => { detailTrigger.current = click.currentTarget; setPredictionId(event.entity_id); }} aria-expanded={predictionId === event.entity_id}>Consultar evaluación</button>}{event.event_type === 'ALERT' && <button className="button secondary" type="button" onClick={() => onNavigate(`/alertas/${encodeURIComponent(event.entity_id)}?period_id=${encodeURIComponent(period.id)}`)}>Consultar caso</button>}</div></li>)}</ol>
      <Pagination page={timeline.data.page} pageSize={timeline.data.page_size} total={timeline.data.total} onPageChange={value => { setPage(value); setPredictionId(null); }} />
    </>}
  </section>;
}

function RelatedRecords({ detail, period, user, onNavigate }: { detail: StudentDetail; period: Period; user: User; onNavigate: (path: string) => void }) {
  function open(event: MouseEvent<HTMLAnchorElement>, path: string) { if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey) { event.preventDefault(); onNavigate(path); } }
  return <section className="panel student-detail-panel"><h2>Seguimiento registrado</h2><p className="muted">{user.role === 'DIRECTOR' ? 'Consulta los casos y actividades de simulación. Tu rol mantiene acceso de lectura.' : 'Abre el caso para planificar y registrar actividades autorizadas. Cada actividad mantiene su propio estado.'}</p>
    {!detail.alerts.length && !detail.interventions.length && <EmptyState title="Sin seguimiento registrado"><p>No hay casos ni actividades para esta matrícula. Una evaluación pendiente o insuficiente no se reemplaza por riesgo bajo.</p></EmptyState>}
    {detail.alerts.length > 0 && <><h3>Casos</h3><ul className="student-related-list">{detail.alerts.map(alert => { const path = `/alertas/${alert.id}?period_id=${encodeURIComponent(period.id)}`; return <li key={alert.id}><AlertStatusBadge status={alert.status} /><RiskBadge risk={alert.severity} /><p>Apertura: {timestampLabel(alert.opened_at)}</p>{alert.resolution_reason && <p>{alert.resolution_reason}</p>}<a className="followup-link" href={path} onClick={event => open(event, path)}>Consultar caso{user.role !== 'DIRECTOR' && (alert.status === 'OPEN' || alert.status === 'IN_REVIEW') ? ' y gestionar actividades' : ''} →</a></li>; })}</ul></>}
    {detail.interventions.length > 0 && <><h3>Actividades</h3><ul className="student-related-list">{detail.interventions.map(intervention => { const path = intervention.alert_id ? `/alertas/${intervention.alert_id}?period_id=${encodeURIComponent(period.id)}` : null; return <li key={intervention.id}><strong>{interventionKindLabels[intervention.kind]}</strong> <InterventionStatusBadge status={intervention.status} /><p>{intervention.objective}</p><p>Programada: {timestampLabel(intervention.scheduled_at)}</p><p>Fecha efectiva: {intervention.performed_at ? timestampLabel(intervention.performed_at) : 'No realizada'}</p>{path && <a className="followup-link" href={path} onClick={event => open(event, path)}>Consultar actividad en su caso →</a>}</li>; })}</ul></>}
  </section>;
}
