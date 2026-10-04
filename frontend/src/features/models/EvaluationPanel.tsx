import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, currentEvaluationInstant, type Period, type ProcessingStatus, type User } from '../../lib/api';
import { numberLabel, reasonLabel, timestampLabel } from '../../lib/format';
import { ErrorState } from '../../components/ui';

type Props = { user: User; period: Period | null; processing: ProcessingStatus | null; onNavigate: (path: string) => void };

export function EvaluationPanel(props: Props) {
  return <PeriodEvaluation key={`${props.user.id}:${props.user.role}:${props.period?.id ?? 'none'}`} {...props} />;
}

function PeriodEvaluation({ user, period, processing, onNavigate }: Props) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<'now' | 'manual'>('now');
  const [manual, setManual] = useState('');
  const [validation, setValidation] = useState<string | null>(null);
  const requestController = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const validationMessage = useRef<HTMLParagraphElement>(null);
  const responseSummary = useRef<HTMLDivElement>(null);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; requestController.current?.abort(); };
  }, []);
  const operation = processing?.operations.predict;
  const available = user.role === 'ADMIN' && Boolean(operation?.available) && period?.data_origin === 'SYNTHETIC' && !period.is_locked;
  const mutation = useMutation({ mutationFn: (asOf: string) => {
    requestController.current?.abort();
    const controller = new AbortController(); requestController.current = controller;
    return api.runPredictions({ period_id: period!.id, as_of: asOf }, controller.signal);
  }, retry: false, onSuccess: () => {
    if (mounted.current && !requestController.current?.signal.aborted) return queryClient.invalidateQueries({ queryKey: [user.id, user.role] });
  } });
  useEffect(() => { if (validation) validationMessage.current?.focus(); }, [validation]);
  useEffect(() => { if (mutation.isSuccess || mutation.isError) responseSummary.current?.focus(); }, [mutation.isSuccess, mutation.isError]);
  let blocked: string | null = null;
  if (!period) blocked = 'Selecciona el periodo que deseas evaluar.';
  else if (period.data_origin !== 'SYNTHETIC') blocked = reasonLabel('INSTITUTIONAL_PROCESSING_NOT_READY');
  else if (period.is_locked) blocked = reasonLabel('PERIOD_LOCKED');
  else if (!processing) blocked = 'No pudimos comprobar la preparación del módulo. La evaluación permanecerá deshabilitada hasta consultar su estado.';
  else if (!operation?.available) blocked = reasonLabel(operation?.reason);
  else if (user.role !== 'ADMIN') blocked = reasonLabel('FORBIDDEN');

  function evaluate(event: FormEvent) {
    event.preventDefault();
    if (!available || mutation.isPending) return;
    setValidation(null);
    const instant = mode === 'now' ? currentEvaluationInstant() : new Date(`${manual}:00-05:00`);
    if (!instant) { setValidation('No pudimos consultar la hora del sistema. Actualiza la vista o elige una fecha y hora en Lima.'); return; }
    if (!manual && mode === 'manual' || Number.isNaN(instant.getTime())) { setValidation('Indica una fecha y hora válidas en America/Lima.'); return; }
    const observedNow = currentEvaluationInstant();
    if (mode === 'manual' && observedNow && instant.getTime() > observedNow.getTime()) { setValidation('La fecha de evaluación no puede estar en el futuro.'); return; }
    mutation.mutate(instant.toISOString());
  }
  return <section className="panel model-evaluation-panel" aria-labelledby="model-evaluate-title"><div className="model-panel-heading"><div><p className="eyebrow">EVALUACIÓN SINTÉTICA</p><h2 id="model-evaluate-title">Evaluar periodo</h2></div><span className="model-scope-label">Solo simulación</span></div>
    <p className="muted">Se usa el modelo activo compatible y la última revisión de cada registro disponible hasta el instante indicado. El servidor comprueba el periodo y puede abstenerse si faltan datos.</p>
    {blocked && <div className="notice" role="status"><strong>Evaluación no disponible</strong><p>{blocked}</p></div>}
    <form onSubmit={evaluate} className="model-evaluate-form">
      <fieldset disabled={!available || mutation.isPending}><legend>Instante de evaluación</legend><div className="model-time-options"><label className="model-radio"><input type="radio" name="evaluation-time" value="now" checked={mode === 'now'} onChange={() => { setMode('now'); setValidation(null); mutation.reset(); }} />Instante actual</label><label className="model-radio"><input type="radio" name="evaluation-time" value="manual" checked={mode === 'manual'} onChange={() => { setMode('manual'); setValidation(null); mutation.reset(); }} />Elegir fecha y hora (America/Lima)</label></div>
        {mode === 'manual' && <div className="model-manual-date"><label htmlFor="model-as-of">Fecha y hora en Lima</label><input id="model-as-of" type="datetime-local" required value={manual} onChange={event => { setManual(event.target.value); setValidation(null); mutation.reset(); }} aria-describedby={`model-as-of-help${validation ? ' model-as-of-error' : ''}`} aria-invalid={validation !== null} /><p id="model-as-of-help" className="muted">La fecha se interpreta en America/Lima (UTC−05:00). Solo usa información incorporada hasta ese momento.</p></div>}
      </fieldset>
      <p className="muted">El instante actual usa la hora consultada al sistema. Las fechas manuales se interpretan en America/Lima.</p>
      {validation && <p id="model-as-of-error" ref={validationMessage} tabIndex={-1} className="notice error" role="alert">{validation}</p>}
      <div className="model-evaluation-action"><button className="button primary" type="submit" disabled={!available || mutation.isPending}>{mutation.isPending ? 'Evaluando…' : 'Evaluar ahora'}</button><span className="muted">{period ? `Periodo ${period.code}` : 'Sin periodo seleccionado'}</span></div>
    </form>
    {mutation.isPending && <p className="muted" role="status">Evaluación en curso. Espera el resultado antes de volver a solicitarla.</p>}
    {mutation.isError && <div ref={responseSummary} tabIndex={-1}><ErrorState error={mutation.error} />{mutation.error instanceof ApiError && (mutation.error.code === 'NETWORK_ERROR' || mutation.error.status === 503) && <p className="muted">No recibimos la confirmación del servidor. Consulta los registros antes de repetir; una evaluación ya registrada se reutiliza.</p>}</div>}
    {mutation.isSuccess && <div ref={responseSummary} tabIndex={-1} className="model-evaluation-result" role="status"><h3>Evaluación completada</h3><p className="muted">Instante solicitado: {timestampLabel(mutation.data.as_of)}</p><dl className="model-result-values"><div><dt>Cortes seleccionados</dt><dd>{numberLabel(mutation.data.selected)}</dd></div><div><dt>Evaluaciones nuevas</dt><dd>{numberLabel(mutation.data.created)}</dd></div><div><dt>Evaluaciones reutilizadas</dt><dd>{numberLabel(mutation.data.reused)}</dd></div><div><dt>Abstenciones</dt><dd>{numberLabel(mutation.data.abstentions.length)}</dd></div></dl>
      <p className="muted">Las abstenciones conservan el registro sin estimación; no se convierten en riesgo bajo. Reutilizar una evaluación conserva la evidencia existente.</p>
      {mutation.data.abstentions.length > 0 && <details className="model-abstentions"><summary>Consultar motivos de abstención</summary><ul>{mutation.data.abstentions.map((item, index) => <li key={item.snapshot_id}><strong>Corte {index + 1}</strong> · {reasonLabel(item.reason)}<span className="model-reason-code">Motivo registrado: {item.reason}</span></li>)}</ul></details>}
      <button className="button secondary" type="button" onClick={() => onNavigate(`/estudiantes?period_id=${encodeURIComponent(mutation.data.period_id)}`)}>Consultar estudiantes</button>
    </div>}
  </section>;
}
