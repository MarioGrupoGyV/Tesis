import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, currentEvaluationInstant, type Alert, type AlertCase, type AlertDetail, type AlertPatch, type Intervention, type InterventionCreate, type InterventionPatch, type InterventionView, type User } from '../../lib/api';
import { ErrorState } from '../../components/ui';
import { timestampLabel } from '../../lib/format';
import { alertStatusLabels, interventionKindLabels, interventionStatusLabels, limaInputTimestamp, timestampLimaInput } from './labels';
import { ConflictReview, useFollowupWrite } from './formState';

type Refresh = () => Promise<AlertDetail | null>;
type Common = { user: User; available: boolean; blocked: string; onRefresh: Refresh };

function useReview(onRefresh: Refresh) {
  const [refreshing, setRefreshing] = useState(false);
  const [refreshed, setRefreshed] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  async function review(accept: (detail: AlertDetail) => void) {
    setRefreshing(true); setReviewed(false); setRefreshed(false);
    try { const value = await onRefresh(); if (alive.current && value) { accept(value); setRefreshed(true); } }
    finally { if (alive.current) setRefreshing(false); }
  }
  function reset() { setReviewed(false); setRefreshed(false); }
  return { refreshing, refreshed, reviewed, setReviewed, review, reset };
}

export function AlertStateForm({ user, alert, available, blocked, onRefresh }: Common & { alert: AlertCase }) {
  const [status, setStatus] = useState<Alert['status']>(alert.status === 'OPEN' ? 'IN_REVIEW' : 'RESOLVED');
  const [reason, setReason] = useState('');
  const [version, setVersion] = useState(alert.version);
  const [validation, setValidation] = useState('');
  const write = useFollowupWrite(user);
  const review = useReview(onRefresh);
  const closed = status === 'RESOLVED' || status === 'DISMISSED';
  const allowed = alert.status === 'OPEN' ? ['IN_REVIEW', 'RESOLVED', 'DISMISSED'] as const : alert.status === 'IN_REVIEW' ? ['RESOLVED', 'DISMISSED'] as const : [];
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!available || write.pending || write.conflict && !review.reviewed) return;
    if (closed && !reason.trim()) { setValidation('Explica el motivo antes de concluir o descartar el caso.'); return; }
    if (!allowed.includes(status as never)) { setValidation('Elige una transición disponible para el estado actualizado.'); return; }
    setValidation('');
    const payload: AlertPatch = { expected_version: version, status, resolution_reason: closed ? reason.trim() : null };
    await write.submit(signal => api.updateAlert(alert.id, payload, signal), result => {
      setVersion(result.alert.version); review.reset();
      setStatus(result.alert.status === 'OPEN' ? 'IN_REVIEW' : 'RESOLVED'); setReason('');
      write.setSuccess(result.alert.status === 'IN_REVIEW' ? 'Caso en revisión. La evidencia previa se conserva.' : 'Estado guardado. Las actividades conservan su propio estado.');
    });
  }
  return <section aria-labelledby="case-state-title"><h3 id="case-state-title">Cambiar estado</h3><p className="muted">Planifica y registra la actividad por separado. Concluir significa seguimiento terminado en esta simulación, sin afirmar una mejoría académica.</p>
    {!available && <p className="notice" role="status">{blocked}</p>}
    <form className="followup-form" onSubmit={submit}><fieldset disabled={!available || write.pending}><div><label htmlFor="case-next-status">Estado del caso</label><select id="case-next-status" value={status} onChange={event => { setStatus(event.target.value as Alert['status']); setValidation(''); }} required>{(['IN_REVIEW', 'RESOLVED', 'DISMISSED'] as const).map(value => <option key={value} value={value} disabled={!allowed.includes(value as never)}>{alertStatusLabels[value]}</option>)}</select></div>{closed && <div><label htmlFor="case-close-reason">Motivo de cierre</label><textarea id="case-close-reason" maxLength={1000} required value={reason} onChange={event => { setReason(event.target.value); setValidation(''); }} rows={3} /><p className="muted">Hasta 1000 caracteres. Describe la decisión de simulación; no incluyas datos personales.</p></div>}</fieldset>
      {validation && <p className="notice error" role="alert">{validation}</p>}
      {Boolean(write.error) && <ErrorState error={write.error} />}
      {write.conflict && <ConflictReview subject="caso" {...review} onReviewed={review.setReviewed} onRefresh={() => void review.review(value => setVersion(value.alert.version))} />}
      {write.uncertain && <div className="notice" role="status"><strong>Resultado sin confirmar</strong><p>Consulta el caso antes de repetir. Si la acción ya se guardó, conserva el estado actualizado.</p><button className="button secondary" type="button" disabled={review.refreshing} onClick={() => void review.review(value => setVersion(value.alert.version))}>Consultar estado del caso</button></div>}
      <div className="followup-actions"><button className="button primary" type="submit" disabled={!available || write.pending || write.conflict && !review.reviewed}>{write.pending ? 'Guardando estado…' : 'Guardar estado'}</button><p className="muted">Estado registrado: {alertStatusLabels[alert.status]}. Actualización: {timestampLabel(alert.updated_at)}</p></div>
      {write.success && <p className="notice success" role="status">{write.success}</p>}
    </form>
  </section>;
}

