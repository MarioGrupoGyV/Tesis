import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, errorMessage, type ImportBatch, type ImportCommit, type Period, type ProcessingStatus, type User } from '../../lib/api';
import { reasonLabel, timestampLabel } from '../../lib/format';
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../../components/ui';
import './imports.css';

const HEADERS = ['student_code', 'grade', 'section', 'cutoff_at', 'target_date', 'available_at',
  'window_start', 'average_grade', 'attendance_pct', 'activities_pct', 'participation_level',
  'behavior_incidents', 'age_years'] as const;
const MAX_FILE_BYTES = 5 * 1024 * 1024;

export interface ImportsPageProps {
  user: User;
  period: Period | null;
  status: ProcessingStatus | null;
  statusLoading: boolean;
  statusError: string;
  onRetryStatus: () => void;
  onUnauthorized: () => void;
  onCommitted: (periodId: string) => void;
  onViewStudents: (periodId: string) => void;
}

function downloadHeaders() {
  const url = URL.createObjectURL(new Blob([`${HEADERS.join(',')}\n`], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'cabeceras-estudio-sintetico.csv';
  link.click();
  URL.revokeObjectURL(url);
}

function ImportErrors({ batch }: { batch: ImportBatch }) {
  if (!batch.errors.length) return null;
  return <div className="table-container import-errors" tabIndex={0} aria-label="Errores de validación, tabla desplazable">
    <table>
      <caption>Correcciones indicadas por el servidor</caption>
      <thead><tr><th scope="col">Fila</th><th scope="col">Columna</th><th scope="col">Qué debe revisarse</th></tr></thead>
      <tbody>{batch.errors.map((item, index) => <tr key={`${item.row}-${item.column}-${item.code}-${index}`}>
        <td>{item.row}</td><td><code>{item.column}</code></td><td>{item.message}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

function RequestDetails({ error }: { error: unknown }) {
  if (!(error instanceof ApiError)) return null;
  return <>
    {error.details.length > 0 && <ul className="import-request-details" aria-label="Detalles de validación">
      {error.details.map((item, index) => <li key={index}>
        {item.row != null && <strong>Fila {item.row}. </strong>}
        {item.field && <span>Campo <code>{item.field}</code>: </span>}{item.message}
      </li>)}
    </ul>}
    {error.requestId && <p className="import-support">Referencia para soporte: <code>{error.requestId}</code></p>}
  </>;
}

export function ImportsPage({ user, period, status, statusLoading, statusError, onRetryStatus,
  onUnauthorized, onCommitted, onViewStudents }: ImportsPageProps) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const [previewSeed, setPreviewSeed] = useState<{ context: string; batch: ImportBatch } | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [requestError, setRequestError] = useState<unknown>(null);
  const [stale, setStale] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [result, setResult] = useState<ImportCommit | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const reviewRef = useRef<HTMLHeadingElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const operation = useRef<AbortController | null>(null);
  const detailSignal = useRef<AbortSignal | null>(null);
  const generation = useRef(0);
  const context = `${user.id}:${user.role}:${period?.id ?? ''}`;
  const currentContext = useRef(context);
  currentContext.current = context;
  const admin = user.role === 'ADMIN';
  const selectedPreview = previewSeed?.context === context ? previewSeed.batch : null;
  const detailKey = [user.id, user.role, 'import', period?.id ?? '', selectedPreview?.id ?? ''];

  const previewMutation = useMutation({
    mutationFn: ({ selectedFile, periodId, signal }: { selectedFile: File; periodId: string; signal: AbortSignal }) =>
      api.previewImport(selectedFile, periodId, signal),
    retry: false,
  });
  const commitMutation = useMutation({
    mutationFn: ({ id, version, signal }: { id: string; version: number; signal: AbortSignal }) =>
      api.commitImport(id, version, signal),
    retry: false,
  });
  const detail = useQuery({
    queryKey: detailKey,
    queryFn: ({ signal }) => {
      detailSignal.current = signal;
      return api.importDetail(selectedPreview!.id, signal);
    },
    enabled: admin && !!selectedPreview,
    initialData: selectedPreview ?? undefined,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 0,
  });
  const batch = selectedPreview ? (detail.data ?? selectedPreview) : null;
  const freshCommit = result?.batch_id === batch?.id && result?.reused_result === false;
  const busy = previewMutation.isPending || commitMutation.isPending;
  const blocked = !admin ? 'Solo una cuenta administradora puede importar.'
    : statusLoading ? 'Estamos comprobando si la importación está disponible.'
      : statusError || !status ? 'No se pudo comprobar la disponibilidad. Vuelve a intentarlo antes de importar.'
        : !status.operations.import.available ? reasonLabel(status.operations.import.reason)
          : !period ? 'Selecciona un periodo autorizado para preparar el archivo.'
            : period.data_origin !== 'SYNTHETIC' ? 'Este periodo corresponde a datos institucionales. Su procesamiento permanece bloqueado.'
              : period.is_locked ? 'El periodo está bloqueado y no admite nuevas importaciones.' : '';
  const canCommit = !blocked && !busy && !stale && !uncertain && !detail.isFetching && !detail.error
    && batch?.status === 'READY' && batch.invalid_rows === 0 && batch.errors.length === 0 && confirmed;
  const activeStep = !batch ? 1 : batch.status === 'COMMITTED' || confirmed || commitMutation.isPending ? 3 : 2;

  useEffect(() => {
    generation.current += 1;
    operation.current?.abort();
    operation.current = null;
    setFile(null);
    setFileError('');
    setPreviewSeed(null);
    setConfirmed(false);
    setRequestError(null);
    setStale(false);
    setUncertain(false);
    setResult(null);
    previewMutation.reset();
    commitMutation.reset();
    if (inputRef.current) inputRef.current.value = '';
    return () => {
      generation.current += 1;
      operation.current?.abort();
      operation.current = null;
    };
  }, [context]);

  useEffect(() => {
    if (detail.error instanceof ApiError && detail.error.status === 401) onUnauthorized();
  }, [detail.error, onUnauthorized]);

  function selectFile(selected: File | null) {
    generation.current += 1;
    operation.current?.abort();
    operation.current = null;
    setPreviewSeed(null);
    setConfirmed(false);
    setRequestError(null);
    setStale(false);
    setUncertain(false);
    setResult(null);
    previewMutation.reset();
    commitMutation.reset();
    if (selected && (selected.size === 0 || selected.size > MAX_FILE_BYTES)) {
      setFile(null);
      setFileError(selected.size === 0 ? 'El archivo está vacío. Elige el CSV registrado.' : 'El archivo supera 5 MiB. Elige el CSV registrado dentro del límite.');
      return;
    }
    setFile(selected);
    setFileError('');
  }

  function acceptResponse(controller: AbortController, epoch: number, expectedContext: string) {
    return !controller.signal.aborted && generation.current === epoch && currentContext.current === expectedContext;
  }

  async function preview(event: FormEvent) {
    event.preventDefault();
    if (!file || !period || blocked || operation.current) return;
    const controller = new AbortController();
    operation.current = controller;
    const epoch = generation.current;
    const expectedContext = context;
    setRequestError(null);
    setConfirmed(false);
    setResult(null);
    try {
      const response = await previewMutation.mutateAsync({ selectedFile: file, periodId: period.id, signal: controller.signal });
      if (!acceptResponse(controller, epoch, expectedContext)) return;
      const responseKey = [user.id, user.role, 'import', period.id, response.id];
      queryClient.setQueryData(responseKey, response);
      setPreviewSeed({ context: expectedContext, batch: response });
      void queryClient.invalidateQueries({ queryKey: responseKey, exact: true });
      setStale(false);
      setUncertain(false);
      window.requestAnimationFrame(() => reviewRef.current?.focus());
    } catch (error) {
      if (!acceptResponse(controller, epoch, expectedContext)) return;
      if (error instanceof ApiError && error.status === 401) onUnauthorized();
      else {
        setRequestError(error);
        // A preview can have reached the server despite a lost response. An
        // explicit retry is safe because the server reuses file/period identity.
        setPreviewSeed(null);
        window.requestAnimationFrame(() => resultRef.current?.focus());
      }
    } finally {
      if (operation.current === controller) operation.current = null;
    }
  }

  async function commit(event: FormEvent) {
    event.preventDefault();
    if (!canCommit || !batch || !period || operation.current) return;
    const controller = new AbortController();
    operation.current = controller;
    const epoch = generation.current;
    const expectedContext = context;
    const periodId = period.id;
    setRequestError(null);
    try {
      const response = await commitMutation.mutateAsync({ id: batch.id, version: batch.preview_version, signal: controller.signal });
      if (!acceptResponse(controller, epoch, expectedContext)) return;
      setResult(response);
      setConfirmed(false);
      queryClient.setQueryData(detailKey, { ...batch, status: 'COMMITTED' });
      await queryClient.invalidateQueries({ predicate: ({ queryKey }) => queryKey[0] === user.id
        && queryKey[1] === user.role && ['students', 'student', 'timeline', 'processing'].includes(String(queryKey[2])) });
      if (acceptResponse(controller, epoch, expectedContext)) onCommitted(periodId);
    } catch (error) {
      if (!acceptResponse(controller, epoch, expectedContext)) return;
      if (error instanceof ApiError && error.status === 401) onUnauthorized();
      else {
        setRequestError(error);
        setConfirmed(false);
        if (error instanceof ApiError && error.status === 409) setStale(true);
        else if (!(error instanceof ApiError) || error.status === 0 || error.status >= 500) setUncertain(true);
        window.requestAnimationFrame(() => resultRef.current?.focus());
      }
    } finally {
      if (operation.current === controller) operation.current = null;
    }
  }

  async function refreshBatch() {
    const epoch = generation.current;
    const expectedContext = context;
    setRequestError(null);
    setConfirmed(false);
    const pending = detail.refetch();
    const signal = detailSignal.current;
    const response = await pending;
    if (signal?.aborted || generation.current !== epoch || currentContext.current !== expectedContext) return;
    if (response.data && !response.error) {
      setUncertain(false);
      // A stale preview requires POST preview again: GET alone does not replan.
      if (response.data.status === 'COMMITTED') setStale(false);
    }
  }

  return <div className="import-page">
    <PageHeader title="Importar información" eyebrow="DATOS" description="Prepara, revisa y confirma el CSV registrado del estudio sintético." />
    <p className="import-scope">{status?.notice ?? 'Estudio con datos sintéticos. No corresponde a estudiantes reales.'}</p>
    <ol className="import-steps" aria-label="Pasos de importación">
      <li aria-current={activeStep === 1 ? 'step' : undefined}><span aria-hidden="true">1</span>Preparar archivo</li>
      <li aria-current={activeStep === 2 ? 'step' : undefined}><span aria-hidden="true">2</span>Revisar validaciones</li>
      <li aria-current={activeStep === 3 ? 'step' : undefined}><span aria-hidden="true">3</span>Confirmar importación</li>
    </ol>
    {statusLoading && <LoadingState label="Comprobando disponibilidad de importación…" />}
    {blocked && <section className="import-blocked" aria-labelledby="import-blocked-title">
      <h2 id="import-blocked-title">Importación no disponible</h2><p>{blocked}</p>
      {statusError && <button type="button" className="button secondary" onClick={onRetryStatus}>Volver a comprobar</button>}
    </section>}
    {!period && !statusLoading && <EmptyState title="No hay un periodo seleccionado">Selecciona un periodo autorizado en el contexto. El administrador prepara el estudio fuera de esta pantalla.</EmptyState>}
    <section className="panel import-panel" aria-labelledby="import-prepare-title">
      <div className="import-panel-heading"><div><p className="eyebrow">PASO 1</p><h2 id="import-prepare-title">Preparar archivo</h2></div>
        <button type="button" className="button secondary" onClick={downloadHeaders}>Descargar cabeceras CSV</button></div>
      <p className="muted">La plantilla contiene únicamente cabeceras. Para importar, selecciona el archivo exacto del generador que el administrador registró; completar una plantilla arbitraria no acredita su procedencia.</p>
      <form onSubmit={preview} aria-busy={previewMutation.isPending}>
        <div className="import-context"><span>Periodo de destino</span><strong>{period ? `${period.code} · ${period.school_year}` : 'Selecciona un periodo'}</strong></div>
        <label htmlFor="import-file">Archivo CSV registrado</label>
        <input ref={inputRef} id="import-file" name="file" type="file" hidden accept=".csv,text/csv" disabled={!!blocked || busy}
          aria-describedby={`import-file-help${fileError ? ' import-file-error' : ''}`} aria-invalid={!!fileError}
          onChange={(event) => selectFile(event.target.files?.[0] ?? null)} />
        <button type="button" className="button secondary" disabled={!!blocked || busy} aria-describedby="import-file-help" onClick={() => inputRef.current?.click()}>Seleccionar CSV</button>
        <p id="import-file-help" className="import-help">UTF-8 · máximo 5 MiB · hasta 10 000 registros · 13 columnas en el orden de la plantilla.</p>
        {fileError && <p id="import-file-error" className="notice error" role="alert">{fileError}</p>}
        {file && <p className="import-selected-file">Archivo seleccionado: <strong>{file.name}</strong> · {(file.size / 1024).toFixed(1)} KiB</p>}
        <div className="import-actions"><button className="button primary" type="submit" disabled={!!blocked || !file || busy}>
          {previewMutation.isPending ? 'Revisando archivo…' : stale ? 'Revisar archivo de nuevo' : 'Revisar archivo'}</button>
          <p className="muted">La vista previa no crea estudiantes, matrículas ni cortes.</p></div>
      </form>
      <details className="import-format"><summary>Formato y escalas del protocolo sintético</summary>
        <p>En <code>synthetic-study-v1</code>: promedio 0–20; asistencia y actividades 0–100, hasta dos decimales; participación 1, 2 o 3; incidencias enteras 0–12. Son supuestos de simulación.</p>
        <p>El calendario simulado es 2025. Las fechas de ventana y objetivo usan AAAA-MM-DD; corte y disponibilidad llevan zona horaria. Los días académicos se comparan en America/Lima y los instantes se guardan en UTC. El horizonte es de 14 días.</p>
        <p>Conserva los valores faltantes vacíos; el servidor calcula su proporción. No añadas etiquetas, resultados futuros ni columnas. En esta versión no edites el CSV registrado: pide al administrador que revise su procedencia.</p>
        <p><code>{HEADERS.join(', ')}</code></p>
      </details>
    </section>
    {(requestError != null || stale || uncertain) && <div ref={resultRef} tabIndex={-1} className="import-request-error">
      {stale || uncertain ? <section className="import-blocked" aria-labelledby="import-conflict-title">
        <h2 id="import-conflict-title">{stale ? 'La vista previa necesita otra revisión' : 'Comprueba el resultado antes de continuar'}</h2>
        <p>{stale ? 'El contexto cambió. Vuelve a revisar el archivo para obtener una versión vigente; no se confirmará automáticamente.'
          : 'No recibimos un resultado confirmado. Consulta el lote para saber si la importación llegó a completarse.'}</p>
        {uncertain && batch && <button className="button secondary" type="button" onClick={() => void refreshBatch()} disabled={detail.isFetching}>Consultar resultado del lote</button>}
      </section> : <ErrorState error={requestError} />}
      {(stale || uncertain) && <RequestDetails error={requestError} />}
      {(stale || uncertain) && requestError != null && <p className="import-support">{errorMessage(requestError)}</p>}
    </div>}
    {batch && <section className="panel import-panel" aria-labelledby="import-review-title" aria-busy={detail.isFetching}>
      <div className="import-panel-heading"><div><p className="eyebrow">PASO 2</p><h2 id="import-review-title" ref={reviewRef} tabIndex={-1}>Revisar validaciones</h2></div>
        <button type="button" className="button secondary" onClick={() => void refreshBatch()} disabled={busy || detail.isFetching}>Consultar lote</button></div>
      {detail.isFetching && <p role="status" className="import-help">Consultando el estado guardado del lote…</p>}
      {detail.error != null && <ErrorState error={detail.error} onRetry={() => void refreshBatch()} />}
      <div className="import-batch-heading"><strong className={`import-state import-state-${batch.status.toLowerCase()}`}>
        {batch.status === 'COMMITTED' ? '✓ Ya importado' : batch.status === 'READY' ? '✓ Listo para confirmar' : batch.status === 'FAILED' ? '⚠ Requiere revisión' : 'Vista previa'}</strong>
        <span className="muted">{batch.file_name}</span></div>
      <dl className="import-counts"><div><dt>Registros del archivo</dt><dd>{batch.total_rows}</dd></div>
        <div><dt>Registros válidos</dt><dd>{batch.valid_rows}</dd></div><div><dt>Registros con errores</dt><dd>{batch.invalid_rows}</dd></div></dl>
      <p className="import-help">Consulta creada: {timestampLabel(batch.created_at)}.</p>
      <ImportErrors batch={batch} />
      {batch.errors.length > 0 && <p className="notice">No se puede confirmar un lote con errores. Solicita un CSV registrado que cumpla las correcciones y vuelve a revisarlo.</p>}
      {batch.status === 'COMMITTED' ? <div className="import-reused" role="status">
        <h3>{freshCommit ? 'Importación confirmada' : 'Se reutilizó la importación existente'}</h3>
        <p>{freshCommit ? `La confirmación registró ${result!.created_snapshots} cortes. Puedes consultar los registros del periodo.` : 'Este archivo ya fue confirmado en este periodo. La consulta no creó nuevos registros ni requiere otra confirmación.'}</p>
        {batch.committed_at && <p>Confirmado el {timestampLabel(batch.committed_at)}.</p>}
        <button type="button" className="button primary" onClick={() => onViewStudents(batch.period_id)}>Ver estudiantes del periodo</button>
      </div> : batch.status === 'READY' && batch.errors.length === 0 && batch.invalid_rows === 0 ? <>
        <p className="import-plan-title">Creación prevista al confirmar</p>
        <dl className="import-counts import-planned"><div><dt>Estudiantes previstos</dt><dd>{batch.planned_students}</dd></div>
          <div><dt>Matrículas previstas</dt><dd>{batch.planned_enrollments}</dd></div><div><dt>Cortes previstos</dt><dd>{batch.planned_snapshots}</dd></div></dl>
        <p className="import-help">Estas cantidades son un plan, aún no son registros confirmados.</p>
      </> : null}
    </section>}
    {batch && batch.status !== 'COMMITTED' && <section className="panel import-panel" aria-labelledby="import-confirm-title">
      <p className="eyebrow">PASO 3</p><h2 id="import-confirm-title">Confirmar importación</h2>
      {batch.status !== 'READY' || batch.errors.length || batch.invalid_rows ? <p className="muted">Primero completa la revisión sin errores. No se guardarán datos académicos de un lote inválido.</p> : <form onSubmit={commit} aria-busy={commitMutation.isPending}>
        <label className="import-confirm-check"><input type="checkbox" checked={confirmed} disabled={!!blocked || busy || stale || uncertain || !!detail.error || detail.isFetching}
          onChange={(event) => setConfirmed(event.target.checked)} />
          <span>Revisé las validaciones y confirmo importar este archivo sintético en el periodo seleccionado.</span></label>
        <p className="import-help">Se usa la versión {batch.preview_version} de esta vista previa. El servidor vuelve a comprobarla y guarda los datos en una sola transacción.</p>
        <button className="button primary" type="submit" disabled={!canCommit}>{commitMutation.isPending ? 'Confirmando importación…' : 'Confirmar importación'}</button>
      </form>}
    </section>}
    {result && <section className="import-reused" role="status"><h2>{result.reused_result ? 'Resultado reutilizado' : 'Importación confirmada'}</h2>
      <p>{result.reused_result ? 'No se crearon registros duplicados. Cortes del resultado guardado:' : 'Cortes registrados en esta confirmación:'} {result.created_snapshots}.</p></section>}
  </div>;
}
