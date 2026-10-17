import { useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, type Period, type Snapshot, type Student, type User, type MeasurementCreate } from '../../lib/api';
import { timestampLabel, numberLabel } from '../../lib/format';
import { EmptyState, ErrorState, EvaluationBadge, LoadingState, Pagination, RiskBadge } from '../../components/ui';
import { CommandErrors, Field, FormButtons, useCommand } from './ManualForms';

const variables = [
  ['average_grade', 'Promedio · 0–20', 0, 20, '0.01'], ['attendance_pct', 'Asistencia · 0–100 %', 0, 100, '0.01'],
  ['activities_pct', 'Entrega de actividades · 0–100 %', 0, 100, '0.01'], ['participation_level', 'Participación · 1–5', 1, 5, '1'],
  ['behavior_incidents', 'Incidencias · entero ≥ 0', 0, 2147483647, '1'],
] as const;
type Feature = typeof variables[number][0];
function limaInput(value?: string | null) {
  if (!value) return '';
  const parts = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).format(new Date(value));
  return parts.replace(' ', 'T');
}
function toInstant(value: string) { return value + '-05:00'; }

export function MeasurementForm({ student, period, prior, done, cancel }: { student: Student; period: Period; prior?: Snapshot; done: () => void; cancel: () => void }) {
  const command = useCommand();
  const [dates, setDates] = useState({ window_start: prior?.window_start ?? period.start_date, cutoff_at: limaInput(prior?.cutoff_at), available_at: limaInput(prior?.available_at) });
  const [values, setValues] = useState(() => Object.fromEntries(variables.map(([key]) => [key, prior?.[key] == null ? '' : String(prior[key])])) as Record<Feature, string>);
  const [availability, setAvailability] = useState(() => Object.fromEntries(variables.map(([key]) => [key, limaInput(prior?.variable_available_at?.[key])])) as Record<Feature, string>);
  const [distinct, setDistinct] = useState(() => !!prior && Object.values(prior.variable_available_at ?? {}).some(at => Date.parse(at) !== Date.parse(prior.available_at)));
  const [purpose, setPurpose] = useState<MeasurementCreate['purpose']>(prior?.purpose ?? 'PARTIAL');
  const [reason, setReason] = useState('');
  const [base, setBase] = useState(prior);
  function submit(e: FormEvent) { e.preventDefault(); void command.run(async () => {
    const body: MeasurementCreate = { creation_key: command.key, window_start: dates.window_start, cutoff_at: prior?.cutoff_at ?? toInstant(dates.cutoff_at), available_at: toInstant(dates.available_at), purpose,
      ...Object.fromEntries(variables.map(([key]) => [key, values[key] === '' ? null : Number(values[key])])),
      variable_available_at: Object.fromEntries(variables.filter(([key]) => values[key] !== '' && distinct && availability[key]).map(([key]) => [key, toInstant(availability[key])])),
      ...(base ? { supersedes_id: base.id, expected_revision: base.revision, correction_reason: reason } : {}) };
    await api.createMeasurement(student.id, period.id, body); done();
  }); }
  return <form className="m1-form" onSubmit={submit}><h3>{prior ? 'Corregir medición' : 'Nueva medición'}</h3><p className="muted">Fechas observadas en America/Lima. La fecha de digitación y el autor se registran ahora en el servidor. Vacío significa sin dato; cero conserva su valor.</p><CommandErrors command={command} />
    <div className="m1-grid"><Field name="purpose" label="Tipo de información" error={command.error}><select id="m1-purpose" name="purpose" value={purpose} onChange={e => setPurpose(e.target.value as MeasurementCreate['purpose'])}><option value="PARTIAL">Medición parcial · seguimiento durante el periodo</option><option value="CLOSING_REFERENCE">Información de cierre / referencia</option></select></Field>
      <Field name="window_start" label="Inicio de la ventana observada" error={command.error}><input autoFocus id="m1-window_start" name="window_start" type="date" min={period.start_date} max={period.end_date} required value={dates.window_start} onChange={e => setDates({ ...dates, window_start: e.target.value })} /></Field>
      <Field name="cutoff_at" label="Fecha y hora de corte · Lima" error={command.error}><input id="m1-cutoff_at" name="cutoff_at" type="datetime-local" step="1" required disabled={!!prior} value={dates.cutoff_at} onChange={e => setDates({ ...dates, cutoff_at: e.target.value })} /></Field>
      <Field name="available_at" label="Todo lo informado estaba disponible desde · Lima" error={command.error}><input id="m1-available_at" name="available_at" type="datetime-local" step="1" required value={dates.available_at} onChange={e => setDates({ ...dates, available_at: e.target.value })} /></Field></div>
    <p className="notice">{purpose === 'CLOSING_REFERENCE' ? 'El promedio de cierre se conserva como referencia; no es un predictor anterior al cierre.' : 'Registra solo información que ya estaba disponible al corte.'} No se solicita una fecha objetivo: el horizonte lo define el modelo al evaluar y no se guarda como dato observado.</p>
    <fieldset><legend>Mediciones académicas · al menos un dato</legend><div className="m1-grid">{variables.map(([key, base, min, max, step]) => { const label = key === 'participation_level' && period.data_origin === 'SYNTHETIC' ? 'Participación · 1–3 en la simulación' : base; return <Field key={key} name={key} label={label} error={command.error}><input id={`m1-${key}`} name={key} type="number" min={min} max={max} step={step} value={values[key]} onChange={e => setValues({ ...values, [key]: e.target.value })} /></Field>; })}</div></fieldset>
    <label className="m1-check"><input type="checkbox" checked={distinct} onChange={e => setDistinct(e.target.checked)} />Registrar disponibilidades diferentes por variable</label>
    {distinct && <div className="m1-grid">{variables.filter(([key]) => values[key] !== '').map(([key, label]) => <Field key={key} name={`availability-${key}`} label={`Disponible desde: ${label}`}><input id={`m1-availability-${key}`} type="datetime-local" step="1" value={availability[key]} onChange={e => setAvailability({ ...availability, [key]: e.target.value })} /></Field>)}</div>}
    {prior && <Field name="correction_reason" label={`Motivo de corrección · revisión esperada ${base?.revision}`} error={command.error}><textarea id="m1-correction_reason" name="correction_reason" minLength={3} maxLength={1000} required value={reason} onChange={e => setReason(e.target.value)} /></Field>}
    {prior && command.error instanceof ApiError && command.error.status === 409 && <button type="button" className="button secondary" onClick={() => void command.run(async () => { const current = (await api.measurements(student.id, period.id)).items.find(s => s.cutoff_at === prior.cutoff_at); if (current) { setBase(current); command.newKey(); } })}>Consultar revisión actual conservando valores del borrador</button>}
    <FormButtons busy={command.busy} cancel={cancel} label={prior ? 'Guardar nueva revisión' : 'Guardar medición'} /></form>;
}

