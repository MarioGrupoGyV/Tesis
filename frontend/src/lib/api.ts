import type { components } from './api.generated';

export type User = components['schemas']['User'];
export type Period = components['schemas']['Period'];
export type Section = components['schemas']['Section'];
export type ProcessingStatus = components['schemas']['ProcessingStatus'];
type ApiErrorBody = components['schemas']['Error'];
type LoginInput = components['schemas']['LoginInput'];
type LoginResult = components['schemas']['LoginResult'];
type Csrf = components['schemas']['Csrf'];

// Kept only in memory. Session authentication is the server's HttpOnly cookie.
let csrfToken: string | null = null;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      credentials: 'include',
      cache: 'no-store',
      headers: { Accept: 'application/json', ...options.headers },
    });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'No pudimos conectar con el sistema. Revisa la conexión e inténtalo de nuevo.');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => null) as ApiErrorBody | null;
    if (response.status === 401) csrfToken = null;
    throw new ApiError(
      response.status,
      error?.code ?? 'REQUEST_FAILED',
      error?.message ?? 'No pudimos completar la solicitud. Inténtalo de nuevo.',
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  async restoreSession(): Promise<User> {
    const user = await request<User>('/auth/me');
    const csrf = await request<Csrf>('/auth/csrf');
    csrfToken = csrf.csrf_token;
    return user;
  },
  async login(input: LoginInput): Promise<User> {
    const result = await request<LoginResult>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    csrfToken = result.csrf_token;
    return result.user;
  },
  async logout(): Promise<void> {
    if (!csrfToken) {
      const csrf = await request<Csrf>('/auth/csrf');
      csrfToken = csrf.csrf_token;
    }
    await request<void>('/auth/logout', {
      method: 'POST',
      headers: { 'X-CSRF-Token': csrfToken },
    });
    csrfToken = null;
  },
  periods(): Promise<Period[]> {
    return request<Period[]>('/periods');
  },
  sections(periodId: Period['id']): Promise<Section[]> {
    return request<Section[]>(`/sections?period_id=${encodeURIComponent(periodId)}`);
  },
  processingStatus(): Promise<ProcessingStatus> {
    return request<ProcessingStatus>('/processing/status');
  },
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'La sesión terminó. Vuelve a ingresar para continuar.';
    if (error.status === 403) return 'Tu cuenta no tiene permiso para realizar esta acción.';
    if (error.status === 429) return 'Se alcanzó el límite de intentos. Espera unos minutos antes de volver a ingresar.';
    return error.message;
  }
  return 'Ocurrió un error. Inténtalo de nuevo.';
}
