import { useRef, useState, type FormEvent, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, type Period, type Section, type Identity } from '../../lib/api';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui';

export function useCommand() {
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [key, setKey] = useState(() => crypto.randomUUID());
  async function run(action: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(null);
    try { await action(); }
    catch (err) { setError(err); requestAnimationFrame(() => {
      const field = err instanceof ApiError ? err.details[0]?.field?.replace(/^body\./, '') : undefined;
      const target = field ? document.getElementsByName(field)[0] : document.querySelector<HTMLElement>('.m1-errors');
      target?.focus();
    }); }
    finally { busyRef.current = false; setBusy(false); }
  }
  return { busy, error, key, run, newKey: () => setKey(crypto.randomUUID()) };
}
export function Field({ name, label, error, children }: { name: string; label: string; error?: unknown; children: ReactNode }) {
  const message = error instanceof ApiError ? error.details.find(item => item.field?.replace(/^body\./, '') === name)?.message : null;
  return <div className="m1-field"><label htmlFor={`m1-${name}`}>{label}</label>{children}{message && <p className="field-error" id={`m1-${name}-error`}>{message}</p>}</div>;
}
export function CommandErrors({ command }: { command: ReturnType<typeof useCommand> }) {
  return command.error ? <div className="m1-errors" tabIndex={-1}><ErrorState error={command.error} /><p className="muted">Tu borrador se conserva. Si hubo un problema de conexión, consulta el resultado antes de repetir. El mismo envío conserva su clave.</p>{command.error instanceof ApiError && command.error.status === 409 && <button type="button" className="button secondary" onClick={command.newKey}>Preparar nuevo envío con este borrador</button>}</div> : null;
}
export function FormButtons({ busy, cancel, label = 'Guardar', submitDisabled = false }: { busy: boolean; cancel: () => void; label?: string; submitDisabled?: boolean }) {
  return <div className="student-filter-actions"><button type="submit" className="button primary" disabled={busy || submitDisabled}>{busy ? 'Guardando…' : label}</button><button type="button" className="button secondary" disabled={busy} onClick={cancel}>Cancelar</button></div>;
}

export function PeriodForm({ initial, done, cancel }: { initial?: Period; done: (period: Period) => void; cancel: () => void }) {
  const command = useCommand();
  const [draft, setDraft] = useState({ code: initial?.code ?? '', school_year: initial?.school_year ?? 2026, start_date: initial?.start_date ?? '', end_date: initial?.end_date ?? '', data_origin: initial?.data_origin ?? 'REAL', is_locked: initial?.is_locked ?? false });
  const [expected, setExpected] = useState(initial?.version ?? 1);
  async function submit(event: FormEvent) { event.preventDefault(); await command.run(async () => {
    const { is_locked, ...fields } = draft;
    const body = { ...fields, creation_key: command.key };
    done(initial ? await api.updatePeriod(initial.id, { ...body, is_locked, expected_version: expected }) : await api.createPeriod(body));
  }); }
  return <form className="panel student-detail-panel m1-form" onSubmit={submit}><h2>{initial ? 'Editar periodo' : 'Nuevo periodo'}</h2><p className="muted">El origen se conserva en alumnos y mediciones. El registro REAL local no habilita evaluación predictiva.</p><CommandErrors command={command} />
    <div className="m1-grid"><Field name="code" label="Código del periodo" error={command.error}><input autoFocus id="m1-code" name="code" required maxLength={40} value={draft.code} onChange={e => setDraft({ ...draft, code: e.target.value })} /></Field>
      <Field name="school_year" label="Año escolar" error={command.error}><input id="m1-school_year" name="school_year" type="number" required min={2000} max={2100} value={draft.school_year} onChange={e => setDraft({ ...draft, school_year: Number(e.target.value) })} /></Field>
      <Field name="start_date" label="Fecha de inicio" error={command.error}><input id="m1-start_date" name="start_date" type="date" required value={draft.start_date} onChange={e => setDraft({ ...draft, start_date: e.target.value })} /></Field>
      <Field name="end_date" label="Fecha de fin" error={command.error}><input id="m1-end_date" name="end_date" type="date" required value={draft.end_date} onChange={e => setDraft({ ...draft, end_date: e.target.value })} /></Field>
      <Field name="data_origin" label="Origen de los datos" error={command.error}><select id="m1-data_origin" name="data_origin" value={draft.data_origin} onChange={e => setDraft({ ...draft, data_origin: e.target.value as 'REAL' | 'SYNTHETIC' })}><option value="REAL">Real · registro local</option><option value="SYNTHETIC">Sintético · prueba</option></select></Field>
    </div>{initial && <label className="m1-check"><input type="checkbox" checked={draft.is_locked} onChange={e => setDraft({ ...draft, is_locked: e.target.checked })} />Bloquear periodo: impide nuevas escrituras. Desmarcar lo reabre explícitamente.</label>}
    {command.error instanceof ApiError && command.error.status === 409 && initial && <button type="button" className="button secondary" onClick={() => void command.run(async () => { const current = (await api.periods()).find(p => p.id === initial.id); if (current) setExpected(current.version ?? 1); })}>Consultar versión actual conservando borrador</button>}
    <FormButtons busy={command.busy} cancel={cancel} label={initial ? 'Confirmar cambios del periodo' : 'Crear periodo'} /></form>;
}