export function Measurements({ student, period, user }: { student: Student; period: Period; user: User }) {
  const cache = useQueryClient();
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: [user.id, 'measurements', student.id, period.id, page], queryFn: () => api.measurements(student.id, period.id, page), retry: false });
  const [editing, setEditing] = useState<Snapshot | 'new' | null>(null);
  const [notice, setNotice] = useState('');
  const writable = ['ADMIN', 'TUTOR'].includes(user.role) && !period.is_locked && student.is_active !== false;
  return <section className="panel student-detail-panel" aria-labelledby="m1-measurements"><h2 id="m1-measurements">Mediciones</h2><p className="muted">Se conservan todas las revisiones. Registrar o corregir una medición no evalúa el riesgo por sí solo: en periodos sintéticos el administrador puede evaluar la última revisión desde esta ficha (simulación, sin valor de validación académica).</p>{notice && <p role="status" className="notice">{notice}</p>}{query.data && query.data.items.length > 0 && <p className="notice" role="status" aria-live="polite">Estado de la última revisión: <EvaluationBadge status={student.evaluation_status} /> <RiskBadge risk={student.risk_level ?? null} />{student.evaluation_status === 'NOT_EVALUATED' ? (period.data_origin === 'SYNTHETIC' && user.role === 'ADMIN' ? ' Usa «Evaluar riesgo de este estudiante».' : ' Pendiente de evaluación.') : student.evaluation_status === 'INSUFFICIENT_DATA' ? ' No se asigna riesgo.' : ''}</p>}
    {editing ? <MeasurementForm key={editing === 'new' ? 'new' : editing.id} student={student} period={period} prior={editing === 'new' ? undefined : editing} cancel={() => setEditing(null)} done={() => { setEditing(null); setNotice('Medición guardada en el servidor.'); void cache.invalidateQueries(); }} /> : <>{writable && <button type="button" className="button primary" onClick={() => { setEditing('new'); setNotice(''); }}>Nueva medición</button>}{!writable && <p className="muted">{student.is_active === false ? 'Estudiante inactivo: historial disponible para consulta.' : period.is_locked ? 'Periodo bloqueado: solo consulta.' : 'Tu rol permite consultar las mediciones.'}</p>}
    {query.isPending ? <LoadingState /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : query.data.items.length === 0 ? <EmptyState title="Sin mediciones"><p>El alumno ya está matriculado. Sus mediciones aparecerán aquí cuando se guarden.</p></EmptyState> : <><ol className="m1-measurements-list">{query.data.items.map(s => <li key={s.id}><h3>Corte {timestampLabel(s.cutoff_at)} · revisión {s.revision}</h3><p className="muted">{s.entry_channel === 'MANUAL' ? 'Registro manual' : 'Importación CSV'} · {s.purpose === 'CLOSING_REFERENCE' ? 'Cierre / referencia' : 'Medición parcial'} · digitado {timestampLabel(s.created_at ?? null)}</p><dl className="student-data">{variables.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{numberLabel(s[key])}</dd></div>)}</dl><p className="muted">Disponible desde {timestampLabel(s.available_at)}. {s.correction_reason && `Motivo: ${s.correction_reason}`}</p>{s.variable_available_at && Object.entries(s.variable_available_at).length > 0 && <details><summary>Disponibilidad por variable</summary><ul>{variables.filter(([key]) => s.variable_available_at?.[key]).map(([key,label]) => <li key={key}>{label}: {timestampLabel(s.variable_available_at![key])}</li>)}</ul></details>}{writable && <button type="button" className="button secondary" onClick={() => setEditing(s)}>Corregir medición · revisión {s.revision}</button>}</li>)}</ol><Pagination page={page} pageSize={10} total={query.data.total} onPageChange={setPage} /></>}</>}
  </section>;
}

