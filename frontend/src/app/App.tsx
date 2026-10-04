import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { LoginForm } from '../features/auth/LoginForm';
import { HomePage } from '../features/home/HomePage';
import { StudentsPage } from '../features/students/StudentsPage';
import { StudentDetailPage } from '../features/students/StudentDetailPage';
import { ImportsPage } from '../features/imports/ImportsPage';
import { ModelsPage } from '../features/models/ModelsPage';
import { ModelDetailPage } from '../features/models/ModelDetailPage';
import { AlertsPage } from '../features/alerts/AlertsPage';
import { AlertDetailPage } from '../features/alerts/AlertDetailPage';
import { ReportsPage } from '../features/reports/ReportsPage';
import { AppShell } from '../components/AppShell';
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../components/ui';
import { api, ApiError, clearSessionMemory, errorMessage, SESSION_EXPIRED_EVENT, type User } from '../lib/api';
import { navigate, useLocation } from '../lib/navigation';

export function App() {
  const cache = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const currentUser = useRef(user); currentUser.current = user;
  const [checking, setChecking] = useState(true);
  const [startupError, setStartupError] = useState<unknown>(null);
  const [notice, setNotice] = useState('');
  const [sessionError, setSessionError] = useState<unknown>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [restoreVersion, setRestoreVersion] = useState(0);
  const expire = useCallback(() => {
    clearSessionMemory(); void cache.cancelQueries(); cache.clear();
    if (currentUser.current) { navigate('/', true); setNotice('La sesión terminó. Vuelve a ingresar para continuar.'); }
    setUser(null); setSessionError(null);
  }, [cache]);
  useEffect(() => { window.addEventListener(SESSION_EXPIRED_EVENT, expire); return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expire); }, [expire]);
  useEffect(() => {
    const controller = new AbortController(); setChecking(true); setStartupError(null);
    void api.restoreSession(controller.signal).then(setUser).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 401) setUser(null); else setStartupError(error);
    }).finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, [restoreVersion]);
  async function logout() {
    setLoggingOut(true); setSessionError(null);
    await cache.cancelQueries(); cache.clear(); clearSessionMemory();
    try { await api.logout(); setUser(null); setNotice('Sesión cerrada correctamente.'); navigate('/', true); }
    catch (error) { if (error instanceof ApiError && error.status === 401) expire(); else setSessionError(error); }
    finally { setLoggingOut(false); }
  }
  if (checking || loggingOut) return <div className="auth-shell"><Brand /><main className="status-page"><PageHeader title={loggingOut ? 'Cerrando tu sesión…' : 'Comprobando tu sesión…'} /><LoadingState label="Un momento, estamos conectando con el sistema." /></main></div>;
  if (startupError) return <div className="auth-shell"><Brand /><main className="status-page"><PageHeader title="No pudimos comprobar tu sesión" /><ErrorState error={startupError} onRetry={() => setRestoreVersion((value) => value + 1)} /></main></div>;
  if (!user) return <div className="auth-shell"><Brand /><LoginForm notice={notice} onLogin={(actor) => { void cache.cancelQueries(); cache.clear(); setUser(actor); setNotice(''); }} /><footer className="site-footer"><span>Seguimiento Escolar · Estudio sintético</span><span>America/Lima</span></footer></div>;
  return <AuthenticatedApp key={user.id} user={user} onLogout={() => void logout()} onExpired={expire} sessionError={sessionError} />;
}
function Brand() {
  return <header className="site-header"><a className="brand" href="/"><span className="brand-mark">SE</span><span>Seguimiento<br /><strong>Escolar</strong></span></a><span className="access-label">ACCESO AUTORIZADO</span></header>;
}
function AuthenticatedApp({ user, onLogout, onExpired, sessionError }: { user: User; onLogout: () => void; onExpired: () => void; sessionError: unknown }) {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const periodId = params.get('period_id') ?? '';
  const sectionId = params.get('section_id') ?? '';
  const schoolContext = user.role !== 'RESEARCHER';
  const periods = useQuery({ queryKey: [user.id, user.role, 'periods'], queryFn: ({ signal }) => api.periods(signal), enabled: schoolContext });
  const period = periods.data?.find((item) => item.id === periodId) ?? null;
  const sections = useQuery({ queryKey: [user.id, user.role, 'sections', periodId], queryFn: ({ signal }) => api.sections(periodId, signal), enabled: schoolContext && !!period });
  const status = useQuery({ queryKey: [user.id, user.role, 'processing'], queryFn: ({ signal }) => api.processingStatus(signal) });
  const processing = status.isError ? null : status.data ?? null;
  const validSection = sections.data?.some((section) => section.id === sectionId) ? sectionId : '';
  useEffect(() => {
    if (schoolContext && periods.data?.length && !periodId) {
      const next = new URLSearchParams(location.search); next.set('period_id', (periods.data.find((item) => item.data_origin === 'SYNTHETIC') ?? periods.data[0]).id);
      navigate(location.pathname + '?' + next.toString(), true);
    }
  }, [schoolContext, periods.data, periodId, location.pathname, location.search]);
  useEffect(() => {
    if (sections.data && sectionId && !validSection) { const next = new URLSearchParams(location.search); next.delete('section_id'); navigate(location.pathname + '?' + next.toString(), true); }
  }, [sections.data, sectionId, validSection, location.pathname, location.search]);
  useEffect(() => { document.querySelector<HTMLElement>('#main-content h1')?.focus(); }, [location.pathname]);
  function go(path: string) {
    const next = new URL(path, window.location.origin);
    if (schoolContext && periodId && !next.searchParams.has('period_id')) next.searchParams.set('period_id', periodId);
    if (schoolContext && validSection && !next.searchParams.has('section_id')) next.searchParams.set('section_id', validSection);
    navigate(next.pathname + next.search);
  }
  function changePeriod(id: string) {
    const path = location.pathname.startsWith('/estudiantes/') ? '/estudiantes' : location.pathname.startsWith('/alertas/') ? '/alertas' : location.pathname;
    navigate(path + '?' + new URLSearchParams({ period_id: id }).toString());
  }
  function changeSection(id: string) {
    const next = new URLSearchParams(location.search); next.delete('page'); next.delete('search'); next.delete('risk_level');
    if (id) next.set('section_id', id); else next.delete('section_id');
    const path = location.pathname.startsWith('/alertas/') ? '/alertas' : location.pathname.startsWith('/estudiantes/') ? '/estudiantes' : location.pathname;
    navigate(path + '?' + next.toString());
  }
  const context = !schoolContext ? null : <section className="context-bar" aria-label="Contexto de consulta">
    {periods.isPending ? <LoadingState label="Cargando periodos autorizados…" /> : periods.isError ? <ErrorState error={periods.error} onRetry={() => void periods.refetch()} /> : periods.data.length === 0 ? <p className="muted">No hay periodos configurados para tu cuenta.</p> : <><div className="context-field"><label htmlFor="period">Periodo de consulta</label><select id="period" value={periodId} onChange={(event) => changePeriod(event.target.value)}><option value="" disabled>Selecciona un periodo</option>{periods.data.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.school_year}</option>)}</select></div><div className="context-field"><label htmlFor="section">Sección autorizada</label><select id="section" value={validSection} disabled={!period || sections.isPending || sections.isError} onChange={(event) => changeSection(event.target.value)}><option value="">Todas las autorizadas</option>{sections.data?.map((item) => <option key={item.id} value={item.id}>{item.grade}.º · {item.code}</option>)}</select></div><span className={`badge ${period?.is_locked ? 'locked' : ''}`}>{period?.data_origin === 'SYNTHETIC' ? 'Datos sintéticos' : 'Contexto sin procesamiento'}{period?.is_locked && ' · Bloqueado'}</span></>}
    {sections.isError && <ErrorState error={sections.error} onRetry={() => void sections.refetch()} />}
  </section>;
  const notice = <>{sessionError && <ErrorState error={sessionError} />}{status.isPending ? <LoadingState label="Consultando el alcance del sistema…" /> : status.isError ? <div className="processing-warning"><p className="notice">No pudimos consultar el estado de procesamiento. Las acciones sensibles permanecen deshabilitadas.</p><ErrorState error={status.error} onRetry={() => void status.refetch()} /></div> : <div className="synthetic-banner" role="status"><span aria-hidden="true">◇</span><div><strong>Estudio con datos sintéticos</strong><p>{processing?.notice}</p></div><span className="scope-label">REAL bloqueado</span></div>}</>;
  const pathname = location.pathname.replace(/\/$/, '') || '/';
  const studentMatch = pathname.match(/^\/estudiantes\/([^/]+)$/);
  const modelMatch = pathname.match(/^\/modelos\/([^/]+)$/);
  const alertMatch = pathname.match(/^\/alertas\/([^/]+)$/);
  const forbidden = user.role === 'RESEARCHER' && pathname !== '/' || user.role !== 'ADMIN' && (pathname === '/datos' || pathname.startsWith('/modelos'));
  let page;
  if (forbidden) page = <><PageHeader title="Acceso no disponible" /><EmptyState title="Tu rol no permite abrir esta vista"><p>Vuelve a Inicio para conocer las consultas autorizadas.</p><button className="button secondary" type="button" onClick={() => go('/')}>Volver a Inicio</button></EmptyState></>;
  else if (pathname === '/' && schoolContext && (periods.isPending || period && sections.isPending)) page = <><PageHeader title="Inicio" /><LoadingState label="Cargando contexto autorizado…" /></>;
  else if (pathname === '/' && schoolContext && (periods.isError || sections.isError)) page = <><PageHeader title="Inicio" /><ErrorState error={periods.error ?? sections.error} onRetry={() => { void periods.refetch(); if (period) void sections.refetch(); }} /></>;
  else if (pathname === '/') page = <HomePage key={periodId + validSection} user={user} period={period} sectionId={validSection} sections={sections.data ?? []} processing={processing} onNavigate={go} />;
  else if (pathname === '/estudiantes' && period && sections.isPending) page = <LoadingState label="Cargando secciones autorizadas…" />;
  else if (pathname === '/estudiantes' && period && sections.isError) page = <ErrorState error={sections.error} onRetry={() => void sections.refetch()} />;
  else if (pathname === '/estudiantes') page = <StudentsPage key={periodId + validSection} user={user} period={period} sectionId={validSection} onNavigate={go} />;
  else if (studentMatch) page = <StudentDetailPage key={periodId + studentMatch[1]} user={user} period={period} studentId={studentMatch[1]} onNavigate={go} />;
  else if (pathname === '/datos') page = <ImportsPage user={user} period={period} status={processing} statusLoading={status.isPending} statusError={status.isError ? errorMessage(status.error) : ''} onRetryStatus={() => void status.refetch()} onUnauthorized={onExpired} onCommitted={(id) => navigate('/estudiantes?' + new URLSearchParams({ period_id: id }))} onViewStudents={(id) => navigate('/estudiantes?' + new URLSearchParams({ period_id: id }))} />;
  else if (pathname === '/modelos') page = <ModelsPage user={user} period={period} processing={processing} onNavigate={go} />;
  else if (modelMatch) page = <ModelDetailPage user={user} period={period} processing={processing} modelId={modelMatch[1]} onNavigate={go} />;
  else if ((pathname === '/alertas' || pathname === '/reportes') && period && sections.isPending) page = <LoadingState label="Cargando secciones autorizadas…" />;
  else if ((pathname === '/alertas' || pathname === '/reportes') && period && sections.isError) page = <ErrorState error={sections.error} onRetry={() => void sections.refetch()} />;
  else if (pathname === '/alertas') page = <AlertsPage key={periodId + validSection} user={user} period={period} sectionId={validSection} processing={processing} onNavigate={go} />;
  else if (alertMatch) page = <AlertDetailPage key={periodId + alertMatch[1]} user={user} period={period} processing={processing} alertId={alertMatch[1]} onNavigate={go} />;
  else if (pathname === '/reportes') page = <ReportsPage key={periodId + validSection} user={user} period={period} sectionId={validSection} processing={processing} onNavigate={go} />;
  else page = <><PageHeader title="Página no encontrada" /><EmptyState title="Esta dirección no está disponible"><button className="button secondary" type="button" onClick={() => go('/')}>Volver a Inicio</button></EmptyState></>;
  return <AppShell user={user} pathname={pathname} context={context} notice={notice} onNavigate={go} onLogout={onLogout}>{page}</AppShell>;
}
