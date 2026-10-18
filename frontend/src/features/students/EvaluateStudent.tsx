import { useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, type Period, type Student, type StudentEvaluation } from '../../lib/api';
import { ErrorState, LoadingState, RiskBadge } from '../../components/ui';

type Props = { student: Student; period: Period; hasSnapshot: boolean; onNavigate: (path: string) => void };
const algorithmName: Record<string, string> = { RANDOM_FOREST: 'Random Forest', SVM: 'SVM', XGBOOST: 'XGBoost', DUMMY: 'Dummy' };
const approvalName: Record<string, string> = { TECHNICAL_SIMULATION: 'simulación técnica con datos sintéticos', LOCAL_EXPLORATORY: 'exploratorio local, sin validación externa' };
const actionText: Record<StudentEvaluation['case_action'], string> = {
  CREATED: 'Se abrió un caso de seguimiento nuevo.', UPDATED: 'Se actualizó el caso de seguimiento existente.',
  REUSED: 'La evaluación ya estaba registrada; se conserva el mismo caso.', NONE: 'Riesgo bajo: no se abre un caso.' };

export function EvaluateStudent({ student, period, hasSnapshot, onNavigate }: Props) {
  const cache = useQueryClient();
  const result = useRef<HTMLDivElement>(null);
  const status = useQuery({ queryKey: ['processing-status'], queryFn: ({ signal }) => api.processingStatus(signal), retry: false, enabled: period.data_origin === 'SYNTHETIC' });
  const models = useQuery({ queryKey: ['models', 'active-for-evaluation', period.id], queryFn: ({ signal }) => api.models({ page: 1, page_size: 50 }, signal), retry: false, enabled: period.data_origin === 'SYNTHETIC' });
  const activeModel = models.data?.items.find(item => item.is_active && item.data_origin === period.data_origin);
  const evaluate = useMutation({
    mutationFn: () => api.evaluateStudent(student.id, period.id),
    onSuccess: () => { void cache.invalidateQueries(); requestAnimationFrame(() => result.current?.focus()); } });
  if (period.data_origin !== 'SYNTHETIC') return null;
  const predict = status.data?.operations.predict;
  const blocked = !hasSnapshot ? 'Registra primero una medición para poder evaluar.' : student.is_active === false ? 'El estudiante está inactivo.' : period.is_locked ? 'El periodo está bloqueado.'
    : predict && !predict.available ? 'No hay un modelo activo del estudio sintético. Actívalo desde Modelos.' : null;
  const data = evaluate.data;
  return <section className="panel student-detail-panel" aria-labelledby="student-evaluate-title"><h2 id="student-evaluate-title">Evaluar riesgo de este estudiante</h2>
    <p className="muted">Simulación con datos sintéticos y el modelo técnico activo. El resultado no es una decisión pedagógica ni valida el desempeño en el colegio; una persona decide el seguimiento.</p>
    {status.isPending && <LoadingState label="Comprobando modelo disponible…" />}
    {status.isError && <ErrorState error={status.error} onRetry={() => void status.refetch()} />}
    {blocked && !status.isPending && <p className="notice" role="status">{blocked}</p>}
    <button className="button primary" type="button" disabled={!!blocked || status.isPending || status.isError || evaluate.isPending} aria-busy={evaluate.isPending} onClick={() => evaluate.mutate()}>{evaluate.isPending ? 'Evaluando…' : 'Evaluar riesgo de este estudiante'}</button>
    <div ref={result} tabIndex={-1} aria-live="polite">
      {evaluate.isError && (evaluate.error instanceof ApiError ? <p className="field-error" role="alert">{evaluate.error.message}</p> : <ErrorState error={evaluate.error} onRetry={() => evaluate.mutate()} />)}
      {data && <div className="notice" role="status">
        {data.status === 'EVALUATED' && <><p><strong>Evaluación registrada.</strong> <RiskBadge risk={data.risk_level ?? null} /></p>{activeModel && <p>Modelo que hizo la evaluación: <strong>{algorithmName[activeModel.algorithm] ?? activeModel.algorithm}</strong> ({approvalName[activeModel.approval_kind ?? ''] ?? 'modelo activo'}).</p>}<p>{actionText[data.case_action]}</p>
          {data.alert_id && <p><a className="followup-link" href={`/alertas/${data.alert_id}?period_id=${encodeURIComponent(period.id)}`} onClick={event => { if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(`/alertas/${encodeURIComponent(data.alert_id!)}?period_id=${encodeURIComponent(period.id)}`); } }}>Abrir el caso de seguimiento →</a></p>}</>}
        {data.status === 'INSUFFICIENT_DATA' && <p><strong>Datos insuficientes.</strong> {data.reason} No se asigna riesgo bajo por defecto.</p>}
        {data.status === 'NOT_ELIGIBLE' && <p><strong>No elegible para la simulación.</strong> {data.reason}</p>}
      </div>}
    </div>
    <p className="muted student-list-note">La fecha de horizonte que se muestra en la evaluación es la del modelo (corte + días del horizonte); no es una fecha objetivo observada.</p>
  </section>;
}
