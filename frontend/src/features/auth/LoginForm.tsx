import { useState, type FormEvent } from 'react';
import { api, ApiError, errorMessage, type User } from '../../lib/api';

export function LoginForm({ onLogin, notice }: { onLogin: (user: User) => void; notice: string }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const user = await api.login({ email: email.trim(), password });
      setPassword('');
      onLogin(user);
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 401
        ? 'Correo o contraseña incorrectos. Revisa tus credenciales de demostración.'
        : errorMessage(caught));
      setPassword('');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="login-intro" aria-labelledby="intro-title">
        <p className="eyebrow">UN PUNTO DE PARTIDA</p>
        <h1 id="intro-title">Seguimiento escolar,<br />con un contexto claro.</h1>
        <p className="intro-copy">Accede con una cuenta de demostración para consultar el periodo y las secciones asignadas a tu perfil.</p>
        <div className="intro-note">
          <span className="note-icon" aria-hidden="true">◎</span>
          <div><strong>Demostración técnica</strong><p>El contexto y las cuentas son sintéticos. Las decisiones pedagógicas corresponden a las personas.</p></div>
        </div>
      </section>
      <section className="panel login-card" aria-labelledby="login-title">
        <div className="card-heading"><span className="small-mark" aria-hidden="true">↗</span><p className="eyebrow">ACCESO A LA DEMO</p></div>
        <h2 id="login-title">Iniciar sesión</h2>
        <p className="muted">Utiliza las credenciales preparadas para esta demostración.</p>
        {notice && <p className="notice success" role="status">{notice}</p>}
        <form onSubmit={submit} aria-busy={submitting}>
          <label htmlFor="email">Correo electrónico</label>
          <input id="email" name="email" type="email" autoComplete="username" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} disabled={submitting} placeholder="Tu correo de demostración" />
          <label htmlFor="password">Contraseña</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required maxLength={200} value={password} onChange={(event) => setPassword(event.target.value)} disabled={submitting} aria-describedby={error ? 'login-error' : undefined} />
          {error && <p id="login-error" className="notice error" role="alert">{error}</p>}
          <button className="button primary login-submit" type="submit" disabled={submitting}>{submitting ? 'Ingresando…' : 'Iniciar sesión'}<span aria-hidden="true">→</span></button>
        </form>
        <p className="login-help">Solicita las credenciales de demostración a quien prepara la demo.</p>
      </section>
    </main>
  );
}
