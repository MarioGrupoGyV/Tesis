import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type User, type RetrospectivePartialResult } from '../../lib/api';
import { timestampLabel } from '../../lib/format';
import { ErrorState, LoadingState, Pagination } from '../../components/ui';

const riskLabels = { LOW: '○ Bajo', MEDIUM: '△ Medio', HIGH: '▲ Alto' };

export function RetrospectivePanel({ user }: { user: User }) {
  const cache = useQueryClient();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [partialResult, setPartialResult] = useState<RetrospectivePartialResult | null>(null);
  const [downloadError, setDownloadError] = useState<unknown>(null);
  const [downloading, setDownloading] = useState(false);
  const history = useQuery({ queryKey: [user.id, 'retrospective', page],
    queryFn: ({ signal }) => api.retrospectiveHistory(page, signal), retry: false });
  const detail = useQuery({ queryKey: [user.id, 'retrospective-detail', selected],
    queryFn: ({ signal }) => api.retrospectiveDetail(selected!, signal), enabled: selected !== null, retry: false });
  const run = useMutation({ mutationFn: () => api.runRetrospective(), onSuccess: result => {
    cache.setQueryData([user.id, 'retrospective-detail', result.id], result);
    setSelected(result.id); setPage(1); void cache.invalidateQueries({ queryKey: [user.id, 'retrospective'] });
  } });
  const partial = useMutation({ mutationFn: api.retrospectivePartialPrediction, onSuccess: setPartialResult });
  async function download() {
    if (!selected) return;
    setDownloading(true); setDownloadError(null);
    try {
      const blob = await api.exportRetrospectiveCsv(selected);
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = 'evaluacion-retrospectiva-B2.csv'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setDownloadError(error); } finally { setDownloading(false); }
  }
  function predict(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPartialResult(null);
    const fields = new FormData(event.currentTarget);
    const date = String(fields.get('availability'));
    const available = `${date}T00:00:00-05:00`;
    partial.mutate({ term: 'B2', values: {
      promedio_parcial_0_20: Number(fields.get('grade')),
      asistencia_parcial_proporcion: Number(fields.get('attendance')),
      entrega_parcial_proporcion: Number(fields.get('activities')),
    }, available_at: { promedio_parcial_0_20: available,
      asistencia_parcial_proporcion: available, entrega_parcial_proporcion: available } });
  }
  return <section className="panel retrospective-panel" aria-labelledby="retrospective-title">
    <h2 id="retrospective-title">Evaluación retrospectiva B1 → B2</h2>
    <p>Modelo SVM del paquete autorizado. Entrenamiento declarado: B1, corte 21 de abril de 2026. Evaluación: B2, corte 30 de junio de 2026; mismos 60 estudiantes. Cada ejecución conserva su fecha real.</p>
    <div className="notice"><strong>Alcance retrospectivo</strong><p>Las propuestas de alerta se evalúan aquí. La autorización local fue declarada por el usuario; la autenticidad institucional requiere sustento documental. Los resultados no demuestran ejecución histórica ni efecto escolar.</p></div>
    {history.isPending ? <LoadingState label="Consultando evaluaciones retrospectivas…" /> : history.isError ? <ErrorState error={history.error} onRetry={() => void history.refetch()} /> : !history.data.available ?
      <p role="status">Paquete retrospectivo aún no registrado mediante el procedimiento administrativo local.</p> : <>
        <p>El artefacto usa scikit-learn 1.8.0; su carga en el runtime 1.9.1 es experimental y no está respaldada como compatibilidad entre versiones. Se conservan las advertencias y las discrepancias reales.</p>
        <button className="button" type="button" disabled={run.isPending} onClick={() => run.mutate()}>{run.isPending ? 'Evaluando B2…' : 'Ejecutar evaluación retrospectiva'}</button>
        {run.isError && <ErrorState error={run.error} onRetry={() => run.mutate()} />}
        {history.data.total === 0 ? <p role="status">Todavía no hay ejecuciones retrospectivas.</p> : <>
          <div className="table-container" tabIndex={0} role="region" aria-label="Historial retrospectivo"><table><caption>Ejecuciones retrospectivas; fechas en Lima</caption><thead><tr><th>Fecha real</th><th>Aciertos / total</th><th>Exactitud</th><th>F1 macro</th><th>Propuestas</th></tr></thead><tbody>{history.data.items.map(item => <tr key={item.id}><td><button className="button secondary" onClick={() => setSelected(item.id)}>{timestampLabel(item.executed_at)}</button></td><td>{item.metrics.correct} / {item.metrics.n}</td><td>{(item.metrics.accuracy * 100).toFixed(2)} %</td><td>{item.metrics.f1_macro.toFixed(6)}</td><td>{item.metrics.alert_proposals}</td></tr>)}</tbody></table></div>
          <Pagination page={page} pageSize={history.data.page_size} total={history.data.total} onPageChange={setPage} />
        </>}
        {selected && (detail.isPending ? <LoadingState label="Consultando resultado…" /> : detail.isError ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} /> : detail.data && <div aria-label="Resultado retrospectivo">
          <h3>Resultado B2</h3><p role="status">{detail.data.metrics.correct} aciertos de {detail.data.metrics.n}; exactitud {(detail.data.metrics.accuracy * 100).toFixed(2)} %; F1 macro {detail.data.metrics.f1_macro.toFixed(6)}.</p>
          <p>{detail.data.metrics.alert_proposals} propuestas de alerta · {detail.data.notifications_sent} notificaciones enviadas · {detail.data.interventions_performed} intervenciones realizadas por esta ejecución.</p>
          <p>Ejecución: {timestampLabel(detail.data.executed_at)}. Coincidencia con las clases del ZIP: {detail.data.metrics.n - detail.data.prediction_mismatches} / {detail.data.metrics.n}. Escalador B1: {detail.data.scaler_b1_verified ? 'comprobado' : 'sin comprobar'}. Reajuste: {detail.data.refitted ? 'sí' : 'no'}.</p>
          <p>{detail.data.source_events_verified ? 'Fechas declaradas de 720 notas parciales y 240 ventanas de asistencia/actividades verificadas contra el Excel original y el CSV derivado.' : 'Disponibilidad temporal comprobada en el CSV derivado; eventos fuente originales pendientes.'} La autenticidad institucional requiere sustento documental. Compatibilidad: {detail.data.compatibility === 'CROSS_VERSION_EXPERIMENTAL' ? 'experimental entre versiones' : 'misma versión scikit-learn'}.</p>
          {detail.data.discrepancies.length > 0 && <p role="alert">Discrepancias: {detail.data.discrepancies.join(', ')}</p>}
          <button className="button secondary" disabled={downloading} onClick={() => void download()}>{downloading ? 'Preparando CSV…' : 'Descargar reporte retrospectivo CSV'}</button>
          {downloadError !== null && <ErrorState error={downloadError} onRetry={() => void download()} />}
          <div className="table-container" tabIndex={0} role="region" aria-label="Predicciones retrospectivas"><table><caption>60 predicciones de B2; filas anonimizadas para este reporte</caption><thead><tr><th>Fila</th><th>Riesgo predicho</th><th>Referencia</th><th>Acierto</th><th>Propuesta</th></tr></thead><tbody>{detail.data.predictions.map(row => <tr key={row.row_number}><td>{row.row_number}</td><td><span className={`badge risk-${row.risk_level.toLowerCase()}`}>{riskLabels[row.risk_level]}</span></td><td>{riskLabels[row.reference_risk]}</td><td>{row.correct ? 'Sí' : 'No'}</td><td>{row.alert_proposed ? 'Propuesta pendiente de revisión humana' : 'Sin propuesta'}</td></tr>)}</tbody></table></div>
        </div>)}
        <h3>Comprobar una entrada parcial</h3><p>Ensayo sin crear un caso. Introduce el promedio parcial y las dos proporciones; se usa el escalador incluido. Indica una fecha en la que los tres valores ya estaban disponibles, como máximo el corte B2 a las 00:00 en Lima.</p>
        <form onSubmit={predict} onChange={() => { setPartialResult(null); partial.reset(); }}>
        <fieldset className="retrospective-form" disabled={partial.isPending}>
          <label>Promedio parcial (0 a 20)<input name="grade" type="number" min="0" max="20" step="any" required /></label>
          <label>Asistencia parcial (0 a 1)<input name="attendance" type="number" min="0" max="1" step="any" required /></label>
          <label>Entrega parcial (0 a 1)<input name="activities" type="number" min="0" max="1" step="any" required /></label>
          <label>Disponibilidad de los tres valores<input name="availability" type="date" max="2026-06-30" required /></label>
          <button className="button secondary" disabled={partial.isPending}>{partial.isPending ? 'Calculando…' : 'Comprobar entrada parcial'}</button>
        </fieldset>
        </form>
        {partial.isError && <ErrorState error={partial.error} />}
        {partialResult && <p role="status">{riskLabels[partialResult.risk_level]}. {partialResult.alert_proposed ? 'Propuesta de alerta' : 'Sin propuesta de alerta'}. 0 notificaciones enviadas; 0 intervenciones realizadas. Ejecución: {timestampLabel(partialResult.executed_at)}.</p>}
      </>}
  </section>;
}
