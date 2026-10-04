import { useCallback, useEffect, useState } from 'react';
import { LoginForm } from '../features/auth/LoginForm';
import { api, ApiError, errorMessage, type Period, type Section, type User } from '../lib/api';

const roleLabels: Record<User['role'], string> = {
  ADMIN: 'Administrador',
  TUTOR: 'Tutor',
  DIRECTOR: 'Directivo',
  RESEARCHER: 'Investigador',
};

function dateLabel(date: string): string {
  return new Intl.DateTimeFormat('es-PE', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'America/Lima' }).format(new Date(`${date}T12:00:00-05:00`));
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [startupError, setStartupError] = useState('');
  const [notice, setNotice] = useState('');
  const [sessionError, setSessionError] = useState('');
  const [loggingOut, setLoggingOut] = useState(false);

  async function restore() {
    setChecking(true);
    setStartupError('');
    try {
      setUser(await api.restoreSession());
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setUser(null);
      else setStartupError(errorMessage(error));
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => { void restore(); }, []);

  const sessionExpired = useCallback(() => {
    setUser(null);
    setNotice('La sesión terminó. Vuelve a ingresar para continuar.');
    setSessionError('');
  }, []);

  async function logout() {
    setLoggingOut(true);
    setSessionError('');
    try {
      await api.logout();
      setUser(null);
      setNotice('Sesión cerrada correctamente.');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) sessionExpired();
      else setSessionError(errorMessage(error));
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Seguimiento Escolar, Inicio"><span className="brand-mark" aria-hidden="true">SE</span><span>Seguimiento<br /><strong>Escolar</strong></span></a>
        <div className="header-actions">{user && <button type="button" className="button secondary" disabled={loggingOut} onClick={() => void logout()}>{loggingOut ? 'Cerrando…' : 'Cerrar sesión'}</button>}</div>
      </header>
      {checking ? <main className="status-page"><p className="eyebrow">ACCESO SEGURO</p><h1>Comprobando tu sesión…</h1><p className="muted" role="status">Un momento, estamos conectando con el sistema.</p></main>
        : startupError ? <main className="status-page"><h1>No pudimos comprobar tu sesión</h1><p className="notice error" role="alert">{startupError}</p><button type="button" className="button primary" onClick={() => void restore()}>Volver a intentar</button></main>
          : user ? <main className="workspace"><div className="page-heading"><p className="eyebrow">INICIO</p><h1>Bienvenido, {user.display_name}</h1><p className="muted">Consulta el contexto autorizado para tu cuenta.</p></div>{sessionError && <p className="notice error" role="alert">{sessionError}</p>}<div className="account-strip"><span className="account-icon" aria-hidden="true">✓</span><div><strong>Sesión activa</strong><p>{roleLabels[user.role]}</p></div></div>{user.role === 'RESEARCHER' ? <section className="panel" aria-labelledby="restricted-title"><h2 id="restricted-title">Acceso de investigador</h2><p className="notice" role="status">Tu rol de investigador no tiene acceso al contexto escolar.</p><p className="muted">Puedes consultar y cerrar tu sesión. No se muestran periodos, secciones ni casos.</p></section> : <Catalogs user={user} onExpired={sessionExpired} />}</main>
            : <LoginForm notice={notice} onLogin={(current) => { setUser(current); setNotice(''); }} />}
      <footer className="site-footer"><span>Seguimiento Escolar</span><span>America/Lima</span></footer>
    </div>
  );
}

