import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, type Period, type User } from '../../lib/api';
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../../components/ui';
import { dateLabel, timestampLabel } from '../../lib/format';
import { REAL_NOTICE } from '../../lib/origin';

type Props = { user: User; periods: Period[]; periodId: string };

/** Página mínima del protocolo REAL (solo ADMIN): estado y confirmar/revocar. No guarda consentimientos ni documentos. */
export function ProtocolPage({ user, periods, periodId }: Props) {
  const real = periods.filter(item => item.data_origin === 'REAL');
  const [selected, setChosen] = useState('');
  // Los periodos llegan después del primer render: el periodo elegido se deriva, no se congela en el estado inicial.
  const chosen = real.some(item => item.id === selected) ? selected : real.find(item => item.id === periodId)?.id ?? real[0]?.id ?? '';
  const queryClient = useQueryClient();
  const protocol = useQuery({ queryKey: [user.id, user.role, 'protocol', chosen], queryFn: ({ signal }) => api.protocolByPeriod(chosen, signal), enabled: Boolean(chosen), retry: false });
  const [confirming, setConfirming] = useState<'confirm' | 'revoke' | null>(null);
  const change = useMutation({
    mutationFn: (action: 'confirm' | 'revoke') => action === 'confirm' ? api.confirmProtocol(protocol.data!.id) : api.revokeProtocol(protocol.data!.id),
    retry: false,
    onSuccess: () => { setConfirming(null); return queryClient.invalidateQueries({ queryKey: [user.id, user.role] }); },
  });
  const missing = protocol.error instanceof ApiError && protocol.error.status === 404;
  const data = protocol.data;
  return <div className="models-feature"><PageHeader title="Protocolo de datos reales" eyebrow="ADMINISTRACIÓN" description="Interruptor técnico que habilita el procesamiento local de un periodo con datos reales. No guarda consentimientos, documentos, autorizadores ni fechas de permiso." />
    <p className="notice" role="status">{REAL_NOTICE} Solo se usan códigos; los nombres no salen de la ficha del estudiante.</p>
    {real.length === 0 ? <EmptyState title="No hay periodos reales"><p>Crea un periodo con origen real desde Estudiantes para registrar su protocolo.</p></EmptyState> : <>
      <div className="context-field"><label htmlFor="protocol-period">Periodo real</label><select id="protocol-period" value={chosen} onChange={event => { setChosen(event.target.value); setConfirming(null); change.reset(); }}>{real.map(item => <option key={item.id} value={item.id}>{item.code} · {item.school_year}</option>)}</select></div>
      {protocol.isPending && chosen ? <LoadingState label="Consultando el protocolo…" /> : missing ? <EmptyState title="Este periodo aún no tiene protocolo"><p>El protocolo se registra con los parámetros del procedimiento descrito en el manual «Protocolo REAL». Mientras no exista y esté confirmado, todo el procesamiento de este periodo permanece bloqueado.</p></EmptyState> : protocol.isError ? <ErrorState error={protocol.error} onRetry={() => void protocol.refetch()} /> : data && <section className="panel model-detail-panel" aria-labelledby="protocol-title">
        <div className="model-panel-heading"><h2 id="protocol-title">Estado del protocolo</h2><span className={`badge ${data.authorization_confirmed_by_admin ? 'model-active' : 'model-inactive'}`}>{data.authorization_confirmed_by_admin ? '● Confirmado: procesamiento habilitado' : '○ Sin confirmar: procesamiento bloqueado'}</span></div>
        <dl className="model-detail-values">
          <div><dt>Cohorte</dt><dd>{data.cohort_label}</dd></div>
          <div><dt>Escala de notas</dt><dd>{data.grade_scale_min}–{data.grade_scale_max}</dd></div>
          
          <div><dt>Bimestres</dt><dd>{data.bimesters.map(item => `${item.code} (fin del bimestre ${dateLabel(item.close_date)})`).join(' · ')}</dd></div>
          <div><dt>Ventanas de oportunidad</dt><dd>Detección ≥ {data.opportune_windows.detection_days} días antes del fin del bimestre · intervención ≤ {data.opportune_windows.intervention_days} días</dd></div>
          <div><dt>Versión</dt><dd>{data.version}</dd></div>
          <div><dt>Confirmado</dt><dd>{data.confirmed_at ? timestampLabel(data.confirmed_at) : 'No confirmado'}</dd></div>
        </dl>
        <p className="muted model-detail-note">Confirmar habilita, para este periodo, la importación del CSV canónico, la comparación exploratoria de modelos, la evaluación retrospectiva, las alertas y los indicadores. Revocar vuelve a bloquear todo de inmediato y conserva lo ya guardado.</p>
        {change.isError && <ErrorState error={change.error} />}
        {confirming ? <div className="notice" role="alertdialog" aria-label="Confirmar cambio de protocolo"><p>{confirming === 'confirm' ? '¿Confirmas que este periodo puede procesarse localmente con datos reales? Se rotula como análisis exploratorio.' : '¿Revocas el protocolo? Todo el procesamiento REAL de este periodo quedará bloqueado.'}</p>
          <button className="button primary" type="button" disabled={change.isPending} onClick={() => change.mutate(confirming)}>{change.isPending ? 'Guardando…' : confirming === 'confirm' ? 'Sí, confirmar' : 'Sí, revocar'}</button>{' '}
          <button className="button secondary" type="button" disabled={change.isPending} onClick={() => setConfirming(null)}>Cancelar</button></div>
          : data.authorization_confirmed_by_admin ? <button className="button secondary" type="button" onClick={() => setConfirming('revoke')}>Revocar protocolo</button> : <button className="button primary" type="button" onClick={() => setConfirming('confirm')}>Confirmar protocolo</button>}
      </section>}
    </>}
  </div>;
}