export function StudentAdministration({ student, period }: { student: Student; period: Period }) {
  const command = useCommand();
  const cache = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(student.full_name ?? '');
  const [active, setActive] = useState(student.is_active !== false);
  const [confirmed, setConfirmed] = useState(false);
  const [reason, setReason] = useState('');
  const [expected, setExpected] = useState(student.version ?? 1);
  const [section, setSection] = useState(student.section_id);
  const [enrollmentExpected, setEnrollmentExpected] = useState(student.enrollment_version ?? 1);
  const [notice, setNotice] = useState('');
  const sections = useQuery({ queryKey: ['m1-sections', period.id], queryFn: () => api.sections(period.id), enabled: editing });
  if (!editing) return <div className="student-filter-actions">{notice && <p role="status">{notice}</p>}<button type="button" className="button secondary" disabled={period.is_locked} onClick={() => { setEditing(true); setName(student.full_name ?? ''); setActive(student.is_active !== false); setExpected(student.version ?? 1); setConfirmed(false); setReason(''); }}>Editar datos / {student.is_active === false ? 'reactivar' : 'desactivar'}</button></div>;
  return <section className="panel student-detail-panel"><h2>Administrar estudiante y matrícula</h2><CommandErrors command={command} /><form onSubmit={e => { e.preventDefault(); void command.run(async () => { await api.updateStudent(student.id, { creation_key: command.key, full_name: name, expected_version: expected, is_active: active, confirmed, reason }); setEditing(false); setNotice('Datos actualizados en el servidor.'); void cache.invalidateQueries(); command.newKey(); }); }} className="m1-form">
    <Field name="full_name" label="Nombre completo" error={command.error}><input autoFocus id="m1-full_name" name="full_name" required maxLength={160} value={name} onChange={e => setName(e.target.value)} /></Field><label className="m1-check"><input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} />Estudiante activo</label><p className="muted">Desactivar conserva matrículas, mediciones e historial e impide nuevas escrituras. Reactivar es una decisión explícita.</p><Field name="reason" label="Motivo del cambio" error={command.error}><textarea id="m1-reason" name="reason" required minLength={3} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></Field><label className="m1-check"><input type="checkbox" required checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Confirmo este cambio de datos y estado</label><FormButtons busy={command.busy} cancel={() => setEditing(false)} label="Confirmar cambio del estudiante" /></form>
    {command.error instanceof ApiError && command.error.status === 409 && <button type="button" className="button secondary" onClick={() => void command.run(async () => { const current = await api.student(student.id, period.id); setExpected(current.student.version ?? 1); setEnrollmentExpected(current.student.enrollment_version ?? 1); command.newKey(); })}>Consultar versión actual conservando borrador</button>}
    <form className="m1-form" onSubmit={e => { e.preventDefault(); void command.run(async () => { await api.updateEnrollment(student.enrollment_id, { creation_key: command.key, expected_version: enrollmentExpected, section_id: section }); setEditing(false); setNotice('Matrícula actualizada en el servidor.'); void cache.invalidateQueries(); command.newKey(); }); }}><h3>Sección de la matrícula</h3><p className="muted">Solo se permite cambiar sección si no existen mediciones. Con mediciones, el historial conserva su sección.</p>{sections.isError && <ErrorState error={sections.error} />}
    <Field name="section_id" label="Grado / sección"><select id="m1-section_id" name="section_id" required value={section} onChange={e => setSection(e.target.value)}>{sections.data?.map(g => <option key={g.id} value={g.id}>{g.grade}.º / {g.code}</option>)}</select></Field><FormButtons busy={command.busy} submitDisabled={!sections.data} cancel={() => setEditing(false)} label="Guardar matrícula" /></form>
  </section>;
}