export function SectionForm({ period, initial, done, cancel }: { period: Period; initial?: Section; done: (section: Section) => void; cancel: () => void }) {
  const command = useCommand();
  const tutors = useQuery({ queryKey: ['m1-tutors'], queryFn: api.tutors, retry: false });
  const [draft, setDraft] = useState({ code: initial?.code ?? '', grade: initial?.grade ?? 1, tutor_id: initial?.tutor_id ?? '' });
  const [expected, setExpected] = useState(initial?.version ?? 1);
  function submit(e: FormEvent) { e.preventDefault(); void command.run(async () => {
    const body = { ...draft, creation_key: command.key, school_year: period.school_year, data_origin: period.data_origin };
    done(initial ? await api.updateSection(initial.id, { ...body, expected_version: expected }) : await api.createSection(body));
  }); }
  return <form onSubmit={submit} className="panel student-detail-panel m1-form"><h2>{initial ? 'Editar sección' : 'Crear sección'}</h2><p className="muted">{period.school_year} · {period.data_origin === 'REAL' ? 'Origen real' : 'Origen sintético'}. Asigna un tutor existente activo.</p><CommandErrors command={command} />
    {tutors.isPending ? <LoadingState /> : tutors.isError ? <ErrorState error={tutors.error} onRetry={() => void tutors.refetch()} /> : <div className="m1-grid">
      <Field name="code" label="Código de sección" error={command.error}><input autoFocus id="m1-code" name="code" required maxLength={40} value={draft.code} onChange={e => setDraft({ ...draft, code: e.target.value })} /></Field>
      <Field name="grade" label="Grado" error={command.error}><select id="m1-grade" name="grade" value={draft.grade} onChange={e => setDraft({ ...draft, grade: Number(e.target.value) })}>{[1, 2, 3, 4, 5].map(g => <option key={g} value={g}>{g}.º</option>)}</select></Field>
      <Field name="tutor_id" label="Tutor responsable" error={command.error}><select id="m1-tutor_id" name="tutor_id" required value={draft.tutor_id} onChange={e => setDraft({ ...draft, tutor_id: e.target.value })}><option value="">Selecciona tutor</option>{tutors.data.map(t => <option key={t.id} value={t.id}>{t.display_name}</option>)}</select></Field>
    </div>}
    {command.error instanceof ApiError && command.error.status === 409 && initial && <button type="button" className="button secondary" onClick={() => void command.run(async () => { const current = (await api.sections(period.id)).find(s => s.id === initial.id); if (current) setExpected(current.version ?? 1); })}>Consultar versión actual conservando borrador</button>}
    <FormButtons busy={command.busy} submitDisabled={!tutors.data?.length} cancel={cancel} label={initial ? 'Guardar sección' : 'Guardar nueva sección'} /></form>;
}

