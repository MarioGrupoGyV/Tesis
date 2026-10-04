import { useRef, type ReactNode } from 'react';
import type { User } from '../lib/api';
export const roleLabels: Record<User['role'], string> = { ADMIN: 'Administrador', TUTOR: 'Tutor', DIRECTOR: 'Directivo', RESEARCHER: 'Investigador' };
export function AppShell({ user, pathname, onNavigate, onLogout, context, notice, children }: {
  user: User; pathname: string; onNavigate: (path: string) => void; onLogout: () => void;
  context: ReactNode; notice: ReactNode; children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const menu = useRef<HTMLButtonElement>(null);
  const close = () => { dialog.current?.close(); menu.current?.focus(); };
  const go = (path: string) => { onNavigate(path); close(); };
  const nav = <nav aria-label="Navegación principal"><p className="nav-label">CONSULTA Y SEGUIMIENTO</p>
    {[['/', '⌂', 'Inicio'], ...(user.role !== 'RESEARCHER' ? [['/estudiantes', '▤', 'Estudiantes']] : [])].map(([path, icon, label]) =>
      <a key={path} href={path} aria-current={pathname === path || (path !== '/' && pathname.startsWith(path + '/')) ? 'page' : undefined} onClick={(event) => { event.preventDefault(); go(path); }}><span aria-hidden="true">{icon}</span>{label}<span className="nav-arrow" aria-hidden="true">›</span></a>)}
    {user.role !== 'RESEARCHER' && <a href="/alertas" aria-current={pathname.startsWith('/alertas') ? 'page' : undefined} onClick={(event) => { event.preventDefault(); go('/alertas'); }}><span aria-hidden="true">♧</span>Alertas<span className="nav-arrow" aria-hidden="true">›</span></a>}
    {user.role === 'ADMIN' && <a href="/datos" aria-current={pathname === '/datos' ? 'page' : undefined} onClick={(event) => { event.preventDefault(); go('/datos'); }}><span aria-hidden="true">⇧</span>Datos<span className="nav-arrow" aria-hidden="true">›</span></a>}
    {user.role !== 'RESEARCHER' && <a href="/reportes" aria-current={pathname === '/reportes' ? 'page' : undefined} onClick={(event) => { event.preventDefault(); go('/reportes'); }}><span aria-hidden="true">▥</span>Reportes<span className="nav-arrow" aria-hidden="true">›</span></a>}
    {user.role === 'ADMIN' && <><p className="nav-label nav-secondary">ADMINISTRACIÓN</p><a href="/modelos" aria-current={pathname.startsWith('/modelos') ? 'page' : undefined} onClick={(event) => { event.preventDefault(); go('/modelos'); }}><span aria-hidden="true">◇</span>Modelos<span className="nav-arrow" aria-hidden="true">›</span></a></>}
  </nav>;
  return <div className="workspace-layout"><a className="skip-link" href="#main-content">Ir al contenido</a>
    <aside className="desktop-sidebar"><a className="brand" href="/" onClick={(event) => { event.preventDefault(); go('/'); }}><span className="brand-mark">SE</span><span>Seguimiento<br /><strong>Escolar</strong></span></a>{nav}<div className="sidebar-note"><strong>Estudio con datos sintéticos</strong><p>Registros y estimaciones generados. No corresponden a estudiantes reales.</p></div></aside>
    <div className="workspace-body"><header className="topbar"><button ref={menu} type="button" className="menu-trigger button secondary" aria-label="Abrir menú" onClick={() => dialog.current?.showModal()}>☰ <span>Menú</span></button><span className="topbar-name">Seguimiento Escolar</span><div className="user-summary"><span className="user-avatar" aria-hidden="true">{user.display_name.slice(0, 1)}</span><div><strong>{user.display_name}</strong><small>{roleLabels[user.role]}</small></div></div><button className="button secondary logout-button" type="button" onClick={onLogout}>Cerrar sesión</button></header>
      {context}<main id="main-content" className="workspace" tabIndex={-1}>{notice}{children}</main><footer className="site-footer"><span>Seguimiento Escolar · Estudio sintético</span><span>Fechas en America/Lima</span></footer></div>
    <dialog ref={dialog} className="mobile-menu" onClose={() => menu.current?.focus()} aria-labelledby="menu-title"><div className="mobile-menu-heading"><h2 id="menu-title">Navegación</h2><button className="button secondary" type="button" onClick={close} aria-label="Cerrar menú">✕</button></div>{nav}<p className="muted">Estudio con datos sintéticos. No corresponde a estudiantes reales.</p></dialog>
  </div>;
}
