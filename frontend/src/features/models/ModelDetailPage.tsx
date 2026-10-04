import { type MouseEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../../lib/api';
import { timestampLabel } from '../../lib/format';
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../../components/ui';
import { algorithmNames, modelStatusLabel, type ModelsProps } from './ModelsPage';
import { EvaluationPanel } from './EvaluationPanel';
import './features.css';

type Props = ModelsProps & { modelId: string };
export function ModelDetailPage(props: Props) {
  if (props.user.role !== 'ADMIN') return <EmptyState title="Consulta no disponible para tu rol"><p>La consulta de modelos está reservada a administración.</p></EmptyState>;
  return <ModelRecord key={`${props.user.id}:${props.user.role}:${props.period?.id ?? 'none'}:${props.modelId}`} {...props} />;
}

function ModelRecord({ user, period, processing, modelId, onNavigate }: Props) {
  const detail = useQuery({ queryKey: [user.id, user.role, 'model', period?.id, modelId],
    queryFn: ({ signal }) => api.model(modelId, signal), retry: false });
  const backPath = `/modelos${period ? `?period_id=${encodeURIComponent(period.id)}` : ''}`;
  function back(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(backPath); }
  }
  const action = <a className="button secondary" href={backPath} onClick={back}>← Volver a modelos</a>;
  if (detail.isPending) return <div className="models-feature"><PageHeader title="Detalle del modelo" action={action} /><LoadingState label="Consultando el modelo…" /></div>;
  if (detail.isError) return <div className="models-feature"><PageHeader title="Detalle del modelo" action={action} />{detail.error instanceof ApiError && [403, 404].includes(detail.error.status) ? <EmptyState title="Este modelo no está disponible"><p>Consulta los modelos autorizados de la aplicación.</p></EmptyState> : <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />}</div>;
  const model = detail.data;
  return <div className="models-feature"><PageHeader title={model.name} eyebrow="DETALLE DEL MODELO" description={`Versión ${model.version}`} action={action} />
    <section className="panel model-detail-panel" aria-labelledby="model-context-title"><div className="model-panel-heading"><h2 id="model-context-title">Información del modelo</h2><span className={`badge ${model.is_active ? 'model-active' : 'model-inactive'}`}>{model.is_active ? '● Activo' : '○ Inactivo'}</span></div><dl className="model-detail-values"><div><dt>Algoritmo</dt><dd>{algorithmNames[model.algorithm]}</dd></div><div><dt>Estado</dt><dd>{modelStatusLabel(model)}</dd></div><div><dt>Origen</dt><dd>{model.data_origin === 'SYNTHETIC' ? 'Datos sintéticos' : 'Datos institucionales'}</dd></div><div><dt>Registro</dt><dd>{timestampLabel(model.created_at)}</dd></div><div><dt>Versión del esquema de variables</dt><dd>{model.feature_schema_version}</dd></div><div><dt>Versión del criterio de referencia</dt><dd>{model.reference_criterion_version}</dd></div></dl>
      <p className="muted model-detail-note">La API publica esta información de registro. Las métricas y los archivos privados se consultan mediante el procedimiento técnico autorizado; no están disponibles en esta pantalla.</p>
      {model.data_origin === 'SYNTHETIC' && <div className="notice" role="status"><strong>Alcance de simulación</strong><p>Este modelo pertenece a un estudio con datos sintéticos. Su estado técnico y sus resultados no acreditan validación institucional ni resultados escolares observados.</p></div>}
    </section>
    {model.is_active && model.data_origin === 'SYNTHETIC' ? <EvaluationPanel user={user} period={period} processing={processing} onNavigate={onNavigate} /> : <p className="muted">Este modelo no está disponible para una evaluación desde la aplicación. La preparación y activación siguen el procedimiento administrativo autorizado.</p>}
  </div>;
}
