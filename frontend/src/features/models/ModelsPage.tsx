import { useState, type MouseEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type Model, type Period, type ProcessingStatus, type User } from '../../lib/api';
import { timestampLabel } from '../../lib/format';
import { EmptyState, ErrorState, LoadingState, PageHeader, Pagination } from '../../components/ui';
import { EvaluationPanel } from './EvaluationPanel';
import './features.css';

export type ModelsProps = { user: User; period: Period | null; processing: ProcessingStatus | null; onNavigate: (path: string) => void };
export const algorithmNames: Record<Model['algorithm'], string> = { DUMMY: 'Baseline Dummy', RANDOM_FOREST: 'Random Forest', SVM: 'SVM', XGBOOST: 'XGBoost' };
export function modelStatusLabel(model: Model): string {
  return model.status === 'DRAFT' ? 'Borrador' : model.status === 'EVALUATED' ? 'Evaluado' : model.status === 'RETIRED' ? 'Retirado' : model.data_origin === 'SYNTHETIC' ? 'Aprobado para simulación' : 'Aprobado';
}

export function ModelsPage(props: ModelsProps) {
  if (props.user.role !== 'ADMIN') return <EmptyState title="Consulta no disponible para tu rol"><p>La consulta de modelos está reservada a administración.</p></EmptyState>;
  return <ModelListing key={`${props.user.id}:${props.user.role}:${props.period?.id ?? 'none'}`} {...props} />;
}

function ModelListing({ user, period, processing, onNavigate }: ModelsProps) {
  const [page, setPage] = useState(1);
  const models = useQuery({ queryKey: [user.id, user.role, 'models', period?.id, page],
    queryFn: ({ signal }) => api.models({ page, page_size: 25 }, signal), retry: false });
  function navigate(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(path); }
  }
  return <div className="models-feature"><PageHeader title="Modelos" eyebrow="ADMINISTRACIÓN" description="Consulta los modelos registrados y solicita una evaluación del periodo autorizado. La aprobación técnica de datos sintéticos solo permite simulación." />
    {models.isPending ? <LoadingState label="Consultando modelos…" /> : models.isError ? <ErrorState error={models.error} onRetry={() => void models.refetch()} /> : models.data.items.length === 0 ? <EmptyState title="Modelo no disponible"><p>No hay modelos registrados para consultar. Su preparación se realiza mediante el procedimiento administrativo autorizado.</p></EmptyState> :
      <section className="panel model-list-panel" aria-label="Listado de modelos"><div className="model-list-heading"><h2>Modelos registrados</h2><p className="muted" role="status">{models.data.total} {models.data.total === 1 ? 'modelo' : 'modelos'}</p></div>
        <div className="table-container model-table" tabIndex={0} role="region" aria-label="Tabla de modelos; desplazamiento horizontal disponible"><table><caption>Modelos registrados</caption><thead><tr><th scope="col">Modelo</th><th scope="col">Algoritmo</th><th scope="col">Estado</th><th scope="col">Uso activo</th><th scope="col">Origen</th><th scope="col">Registro</th></tr></thead><tbody>{models.data.items.map(model => { const path = `/modelos/${model.id}${period ? `?period_id=${encodeURIComponent(period.id)}` : ''}`; return <tr key={model.id}><td><a className="model-link" href={path} onClick={event => navigate(event, path)}>{model.name}</a><span className="model-version">Versión {model.version}</span></td><td>{algorithmNames[model.algorithm]}</td><td><span className={`badge model-status-${model.status.toLowerCase()}`}>{modelStatusLabel(model)}</span></td><td><span className={`badge ${model.is_active ? 'model-active' : 'model-inactive'}`}>{model.is_active ? '● Activo' : '○ Inactivo'}</span></td><td>{model.data_origin === 'SYNTHETIC' ? 'Sintético' : 'Institucional'}</td><td className="model-timestamp">{timestampLabel(model.created_at)}</td></tr>; })}</tbody></table></div>
        <Pagination page={models.data.page} pageSize={models.data.page_size} total={models.data.total} onPageChange={setPage} />
      </section>}
    <EvaluationPanel user={user} period={period} processing={processing} onNavigate={onNavigate} />
  </div>;
}