function Catalogs({ user, onExpired }: { user: User; onExpired: () => void }) {
  const [periods, setPeriods] = useState<Period[]>([]);
  const [periodId, setPeriodId] = useState('');
  const [sections, setSections] = useState<Section[]>([]);
  const [loadingPeriods, setLoadingPeriods] = useState(true);
  const [loadingSections, setLoadingSections] = useState(false);
  const [periodError, setPeriodError] = useState('');
  const [sectionError, setSectionError] = useState('');
  const [periodReload, setPeriodReload] = useState(0);
  const [sectionReload, setSectionReload] = useState(0);

  useEffect(() => {
    let active = true;
    setLoadingPeriods(true);
    setPeriodError('');
    void api.periods().then((items) => {
      if (!active) return;
      setPeriods(items);
      setPeriodId((previous) => items.some((period) => period.id === previous) ? previous : (items[0]?.id ?? ''));
    }).catch((error: unknown) => {
      if (!active) return;
      if (error instanceof ApiError && error.status === 401) onExpired();
      else setPeriodError(errorMessage(error));
    }).finally(() => { if (active) setLoadingPeriods(false); });
    return () => { active = false; };
  }, [user.id, periodReload, onExpired]);

  useEffect(() => {
    let active = true;
    setSections([]);
    setSectionError('');
    if (!periodId) { setLoadingSections(false); return () => { active = false; }; }
    setLoadingSections(true);
    void api.sections(periodId).then((items) => { if (active) setSections(items); }).catch((error: unknown) => {
      if (!active) return;
      if (error instanceof ApiError && error.status === 401) onExpired();
      else setSectionError(errorMessage(error));
    }).finally(() => { if (active) setLoadingSections(false); });
    return () => { active = false; };
  }, [periodId, sectionReload, onExpired]);

  const selectedPeriod = periods.find((period) => period.id === periodId);

  return (
    <div className="context-grid">
      <section className="panel period-card" aria-labelledby="period-title" aria-busy={loadingPeriods}>
        <p className="eyebrow">CONTEXTO ACADÉMICO</p><h2 id="period-title">Periodo de consulta</h2>
        {loadingPeriods ? <p className="loading-copy" role="status">Cargando periodos autorizados…</p>
          : periodError ? <div><p className="notice error" role="alert">{periodError}</p><button type="button" className="button secondary" onClick={() => setPeriodReload((value) => value + 1)}>Volver a intentar</button></div>
            : periods.length === 0 ? <p className="empty-copy" role="status">No hay periodos configurados para tu cuenta.</p>
              : <><label htmlFor="period">Selecciona un periodo</label><select id="period" value={periodId} onChange={(event) => setPeriodId(event.target.value)}>{periods.map((period) => <option key={period.id} value={period.id}>{period.code} · {period.school_year}</option>)}</select>{selectedPeriod && <dl className="period-details"><div><dt>Año escolar</dt><dd>{selectedPeriod.school_year}</dd></div><div><dt>Fechas</dt><dd>{dateLabel(selectedPeriod.start_date)} — {dateLabel(selectedPeriod.end_date)}</dd></div><div><dt>Estado</dt><dd><span className={`state-badge ${selectedPeriod.is_locked ? 'locked' : 'open'}`}>{selectedPeriod.is_locked ? '🔒 Bloqueado' : '✓ Abierto'}</span></dd></div><div><dt>Origen</dt><dd>Información institucional</dd></div></dl>}</>}
      </section>
      <section className="panel sections-card" aria-labelledby="sections-title" aria-busy={loadingSections || loadingPeriods}>
        <div className="section-heading"><div><p className="eyebrow">ALCANCE DE TU CUENTA</p><h2 id="sections-title">Secciones autorizadas</h2></div>{!loadingSections && !loadingPeriods && !sectionError && !periodError && periodId && <span className="count-badge" aria-label={`${sections.length} secciones autorizadas`}>{sections.length}</span>}</div>
        <p className="muted section-description">{user.role === 'TUTOR' ? 'Se muestran las secciones asignadas a tu cuenta.' : 'Se muestran las secciones que puedes consultar en el periodo elegido.'}</p>
        {loadingPeriods || loadingSections ? <p className="loading-copy" role="status">Cargando contexto autorizado…</p>
          : !periodId || periodError ? <p className="empty-copy">No hay secciones disponibles. Primero debe configurarse un periodo.</p>
            : sectionError ? <div><p className="notice error" role="alert">{sectionError}</p><button type="button" className="button secondary" onClick={() => setSectionReload((value) => value + 1)}>Volver a intentar</button></div>
              : sections.length === 0 ? <p className="empty-copy" role="status">No hay secciones asignadas en este periodo.</p>
                : <><div className="table-container"><table><caption className="sr-only">Secciones autorizadas para {selectedPeriod?.code}</caption><thead><tr><th scope="col">Sección</th><th scope="col">Grado</th><th scope="col">Año escolar</th></tr></thead><tbody>{sections.map((section) => <tr key={section.id}><td><span className="section-symbol" aria-hidden="true">▦</span><strong>{section.code}</strong></td><td>{section.grade}.º</td><td>{section.school_year}</td></tr>)}</tbody></table></div><p className="result-note" role="status">✓ Contexto autorizado cargado.</p></>}
      </section>
    </div>
  );
}