export function NewStudent({ period, done, cancel }: { period: Period; done: (id: string) => void; cancel: () => void }) {
  const cache = useQueryClient();
  const command = useCommand();
  const sections = useQuery({ queryKey: ['m1-sections', period.id], queryFn: () => api.sections(period.id), retry: false });
  const [draft, setDraft] = useState({ anon_code: '', full_name: '', section_id: '' });
  const [creatingSection, setCreatingSection] = useState(false);
  const [existing, setExisting] = useState<Identity | null>(null);
  const [matches, setMatches] = useState<Identity[] | null>(null);
  const selectedSection = sections.data?.find(g => g.id === draft.section_id);
  async function chooseSearch() { await command.run(async () => { setMatches(await api.identities(draft.anon_code.trim())); }); }
  function submit(e: FormEvent) { e.preventDefault(); void command.run(async () => {
    if (existing) { await api.createEnrollment({ creation_key: command.key, student_id: existing.id, period_id: period.id, section_id: draft.section_id }); done(existing.id); }
    else { const result = await api.createStudent({ ...draft, creation_key: command.key, period_id: period.id }); done(result.id); }
  }); }
  if (creatingSection) return <SectionForm period={period} cancel={() => setCreatingSection(false)} done={section => { setDraft({ ...draft, section_id: section.id }); setCreatingSection(false); void cache.invalidateQueries(); }} />;
  return <form onSubmit={submit} className="panel student-detail-panel m1-form"><h2>Nuevo estudiante</h2><p className="muted">Periodo {period.code} · {period.data_origin === 'REAL' ? 'Registro real local' : 'Datos sintéticos de prueba'}. Crear alumno y primera matrícula es una sola operación.</p><CommandErrors command={command} />
    <div className="m1-grid"><Field name="anon_code" label="Código del estudiante" error={command.error}><input autoFocus id="m1-anon_code" name="anon_code" required minLength={3} maxLength={40} disabled={!!existing} value={draft.anon_code} onChange={e => setDraft({ ...draft, anon_code: e.target.value })} /></Field>
      <Field name="full_name" label="Nombre completo" error={command.error}><input id="m1-full_name" name="full_name" required={!existing} disabled={!!existing} maxLength={160} value={draft.full_name} onChange={e => setDraft({ ...draft, full_name: e.target.value })} /></Field></div>
    {!existing && <button className="button secondary" type="button" disabled={command.busy || draft.anon_code.trim().length < 2} onClick={() => void chooseSearch()}>Buscar alumno existente</button>}
    {matches && !existing && <div className="m1-choice" aria-label="Alumnos existentes">{matches.length === 0 ? <p>No se encontró un alumno con ese código o nombre.</p> : matches.map(s => <button type="button" className="button secondary" key={s.id} disabled={!s.is_active || s.data_origin !== period.data_origin} onClick={() => { setExisting(s); setDraft({ ...draft, anon_code: s.anon_code, full_name: s.full_name ?? '' }); }}>{s.anon_code} · {s.full_name ?? 'Nombre no informado'} · {s.is_active ? s.data_origin : 'Inactivo'}</button>)}</div>}
    {existing && <div className="notice">Se matriculará al alumno seleccionado sin cambiar su identidad. <button type="button" className="button secondary" onClick={() => setExisting(null)}>Usar nuevo alumno</button></div>}
    {sections.isPending ? <LoadingState /> : sections.isError ? <ErrorState error={sections.error} onRetry={() => void sections.refetch()} /> : <Field name="section_id" label="Grado / sección" error={command.error}><select id="m1-section_id" name="section_id" required value={draft.section_id} onChange={e => setDraft({ ...draft, section_id: e.target.value })}><option value="">Selecciona sección</option>{sections.data.map(g => <option key={g.id} value={g.id}>{g.grade}.º / {g.code}</option>)}</select></Field>}
    <button className="button secondary" type="button" disabled={command.busy} onClick={() => setCreatingSection(true)}>Crear sección</button>
    <p className="notice">Resumen de matrícula: {period.code} · {period.school_year} · {selectedSection ? `${selectedSection.grade}.º / ${selectedSection.code}` : 'Sección pendiente'}. Sin evaluación predictiva.</p>
    <FormButtons busy={command.busy} submitDisabled={period.is_locked} cancel={cancel} label={existing ? 'Matricular alumno seleccionado' : 'Guardar estudiante y matrícula'} /></form>;
}

export function Catalogs({ kind, period, close }: { kind: 'periods' | 'sections'; period: Period | null; close: () => void }) {
  const cache = useQueryClient();
  const periods = useQuery({ queryKey: ['m1-periods'], queryFn: () => api.periods(), retry: false });
  const sections = useQuery({ queryKey: ['m1-sections', period?.id], queryFn: () => api.sections(period!.id), enabled: !!period, retry: false });
  const [selected, setSelected] = useState<Period | Section | null>(null);
  const [editing, setEditing] = useState(false);
  const [notice, setNotice] = useState('');
  function done() { void cache.invalidateQueries(); setEditing(false); setSelected(null); setNotice('Cambios guardados en el servidor.'); }
  if (editing && kind === 'periods') return <PeriodForm initial={selected as Period | undefined ?? undefined} cancel={() => setEditing(false)} done={done} />;
  if (editing && kind === 'sections' && period) return <SectionForm period={period} initial={selected as Section | undefined ?? undefined} cancel={() => setEditing(false)} done={done} />;
  const query = kind === 'periods' ? periods : sections;
  return <section className="panel student-detail-panel"><h2>{kind === 'periods' ? 'Periodos' : 'Secciones'}</h2>{notice && <p role="status" className="notice">{notice}</p>}<div className="student-filter-actions"><button type="button" className="button primary" disabled={kind === 'sections' && !period} onClick={() => { setSelected(null); setEditing(true); }}>{kind === 'periods' ? 'Nuevo periodo' : 'Nueva sección'}</button><button type="button" className="button secondary" onClick={close}>Volver al listado</button></div>
    {kind === 'sections' && !period ? <EmptyState title="Crea o selecciona un periodo primero" /> : query.isPending ? <LoadingState /> : query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : query.data?.length === 0 ? <EmptyState title="Todavía no hay registros" /> : <ul className="m1-catalog-list">{query.data?.map(item => <li key={item.id}><span>{'grade' in item ? `${item.grade}.º / ${item.code}` : `${item.code} · ${item.school_year} · ${item.is_locked ? 'Bloqueado' : 'Abierto'}`}</span><button type="button" className="button secondary" onClick={() => { setSelected(item); setEditing(true); }}>Editar {item.code}</button></li>)}</ul>}
  </section>;
}