type ActivityDraft = { kind: Intervention['kind']; objective: string; scheduled: string; notes: string };
const emptyActivity: ActivityDraft = { kind: 'TUTORING', objective: '', scheduled: '', notes: '' };

export function PlanActivityForm({ user, alert, available, blocked, onRefresh }: Common & { alert: AlertCase }) {
  const [draft, setDraft] = useState<ActivityDraft>(emptyActivity);
  const [version, setVersion] = useState(alert.version);
  const [validation, setValidation] = useState('');
  const key = useRef(crypto.randomUUID());
  const originalPayload = useRef<InterventionCreate | null>(null);
  const [uncertainAttempt, setUncertainAttempt] = useState(false);
  const write = useFollowupWrite(user);
  const review = useReview(onRefresh);
  function edit(next: ActivityDraft) {
    setDraft(next); setValidation('');
    key.current = crypto.randomUUID(); originalPayload.current = null; setUncertainAttempt(false);
    if (!write.conflict) write.setError(null); write.setSuccess(''); review.reset();
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!available || write.pending || write.conflict && !review.reviewed) return;
    const scheduled = limaInputTimestamp(draft.scheduled);
    if (!draft.objective.trim() || !scheduled) { setValidation('Indica un objetivo y una fecha y hora programadas válidas en Lima.'); return; }
    setValidation('');
    const payload = originalPayload.current ?? { alert_id: alert.id, expected_alert_version: version, creation_key: key.current, kind: draft.kind, objective: draft.objective.trim(), scheduled_at: scheduled, notes: draft.notes.trim() || null } satisfies InterventionCreate;
    originalPayload.current = payload;
    await write.submit(signal => api.createIntervention(payload, signal), result => {
      setDraft(emptyActivity); key.current = crypto.randomUUID(); originalPayload.current = null; setUncertainAttempt(false); review.reset();
      write.setSuccess(result.reused_result ? 'La actividad ya estaba registrada. Se reutilizó el mismo intento sin duplicarla.' : 'Actividad planificada. Aún no cuenta como realizada.');
    });
  }
  useEffect(() => { if (write.uncertain) setUncertainAttempt(true); }, [write.uncertain]);
  return <section aria-labelledby="plan-activity-title"><h2 id="plan-activity-title">Planificar actividad</h2><p className="muted">Describe una actividad de seguimiento simulada. Registrar una reunión familiar aquí no envía invitaciones ni contacta a personas.</p>{!available && <p className="notice" role="status">{blocked}</p>}
    <form className="followup-form" onSubmit={submit}><fieldset disabled={!available || write.pending}><div><label htmlFor="plan-kind">Tipo de actividad</label><select id="plan-kind" value={draft.kind} onChange={event => edit({ ...draft, kind: event.target.value as ActivityDraft['kind'] })}>{Object.entries(interventionKindLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div><div><label htmlFor="plan-objective">Objetivo</label><textarea id="plan-objective" value={draft.objective} maxLength={1000} required rows={3} onChange={event => edit({ ...draft, objective: event.target.value })} /><p className="muted">Hasta 1000 caracteres. Mantén el objetivo concreto y sin datos personales.</p></div><div><label htmlFor="plan-scheduled">Fecha y hora programadas (Lima)</label><input id="plan-scheduled" type="datetime-local" value={draft.scheduled} required onChange={event => edit({ ...draft, scheduled: event.target.value })} /><p className="muted">America/Lima, UTC−05:00. Esta fecha no se copia como fecha efectiva.</p></div><div><label htmlFor="plan-notes">Notas opcionales</label><textarea id="plan-notes" value={draft.notes} maxLength={2000} rows={3} onChange={event => edit({ ...draft, notes: event.target.value })} /><p className="muted">Hasta 2000 caracteres.</p></div></fieldset>
      {validation && <p className="notice error" role="alert">{validation}</p>}{Boolean(write.error) && <ErrorState error={write.error} />}
      {write.conflict && <ConflictReview subject="caso" {...review} onReviewed={review.setReviewed} onRefresh={() => void review.review(value => { setVersion(value.alert.version); key.current = crypto.randomUUID(); originalPayload.current = null; setUncertainAttempt(false); })} />}
      {uncertainAttempt && <div className="notice" role="status"><strong>Resultado sin confirmar</strong><p>Consulta las actividades antes de repetir. Si mantienes el mismo formulario, se conserva la clave de este intento para evitar duplicados. Si cambias el contenido, será una intención nueva.</p><button className="button secondary" type="button" disabled={review.refreshing} onClick={() => void review.review(() => undefined)}>Consultar actividades registradas</button></div>}
      <div className="followup-actions"><button className="button primary" type="submit" disabled={!available || write.pending || write.conflict && !review.reviewed}>{write.pending ? 'Planificando…' : uncertainAttempt ? 'Repetir el mismo intento de planificación' : 'Planificar actividad'}</button></div>{write.success && <p className="notice success" role="status">{write.success}</p>}
    </form>
  </section>;
}

export function ActivityEditForm({ user, intervention, available, blocked, onRefresh, onClose }: Common & { intervention: InterventionView; onClose: () => void }) {
  const [draft, setDraft] = useState<ActivityDraft>({ kind: intervention.kind, objective: intervention.objective, scheduled: timestampLimaInput(intervention.scheduled_at), notes: intervention.notes ?? '' });
  const [status, setStatus] = useState<Intervention['status']>('PLANNED');
  const [performed, setPerformed] = useState('');
  const [version, setVersion] = useState(intervention.version);
  const [validation, setValidation] = useState('');
  const write = useFollowupWrite(user);
  const review = useReview(onRefresh);
  const prefix = `activity-${intervention.id}`;
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!available || write.pending || write.conflict && !review.reviewed) return;
    const scheduled = limaInputTimestamp(draft.scheduled);
    const performedAt = status === 'DONE' ? limaInputTimestamp(performed) : null;
    if (!draft.objective.trim() || !scheduled) { setValidation('Indica un objetivo y una fecha programada válidos.'); return; }
    if (status === 'DONE' && !performedAt) { setValidation('Una actividad realizada exige su fecha y hora efectiva en Lima.'); return; }
    if (performedAt) {
      const observedNow = currentEvaluationInstant();
      if (!observedNow) { setValidation('No pudimos comprobar la hora del sistema. Consulta el caso nuevamente antes de registrar la realización.'); return; }
      if (new Date(performedAt).getTime() > observedNow.getTime()) { setValidation('La fecha efectiva no puede estar en el futuro respecto del sistema.'); return; }
    }
    setValidation('');
    const payload: InterventionPatch = { expected_version: version, status, ...(performedAt ? { performed_at: performedAt } : {}) };
    if (draft.kind !== intervention.kind) payload.kind = draft.kind;
    if (draft.objective.trim() !== intervention.objective) payload.objective = draft.objective.trim();
    if (draft.scheduled !== timestampLimaInput(intervention.scheduled_at)) payload.scheduled_at = scheduled;
    if (draft.notes.trim() !== (intervention.notes ?? '')) payload.notes = draft.notes.trim() || null;
    await write.submit(signal => api.updateIntervention(intervention.id, payload, signal), result => {
      setVersion(result.version); review.reset(); write.setSuccess(result.status === 'DONE' ? 'Actividad registrada como realizada en la simulación, con fecha efectiva explícita.' : result.status === 'CANCELLED' ? 'Actividad cancelada. No cuenta como realizada.' : 'Planificación actualizada. Aún no cuenta como realizada.');
    });
  }
  return <form className="followup-form" onSubmit={submit} aria-label="Registrar actividad"><fieldset disabled={!available || write.pending}><legend>Registrar actividad</legend><div><label htmlFor={`${prefix}-status`}>Estado de actividad</label><select id={`${prefix}-status`} value={status} onChange={event => { setStatus(event.target.value as Intervention['status']); setValidation(''); }}><option value="PLANNED">Planificada</option><option value="DONE">Realizada</option><option value="CANCELLED">Cancelada</option></select></div><div><label htmlFor={`${prefix}-kind`}>Tipo de actividad</label><select id={`${prefix}-kind`} value={draft.kind} onChange={event => setDraft({ ...draft, kind: event.target.value as ActivityDraft['kind'] })}>{Object.entries(interventionKindLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div><div><label htmlFor={`${prefix}-objective`}>Objetivo</label><textarea id={`${prefix}-objective`} maxLength={1000} required value={draft.objective} rows={3} onChange={event => setDraft({ ...draft, objective: event.target.value })} /></div><div><label htmlFor={`${prefix}-scheduled`}>Fecha y hora programadas (Lima)</label><input id={`${prefix}-scheduled`} type="datetime-local" required value={draft.scheduled} onChange={event => setDraft({ ...draft, scheduled: event.target.value })} /></div>{status === 'DONE' && <div><label htmlFor={`${prefix}-performed`}>Fecha y hora efectiva (Lima)</label><input id={`${prefix}-performed`} type="datetime-local" required value={performed} onChange={event => setPerformed(event.target.value)} /><p className="muted">Indica cuándo se realizó la actividad simulada. No puede ser futura; el sistema valida su propio reloj. No se copia la fecha programada.</p></div>}<div><label htmlFor={`${prefix}-notes`}>Notas o evidencia de la actividad</label><textarea id={`${prefix}-notes`} maxLength={2000} value={draft.notes} rows={3} onChange={event => setDraft({ ...draft, notes: event.target.value })} /><p className="muted">Hasta 2000 caracteres. Describe únicamente la simulación, sin datos personales.</p></div></fieldset>
    {!available && <p className="notice" role="status">{blocked}</p>}{validation && <p className="notice error" role="alert">{validation}</p>}{Boolean(write.error) && <ErrorState error={write.error} />}
    {write.conflict && <ConflictReview subject="actividad" {...review} onReviewed={review.setReviewed} onRefresh={() => void review.review(detail => { const current = detail.interventions.find(item => item.id === intervention.id); if (current) setVersion(current.version); })} />}
    {write.uncertain && <div className="notice" role="status"><strong>Resultado sin confirmar</strong><p>Consulta la actividad antes de repetir y revisa el estado registrado.</p><button className="button secondary" type="button" disabled={review.refreshing} onClick={() => void review.review(detail => { const current = detail.interventions.find(item => item.id === intervention.id); if (current) setVersion(current.version); })}>Consultar estado de actividad</button></div>}
    <div className="followup-actions"><button className="button primary" type="submit" disabled={!available || write.pending || write.conflict && !review.reviewed}>{write.pending ? 'Guardando actividad…' : 'Guardar actividad'}</button><button className="button secondary" type="button" disabled={write.pending} onClick={onClose}>Cerrar formulario</button><p className="muted">Estado registrado: {interventionStatusLabels[intervention.status]}.</p></div>{write.success && <p className="notice success" role="status">{write.success}</p>}
  </form>;
}
