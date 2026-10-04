import type { components, operations } from './api.generated';
export type User = components['schemas']['User'];
export type Period = components['schemas']['Period'];
export type Section = components['schemas']['Section'];
export type ProcessingStatus = components['schemas']['ProcessingStatus'];
export type Student = components['schemas']['Student'];
export type StudentPage = components['schemas']['StudentPage'];
export type StudentDetail = components['schemas']['StudentDetail'];
export type Snapshot = components['schemas']['Snapshot'];
export type TimelineEventPage = components['schemas']['TimelineEventPage'];
export type Model = components['schemas']['Model'];
export type ModelPage = components['schemas']['ModelPage'];
export type Prediction = components['schemas']['Prediction'];
export type PredictionRunResult = components['schemas']['PredictionRunResult'];
export type ImportBatch = components['schemas']['ImportBatch'];
export type ImportCommit = components['schemas']['ImportCommit'];
export type Alert = components['schemas']['Alert'];
export type Intervention = components['schemas']['Intervention'];
export type AlertCase = components['schemas']['AlertCase'];
export type AlertPage = components['schemas']['AlertPage'];
export type AlertDetail = components['schemas']['AlertDetail'];
export type AlertPatch = components['schemas']['AlertPatch'];
export type InterventionView = components['schemas']['InterventionView'];
export type InterventionCreate = components['schemas']['InterventionCreate'];
export type InterventionPatch = components['schemas']['InterventionPatch'];
export type InterventionCreateResult = components['schemas']['InterventionCreateResult'];
export type FollowupResult = components['schemas']['FollowupResult'];
export type ReportSummary = components['schemas']['ReportSummary'];
export type AlertFilters = operations['listAlerts']['parameters']['query'];
export type ReportFilters = operations['reportSummary']['parameters']['query'];
export type StudentFilters = operations['students']['parameters']['query'];
type ErrorBody = components['schemas']['Error'];
let csrfToken: string | null = null;
let sessionEpoch = 0;
let serverClock: { instant: number; receivedAt: number } | null = null;
export const SESSION_EXPIRED_EVENT = 'se:session-expired';
export function clearSessionMemory(): void { csrfToken = null; serverClock = null; sessionEpoch += 1; }
export function currentEvaluationInstant(): Date | null {
  return serverClock ? new Date(serverClock.instant + performance.now() - serverClock.receivedAt) : null;
}
export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string,
    public readonly details: ErrorBody['details'] = [], public readonly requestId?: string) {
    super(message); this.name = 'ApiError';
  }
}
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const epoch = sessionEpoch;
  let response: Response;
  try { response = await fetch(`/api/v1${path}`, { ...options, credentials: 'include', cache: 'no-store', headers: { Accept: 'application/json', ...options.headers } }); }
  catch (error) {
    if (options.signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) throw error;
    throw new ApiError(0, 'NETWORK_ERROR', 'No pudimos conectar con el sistema. Revisa la conexión y vuelve a intentar.');
  }
  if (epoch !== sessionEpoch) throw new DOMException('Sesión cambiada', 'AbortError');
  // Date procede de la API del mismo origen; su precisión de segundos ofrece
  // una estimación conservadora sin depender del reloj de Windows. El servidor
  // conserva la validación de as_of y la selección temporal de cortes.
  const serverDate = Date.parse(response.headers.get('Date') ?? '');
  if (Number.isFinite(serverDate)) serverClock = { instant: serverDate, receivedAt: performance.now() };
  if (!response.ok) {
    const body = await response.json().catch(() => null) as ErrorBody | null;
    if (epoch !== sessionEpoch) throw new DOMException('Sesión cambiada', 'AbortError');
    if (response.status === 401 && path !== '/auth/login') { clearSessionMemory(); window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT)); }
    throw new ApiError(response.status, body?.code ?? 'REQUEST_FAILED', body?.message ?? 'No pudimos completar la solicitud.', body?.details ?? [], body?.request_id);
  }
  if (response.status === 204) return undefined as T;
  let body: unknown;
  try { body = await response.json(); }
  catch (error) {
    if (epoch !== sessionEpoch || options.signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) throw new DOMException('Solicitud cancelada', 'AbortError');
    throw new ApiError(0, 'NETWORK_ERROR', 'No pudimos leer la respuesta del sistema. Comprueba el estado antes de repetir la acción.');
  }
  if (epoch !== sessionEpoch) throw new DOMException('Sesión cambiada', 'AbortError');
  return body as T;
}
function query(values: Record<string, string | number | undefined | null>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') params.set(key, String(value)); });
  return params.toString();
}
async function csrf(signal?: AbortSignal): Promise<string> {
  if (!csrfToken) csrfToken = (await request<components['schemas']['Csrf']>('/auth/csrf', { signal })).csrf_token;
  return csrfToken;
}
async function write<T>(path: string, body: unknown, signal?: AbortSignal, method: 'POST' | 'PATCH' = 'POST'): Promise<T> {
  const token = await csrf(signal);
  return request<T>(path, { method, signal, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token }, body: JSON.stringify(body) });
}
async function requestCsv(path: string, signal?: AbortSignal): Promise<Blob> {
  const epoch = sessionEpoch;
  let response: Response;
  try { response = await fetch(`/api/v1${path}`, { signal, credentials: 'include', cache: 'no-store', headers: { Accept: 'text/csv, application/json' } }); }
  catch (error) {
    if (signal?.aborted || error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'NETWORK_ERROR', 'No pudimos conectar para obtener el reporte.');
  }
  if (epoch !== sessionEpoch || signal?.aborted) throw new DOMException('Sesión cambiada', 'AbortError');
  const serverDate = Date.parse(response.headers.get('Date') ?? '');
  if (Number.isFinite(serverDate)) serverClock = { instant: serverDate, receivedAt: performance.now() };
  const contentType = response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase();
  if (!response.ok || contentType === 'application/json') {
    const body = await response.json().catch(() => null) as ErrorBody | null;
    if (epoch !== sessionEpoch || signal?.aborted) throw new DOMException('Sesión cambiada', 'AbortError');
    if (response.status === 401) { clearSessionMemory(); window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT)); }
    throw new ApiError(response.status, body?.code ?? 'REQUEST_FAILED', body?.message ?? 'No pudimos obtener el reporte CSV.', body?.details ?? [], body?.request_id);
  }
  if (contentType !== 'text/csv') throw new ApiError(0, 'INVALID_CSV_RESPONSE', 'El sistema no devolvió un CSV válido. No se inició una descarga.');
  let blob: Blob;
  try { blob = await response.blob(); }
  catch (error) {
    if (epoch !== sessionEpoch || signal?.aborted || error instanceof DOMException && error.name === 'AbortError') throw new DOMException('Solicitud cancelada', 'AbortError');
    throw new ApiError(0, 'NETWORK_ERROR', 'La respuesta CSV quedó incompleta. No se inició una descarga.');
  }
  if (epoch !== sessionEpoch || signal?.aborted) throw new DOMException('Sesión cambiada', 'AbortError');
  return blob;
}
export const api = {
  async restoreSession(signal?: AbortSignal): Promise<User> {
    const user = await request<User>('/auth/me', { signal }); await csrf(signal); return user;
  },
  async login(input: components['schemas']['LoginInput'], signal?: AbortSignal): Promise<User> {
    const result = await request<components['schemas']['LoginResult']>('/auth/login', { method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input) });
    csrfToken = result.csrf_token; return result.user;
  },
  async logout(signal?: AbortSignal): Promise<void> {
    const token = await csrf(signal);
    await request<void>('/auth/logout', { method: 'POST', signal, headers: { 'X-CSRF-Token': token } }); clearSessionMemory();
  },
  periods: (signal?: AbortSignal) => request<Period[]>('/periods', { signal }),
  sections: (periodId: string, signal?: AbortSignal) => request<Section[]>(`/sections?${query({ period_id: periodId })}`, { signal }),
  processingStatus: (signal?: AbortSignal) => request<ProcessingStatus>('/processing/status', { signal }),
  students: (filters: StudentFilters, signal?: AbortSignal) => request<StudentPage>(`/students?${query(filters)}`, { signal }),
  student: (id: string, periodId: string, signal?: AbortSignal) => request<StudentDetail>(`/students/${encodeURIComponent(id)}?${query({ period_id: periodId })}`, { signal }),
  timeline: (id: string, filters: { period_id: string; page?: number; page_size?: number }, signal?: AbortSignal) => request<TimelineEventPage>(`/students/${encodeURIComponent(id)}/timeline?${query(filters)}`, { signal }),
  models: (filters: { page?: number; page_size?: number }, signal?: AbortSignal) => request<ModelPage>(`/models?${query(filters)}`, { signal }),
  model: (id: string, signal?: AbortSignal) => request<Model>(`/models/${encodeURIComponent(id)}`, { signal }),
  prediction: (id: string, signal?: AbortSignal) => request<Prediction>(`/predictions/${encodeURIComponent(id)}`, { signal }),
  runPredictions: (input: components['schemas']['PredictionRunInput'], signal?: AbortSignal) => write<PredictionRunResult>('/predictions/run', input, signal),
  async previewImport(file: File, periodId: string, signal?: AbortSignal): Promise<ImportBatch> {
    const token = await csrf(signal); const body = new FormData(); body.append('file', file); body.append('period_id', periodId);
    return request<ImportBatch>('/imports/preview', { method: 'POST', signal, headers: { 'X-CSRF-Token': token }, body });
  },
  importDetail: (id: string, signal?: AbortSignal) => request<ImportBatch>(`/imports/${encodeURIComponent(id)}`, { signal }),
  commitImport: (id: string, version: number, signal?: AbortSignal) => write<ImportCommit>(`/imports/${encodeURIComponent(id)}/commit`, { expected_preview_version: version }, signal),
  syncAlerts: (periodId: string, signal?: AbortSignal) => write<FollowupResult>('/alerts/sync', { period_id: periodId }, signal),
  alerts: (filters: AlertFilters, signal?: AbortSignal) => request<AlertPage>(`/alerts?${query(filters)}`, { signal }),
  alert: (id: string, signal?: AbortSignal) => request<AlertDetail>(`/alerts/${encodeURIComponent(id)}`, { signal }),
  updateAlert: (id: string, input: AlertPatch, signal?: AbortSignal) => write<AlertDetail>(`/alerts/${encodeURIComponent(id)}`, input, signal, 'PATCH'),
  createIntervention: (input: InterventionCreate, signal?: AbortSignal) => write<InterventionCreateResult>('/interventions', input, signal),
  updateIntervention: (id: string, input: InterventionPatch, signal?: AbortSignal) => write<InterventionView>(`/interventions/${encodeURIComponent(id)}`, input, signal, 'PATCH'),
  reportSummary: (filters: ReportFilters, signal?: AbortSignal) => request<ReportSummary>(`/reports/summary?${query(filters)}`, { signal }),
  exportReportCsv: (filters: Omit<ReportFilters, 'page' | 'page_size'>, signal?: AbortSignal) => requestCsv(`/reports/export.csv?${query(filters)}`, signal),
};
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'La sesión terminó. Vuelve a ingresar para continuar.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para realizar esta acción.';
    if (error.status === 404) return 'No encontramos el recurso o no está disponible para tu cuenta.';
    if (error.status === 429) return 'Se alcanzó el límite de solicitudes. Espera unos minutos antes de volver a intentar.';
    if (error.status === 503) return 'El servicio no está disponible temporalmente. Vuelve a intentar más tarde.';
    return error.message;
  }
  return 'No pudimos completar la acción. Vuelve a intentar.';
}
