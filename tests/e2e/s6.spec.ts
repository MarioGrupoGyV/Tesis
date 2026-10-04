import { expect, test, type APIResponse, type Page, type Response } from '@playwright/test';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import type { components } from '../../frontend/src/lib/api.generated';

type Role = 'ADMIN' | 'TUTOR' | 'DIRECTOR' | 'RESEARCHER';
type Case = components['schemas']['AlertCase'];
type Detail = components['schemas']['AlertDetail'];
type Target = { kind: 'INSTALL' | 'RESTORE' | 'ACTIVE'; project: string; database: string; web_url: string; api_url: string };
type Study = { study_id: string; period_id: string; csv_file?: string; csv_sha256?: string; import_id?: string;
  student_count: number; real_period_id?: string; own_section: { id: string }; foreign_section: { id: string };
  own_student: { id: string; anon_code: string }; foreign_student: { id: string; anon_code: string };
  insufficient_student: { id: string; anon_code: string }; model: { id: string; name: string } };
const roles: Role[] = ['ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER'];
const accounts = JSON.parse(process.env.E2E_ACCOUNTS ?? '{}') as Record<Role, { email: string; password: string }>;
const study = JSON.parse(process.env.E2E_STUDY ?? '{}') as Study;
const target = JSON.parse(process.env.E2E_TARGET ?? '{}') as Target;
const prefix = process.env.E2E_EVIDENCE_PREFIX ?? '';
const phase = process.env.E2E_PHASE;
const base = process.env.E2E_BASE_URL;
const kinds = ['INSTALL', 'RESTORE', 'ACTIVE'];
const phases = ['s6-import', 's6-integrated', 's6-review', 's6-outage', 's6-period-lock'];
if (!/^s6[a-z0-9-]+$/.test(prefix) || !phases.includes(phase ?? '') || !kinds.includes(target.kind) ||
    !target.project || !target.database || base !== target.web_url || !study.period_id ||
    !roles.every(role => accounts[role]?.email && accounts[role]?.password)) throw new Error('Destino S6 explícito y contexto privado requeridos.');
const address = new URL(base!);
if (!['127.0.0.1', 'localhost'].includes(address.hostname) || address.protocol !== 'http:' || !address.port ||
    target.kind !== 'ACTIVE' && address.port === '15173' ||
    ['s6-import', 's6-integrated', 's6-period-lock'].includes(phase!) && target.kind !== 'INSTALL' ||
    phase === 's6-outage' && target.kind === 'ACTIVE') throw new Error('Destino S6 incompatible con la operación.');
if (phase === 's6-import' && (!study.csv_file || !study.csv_sha256)) throw new Error('CSV privado registrado requerido.');
const missing = '00000000-0000-4000-8000-000000000666';
const sizes = [[1440, 900], [768, 1024], [390, 844]];
const labels: Record<Role, string> = { ADMIN: 'Administrador', TUTOR: 'Tutor', DIRECTOR: 'Directivo', RESEARCHER: 'Investigador' };
const path = (route: string) => `${route}?period_id=${encodeURIComponent(study.period_id)}`;
const samples: { schema: string; body: unknown }[] = [];
const simulations: { case: string; scope: string; result: string }[] = [];
const logins: { role: Role; status: number; code: string | null }[] = [];
let foreignCase: Case | undefined;
let closedCase: Detail | undefined;
const doneObjective = 'S6 instalación: actividad exclusivamente simulada realizada';
const cancelledObjective = 'S6 instalación: actividad exclusivamente simulada cancelada';

test.afterAll(() => {
  if (logins.length) writeFileSync(`tests/evidence/${prefix}-login-statuses.json`, JSON.stringify({ target, attempts: logins }, null, 2) + '\n');
  if (samples.length) writeFileSync(`tests/evidence/${prefix}-response-samples.json`, JSON.stringify(samples, null, 2) + '\n');
  if (simulations.length) writeFileSync(`tests/evidence/${prefix}-ui-simulations.json`, JSON.stringify({ target, cases: simulations, proves_database_outage: false }, null, 2) + '\n');
});
async function record(schema: string, response: APIResponse | Response, status = 200) {
  expect(response.status()).toBe(status); const body = await response.json(); samples.push({ schema, body }); return body;
}
async function login(page: Page, role: Role) {
  await page.goto(path('/')); await expect(page.getByRole('heading', { name: 'Iniciar sesión', exact: true })).toBeVisible();
  await page.getByLabel('Correo electrónico').fill(accounts[role].email);
  await page.getByLabel('Contraseña', { exact: true }).fill(accounts[role].password);
  const submitted = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).focus(); await page.keyboard.press('Enter');
  const response = await submitted; let code: string | null = null;
  if (response.status() !== 200) {
    const body = await response.json(); if (typeof body.code === 'string' && /^[A-Z0-9_]{1,80}$/.test(body.code)) code = body.code;
  }
  logins.push({ role, status: response.status(), code }); expect(response.status()).toBe(200);
  await expect(page.locator('.user-summary').getByText(labels[role], { exact: true })).toBeVisible();
  expect((await (await page.request.get('/api/v1/auth/me')).json()).role).toBe(role);
}
async function token(page: Page) { return (await (await page.request.get('/api/v1/auth/csrf')).json()).csrf_token as string; }
async function navigate(page: Page, name: string) {
  if (await page.getByRole('button', { name: 'Abrir menú', exact: true }).isVisible()) {
    await page.getByRole('button', { name: 'Abrir menú', exact: true }).click();
    await page.getByRole('dialog').getByRole('link', { name, exact: true }).click();
  } else await page.locator('.desktop-sidebar').getByRole('link', { name, exact: true }).click();
}
async function capture(page: Page, name: string) {
  await page.waitForLoadState('networkidle');
  for (const [width, height] of sizes) {
    await page.setViewportSize({ width, height }); await page.locator('#main-content h1').first().focus();
    await page.evaluate(() => window.scrollTo(0, 0));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `tests/evidence/${prefix}-${name}-${width}x${height}.png`, fullPage: true });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}
async function cases(page: Page): Promise<Case[]> {
  return (await record('AlertPage', await page.request.get(`/api/v1/alerts?period_id=${study.period_id}&page_size=100`))).items;
}
async function detail(page: Page, id: string): Promise<Detail> { return record('AlertDetail', await page.request.get(`/api/v1/alerts/${id}`)); }
function parseCsv(csv: string) {
  const rows: string[][] = []; let row: string[] = []; let cell = ''; let quoted = false;
  for (let i = 0; i < csv.length; i++) {
    const character = csv[i];
    if (character === '"') { if (quoted && csv[i + 1] === '"') { cell += '"'; i++; } else quoted = !quoted; }
    else if (character === ',' && !quoted) { row.push(cell); cell = ''; }
    else if (character === '\n' && !quoted) { row.push(cell.replace(/\r$/, '')); rows.push(row); row = []; cell = ''; }
    else cell += character;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); } return rows;
}
async function csv(page: Page, total: number, role: Role) {
  const response = page.waitForResponse(r => r.url().includes('/api/v1/reports/export.csv'));
  const downloaded = page.waitForEvent('download'); await page.getByRole('button', { name: 'Descargar CSV', exact: true }).click();
  const actual = await response; expect(actual.status()).toBe(200);
  expect(actual.headers()['content-type']).toContain('text/csv'); expect(actual.headers()['cache-control']).toBe('no-store');
  const file = await downloaded; expect(file.suggestedFilename()).toBe('seguimiento-escolar-reporte.csv');
  const stream = await file.createReadStream(); expect(stream).not.toBeNull(); const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk)); const bytes = Buffer.concat(chunks);
  expect([...bytes.subarray(0, 3)]).toEqual([239, 187, 191]); const rows = parseCsv(bytes.toString('utf8').replace(/^\uFEFF/, ''));
  expect(rows).toHaveLength(total + 1); expect(rows[0]).toHaveLength(19);
  const index = rows[0].indexOf('codigo_sintetico'); expect(index).toBeGreaterThanOrEqual(0);
  expect(new Set(rows.slice(1).map(row => row[index])).size).toBe(total);
  expect(bytes.toString('utf8')).not.toContain('password_hash'); expect(bytes.toString('utf8')).not.toContain('Actividad de simulación;');
  if (role === 'TUTOR') expect(bytes.toString('utf8')).not.toContain(study.foreign_student.anon_code);
  writeFileSync(`tests/evidence/${prefix}-${role.toLowerCase()}-csv.json`, JSON.stringify({ status: 'COMPROBADO', role,
    rows: total, headers: rows[0], sha256: createHash('sha256').update(bytes).digest('hex'), utf8_bom: true,
    complete_filtered_scope: true, no_free_notes: true, actual_browser_download_response: true, target }, null, 2) + '\n');
}
async function evaluate(page: Page, first: boolean) {
  await navigate(page, 'Modelos'); await page.getByRole('link', { name: study.model.name, exact: true }).click();
  await page.getByRole('radio', { name: 'Instante actual', exact: true }).check();
  const button = page.getByRole('button', { name: 'Evaluar ahora', exact: true }); await expect(button).toBeEnabled();
  const response = page.waitForResponse(r => r.url().endsWith('/api/v1/predictions/run'));
  await button.focus(); await page.keyboard.press('Enter'); const actual = await response;
  const result = await record('PredictionRunResult', actual); expect(result.selected).toBe(60);
  expect(result.created).toBe(first ? 55 : 0); expect(result.reused).toBe(first ? 0 : 55); expect(result.abstentions).toHaveLength(5);
  expect(result.followup.created).toBe(first ? 51 : 0); expect(result.followup.reused).toBe(first ? 0 : 55);
  expect(actual.request().headers()['x-csrf-token']).toBeTruthy();
  expect(Date.parse(actual.request().postDataJSON().as_of)).toBeLessThanOrEqual(Date.parse(actual.headers()['date']) + 1000);
  await expect(page.getByRole('heading', { name: 'Evaluación completada', exact: true })).toBeVisible(); return result;
}

if (phase === 's6-import') test('S6 instalación: primera importación por interfaz sin preparación académica', async ({ page }) => {
  test.setTimeout(120000); await login(page, 'ADMIN');
  const students = async () => record('StudentPage', await page.request.get(`/api/v1/students?period_id=${study.period_id}`));
  expect((await students()).total).toBe(0);
  expect((await record('ModelPage', await page.request.get('/api/v1/models'))).items).toEqual([]);
  await navigate(page, 'Modelos'); await expect(page.getByRole('heading', { name: 'Modelo no disponible', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Evaluar ahora', exact: true })).toBeDisabled(); await capture(page, 'first-models-empty');
  await navigate(page, 'Datos'); await expect(page.getByRole('heading', { name: 'Importar información', exact: true })).toBeVisible();
  const headerDownload = page.waitForEvent('download'); await page.getByRole('button', { name: 'Descargar cabeceras CSV', exact: true }).click();
  const headerStream = await (await headerDownload).createReadStream(); const headerChunks: Buffer[] = [];
  expect(headerStream).not.toBeNull(); for await (const chunk of headerStream!) headerChunks.push(Buffer.from(chunk));
  expect(Buffer.concat(headerChunks).toString('utf8').replace(/\r?\n$/, '')).toBe('student_code,grade,section,cutoff_at,target_date,available_at,window_start,average_grade,attendance_pct,activities_pct,participation_level,behavior_incidents,age_years');
  const chooser = page.waitForEvent('filechooser'); await page.getByRole('button', { name: 'Seleccionar CSV', exact: true }).click();
  await (await chooser).setFiles(study.csv_file!);
  const preview = page.waitForResponse(r => r.url().endsWith('/api/v1/imports/preview'));
  await page.getByRole('button', { name: 'Revisar archivo', exact: true }).click();
  const batch = await record('ImportBatch', await preview, 201); expect(batch.status).toBe('READY'); expect(batch.file_sha256).toBe(study.csv_sha256);
  expect(batch.invalid_rows).toBe(0); expect(batch.planned_students).toBe(60); expect(batch.planned_snapshots).toBe(360);
  expect((await students()).total).toBe(0);
  const batchDetail = await record('ImportBatch', await page.request.get(`/api/v1/imports/${batch.id}`)); expect(batchDetail.status).toBe('READY');
  await expect(page.getByRole('button', { name: 'Confirmar importación', exact: true })).toBeDisabled(); await capture(page, 'first-import-review');
  await page.getByRole('checkbox', { name: 'Revisé las validaciones y confirmo importar este archivo sintético en el periodo seleccionado.' }).check();
  const commit = page.waitForResponse(r => r.url().endsWith(`/imports/${batch.id}/commit`));
  await page.getByRole('button', { name: 'Confirmar importación', exact: true }).click(); const response = await commit;
  const result = await record('ImportCommit', response); expect(result.reused_result).toBe(false); expect(result.created_snapshots).toBe(360);
  expect(response.request().postDataJSON().expected_preview_version).toBe(batch.preview_version);
  expect(response.request().headers()['x-csrf-token']).toBeTruthy(); expect((await students()).total).toBe(60);
  await expect(page.getByRole('heading', { name: 'Estudiantes', exact: true })).toBeVisible(); await capture(page, 'first-import-committed');
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
  await expect(page.getByText('Sesión cerrada correctamente.', { exact: true })).toBeVisible();
});

async function humanWorkflow(page: Page, records: Case[]) {
  const chosen = records.find(item => item.status === 'OPEN')!; expect(chosen).toBeDefined();
  await page.goto(path(`/alertas/${chosen.id}`)); await expect(page.getByRole('heading', { name: `Caso de ${chosen.anon_code}`, exact: true })).toBeVisible();
  for (const [objective, status] of [[doneObjective, 'DONE'], [cancelledObjective, 'CANCELLED']] as const) {
    await page.getByLabel('Objetivo', { exact: true }).fill(objective);
    await page.getByLabel('Fecha y hora programadas (Lima)', { exact: true }).fill('2027-01-05T14:00');
    await page.getByLabel('Notas opcionales', { exact: true }).fill('Actividad de simulación; no se contactó a personas.');
    if (status === 'DONE') await capture(page, 'plan-form');
    const created = page.waitForResponse(r => r.url().endsWith('/api/v1/interventions') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Planificar actividad', exact: true }).click();
    const activity = (await record('InterventionCreateResult', await created, 201)).intervention;
    const item = page.locator('.followup-interventions > li').filter({ has: page.getByText(objective, { exact: true }) });
    await expect(item).toBeVisible(); await item.getByRole('button', { name: 'Registrar actividad', exact: true }).click();
    await item.getByLabel('Estado de actividad', { exact: true }).selectOption(status);
    if (status === 'DONE') {
      const clock = await page.request.get('/api/v1/auth/csrf'); const now = Date.parse(clock.headers()['date']); expect(Number.isFinite(now)).toBe(true);
      await item.getByLabel('Fecha y hora efectiva (Lima)', { exact: true }).fill(new Date(now - 5 * 3600000 - 60000).toISOString().slice(0, 16));
      await capture(page, 'done-form');
    }
    const updated = page.waitForResponse(r => r.url().endsWith(`/api/v1/interventions/${activity.id}`) && r.request().method() === 'PATCH');
    await item.getByRole('button', { name: 'Guardar actividad', exact: true }).click();
    const result = await record('InterventionView', await updated); expect(result.status).toBe(status); expect(result.performed_at === null).toBe(status === 'CANCELLED');
    await item.getByRole('button', { name: 'Cerrar formulario', exact: true }).click();
  }
  const latest = await detail(page, chosen.id); const reason = 'Seguimiento concluido exclusivamente en simulación S6; no implica mejoría académica.';
  await page.getByLabel('Estado del caso', { exact: true }).selectOption('RESOLVED'); await page.getByLabel('Motivo de cierre', { exact: true }).fill(reason);
  // Cambio real concurrente: se conserva el motivo y se exige revisión explícita.
  const changed = await page.request.patch(`/api/v1/alerts/${chosen.id}`, { data: { expected_version: latest.alert.version, status: 'IN_REVIEW' }, headers: { 'X-CSRF-Token': await token(page) } }); expect(changed.status()).toBe(200);
  const stale = page.waitForResponse(r => r.url().endsWith(`/api/v1/alerts/${chosen.id}`) && r.request().method() === 'PATCH');
  await page.getByRole('button', { name: 'Guardar estado', exact: true }).click(); await record('Error', await stale, 409);
  await expect(page.getByLabel('Motivo de cierre', { exact: true })).toHaveValue(reason);
  await expect(page.getByRole('button', { name: 'Guardar estado', exact: true })).toBeDisabled(); await capture(page, 'real-version-conflict');
  await page.getByRole('button', { name: 'Revisar cambios del caso', exact: true }).click();
  await page.getByLabel('He revisado el recurso actualizado', { exact: true }).check();
  const closed = page.waitForResponse(r => r.url().endsWith(`/api/v1/alerts/${chosen.id}`) && r.request().method() === 'PATCH');
  await page.getByRole('button', { name: 'Guardar estado', exact: true }).click(); closedCase = await record('AlertDetail', await closed);
  expect(closedCase!.alert.status).toBe('RESOLVED'); expect(closedCase!.interventions).toHaveLength(2);
  // Limpio/terminal pasa a lectura; no oculta borradores durante el conflicto.
  await page.reload(); await expect(page.getByRole('heading', { name: 'Motivo y fuente del caso', exact: true })).toBeVisible();
  await expect(page.getByLabel('Motivo de cierre', { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Objetivo', { exact: true })).toHaveCount(0); await capture(page, 'case-completed');
}

if (['s6-integrated', 's6-review'].includes(phase!)) for (const role of roles) test(`S6 ${target.kind} ${role}: contexto, historial, permisos y CSV efectivos`, async ({ page, context }) => {
  test.setTimeout(180000); await login(page, role);
  const processing = await record('ProcessingStatus', await page.request.get('/api/v1/processing/status'));
  expect(processing.institutional_ready).toBe(false);
  if (role === 'RESEARCHER') {
    const requests: string[] = []; page.on('request', request => { if (/\/api\/v1\/(alerts|reports|students|models)(?:[/?]|$)/.test(request.url())) requests.push(request.url()); });
    for (const route of ['/alertas', '/reportes', '/estudiantes', `/alertas/${missing}`]) {
      await page.goto(path(route)); await expect(page.getByRole('heading', { name: 'Acceso no disponible', exact: true })).toBeVisible();
    }
    expect(requests).toEqual([]);
    for (const route of ['/alerts', '/reports/summary', '/reports/export.csv', '/students', '/models']) await record('Error', await page.request.get(`/api/v1${route}?period_id=${study.period_id}`), 403);
    await capture(page, 'researcher-restricted');
  } else {
    await expect(page.getByLabel('Periodo de consulta')).toHaveValue(study.period_id);
    await expect(page.locator('#main-content').getByText('Estudio con datos sintéticos. No corresponde a estudiantes reales.', { exact: true })).toBeVisible();
    if (role === 'ADMIN') {
      if (phase === 's6-integrated') { await evaluate(page, true); await capture(page, 'first-ui-inference'); }
      expect((await page.request.post('/api/v1/predictions/run', { data: { period_id: study.period_id, as_of: new Date().toISOString() } })).status()).toBe(403);
      await navigate(page, 'Alertas'); const synchronization = page.waitForResponse(r => r.url().endsWith('/api/v1/alerts/sync'));
      const button = page.getByRole('button', { name: 'Actualizar alertas', exact: true }); await expect(button).toBeEnabled(); await button.focus(); await page.keyboard.press('Enter');
      const sync = await record('FollowupResult', await synchronization); expect(sync.created).toBe(0); expect(sync.reused).toBe(55);
      await evaluate(page, false); await navigate(page, 'Alertas');
      if (phase === 's6-integrated') {
        await navigate(page, 'Modelos'); await page.getByRole('link', { name: study.model.name, exact: true }).click();
        let uncertainCalls = 0;
        test.info().annotations.push({ type: 'response-body-loss-simulation', description: 'Inferencia real reutilizada 200; solo se trunca la respuesta UI. No se simula PostgreSQL ni se reintenta automáticamente.' });
        await page.route('**/api/v1/predictions/run', async route => {
          uncertainCalls++; const actual = await route.fetch(); expect(actual.status()).toBe(200);
          const body = await actual.json(); expect(body.created).toBe(0); expect(body.reused).toBe(55);
          await route.fulfill({ status: 200, contentType: 'application/json', body: '{"period_id":' });
        });
        await page.getByRole('button', { name: 'Evaluar ahora', exact: true }).click();
        await expect(page.getByRole('alert')).toContainText('No pudimos leer la respuesta del sistema.');
        await expect(page.getByRole('heading', { name: 'Evaluación completada', exact: true })).toHaveCount(0);
        await page.waitForLoadState('networkidle'); expect(uncertainCalls).toBe(1); await capture(page, 'http-simulated-uncertain-no-retry');
        simulations.push({ case: 'response_body_loss', scope: 'POST real 200 reutilizado; únicamente cuerpo truncado', result: 'Sin éxito aparente ni reintento automático' });
        await page.unroute('**/api/v1/predictions/run'); await navigate(page, 'Alertas');
      }
      if (study.import_id) expect((await record('ImportBatch', await page.request.get(`/api/v1/imports/${study.import_id}`))).status).toBe('COMMITTED');
    } else { await navigate(page, 'Alertas'); await expect(page.getByRole('button', { name: 'Actualizar alertas', exact: true })).toHaveCount(0); }
    let records = await cases(page); expect(records.length).toBeGreaterThan(0); if (role === 'ADMIN') foreignCase = records.find(item => item.section_id === study.foreign_section.id);
    if (role === 'TUTOR') expect(records.every(item => item.section_id === study.own_section.id)).toBe(true);
    const filtered = page.waitForResponse(r => r.url().includes('/api/v1/alerts?') && new URL(r.url()).searchParams.get('search') === records[0].anon_code);
    await page.getByLabel('Buscar código', { exact: true }).fill(records[0].anon_code); await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click(); expect((await filtered).status()).toBe(200);
    await expect(page.locator('.followup-table tbody tr')).toHaveCount(1); await page.getByRole('button', { name: 'Limpiar filtros', exact: true }).click(); await capture(page, `${role.toLowerCase()}-alerts`);
    if (phase === 's6-integrated' && role === 'TUTOR') { await humanWorkflow(page, records); records = await cases(page); }
    if (phase === 's6-integrated' && role === 'TUTOR') {
      // Rama de UI negativa, separada del conflicto real y sin cerrar otro caso.
      const draftCase = records.find(item => item.status === 'OPEN')!;
      await page.goto(path(`/alertas/${draftCase.id}`)); await expect(page.getByLabel('Objetivo', { exact: true })).toBeVisible();
      const caseDraft = 'Borrador conservado al observar cierre concurrente simulado';
      const activityDraft = 'Actividad no enviada; borrador conservado ante cierre simulado';
      await page.getByLabel('Estado del caso', { exact: true }).selectOption('RESOLVED');
      await page.getByLabel('Motivo de cierre', { exact: true }).fill(caseDraft); await page.getByLabel('Objetivo', { exact: true }).fill(activityDraft);
      test.info().annotations.push({ type: 'terminal-conflict-simulation', description: 'Solo PATCH409 y cierre de GET simulados desde recurso real; prueba borradores UI, no concurrencia PostgreSQL.' });
      await page.route(`**/api/v1/alerts/${draftCase.id}`, async route => {
        if (route.request().method() === 'PATCH') { await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ code: 'ALERT_VERSION_CONFLICT', message: 'El caso cambió.', details: [], request_id: missing }) }); return; }
        const actual = await route.fetch(); const body = await actual.json(); body.alert.status = 'RESOLVED';
        body.alert.closed_at = new Date().toISOString(); body.alert.resolution_reason = 'Cierre exclusivamente simulado en la respuesta UI';
        body.alert.capabilities = { can_edit: false, can_plan: false, reason: 'ALERT_CLOSED' };
        await route.fulfill({ response: actual, json: body });
      });
      await page.getByRole('button', { name: 'Guardar estado', exact: true }).click();
      await expect(page.getByRole('button', { name: 'Revisar cambios del caso', exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Revisar cambios del caso', exact: true }).click();
      await expect(page.getByLabel('Motivo de cierre', { exact: true })).toHaveValue(caseDraft);
      await expect(page.getByLabel('Objetivo', { exact: true })).toHaveValue(activityDraft);
      await expect(page.getByRole('button', { name: 'Guardar estado', exact: true })).toBeDisabled();
      await expect(page.getByRole('button', { name: 'Planificar actividad', exact: true })).toBeDisabled();
      await expect(page.getByText('Este caso no registra actividades. Sus decisiones e historial se conservan para consulta.', { exact: true })).toBeVisible();
      await capture(page, 'http-simulated-terminal-conflict-drafts'); await page.unroute(`**/api/v1/alerts/${draftCase.id}`);
      expect((await detail(page, draftCase.id)).alert.status).toBe('OPEN');
      simulations.push({ case: 'terminal_conflict', scope: 'PATCH409 y cierre del GET simulados; sin cambios DB', result: 'Ambos borradores conservados y escrituras deshabilitadas' });
    }
    const selected = records.find(item => item.status === 'RESOLVED') ?? records[0];
    const actual = await detail(page, selected.id); if (actual.alert.status === 'RESOLVED') {
      expect(actual.interventions).toHaveLength(2); expect(actual.interventions.filter(item => item.status === 'DONE')).toHaveLength(1);
      expect(actual.interventions.filter(item => item.status === 'CANCELLED')).toHaveLength(1); closedCase = actual;
    }
    await page.goto(path(`/alertas/${selected.id}`)); await expect(page.getByRole('heading', { name: `Caso de ${selected.anon_code}`, exact: true })).toBeVisible();
    if (selected.status === 'RESOLVED' || role === 'DIRECTOR') { await expect(page.getByRole('button', { name: 'Guardar estado', exact: true })).toHaveCount(0); await expect(page.getByLabel('Objetivo', { exact: true })).toHaveCount(0); }
    await capture(page, `${role.toLowerCase()}-case`);
    if (role === 'DIRECTOR') await record('Error', await page.request.patch(`/api/v1/alerts/${selected.id}`, { data: { expected_version: selected.version, status: 'IN_REVIEW' }, headers: { 'X-CSRF-Token': await token(page) } }), 403);
    if (role === 'TUTOR') {
      expect(foreignCase).toBeDefined(); const inaccessible = await record('Error', await page.request.get(`/api/v1/alerts/${foreignCase!.id}`), 404);
      const nonexistent = await record('Error', await page.request.get(`/api/v1/alerts/${missing}`), 404);
      const { request_id: _a, ...foreign } = inaccessible; const { request_id: _b, ...empty } = nonexistent; expect(foreign).toEqual(empty);
      const response = page.waitForResponse(r => r.url().endsWith(`/api/v1/alerts/${foreignCase!.id}`)); await page.goto(path(`/alertas/${foreignCase!.id}`)); expect((await response).status()).toBe(404);
      await expect(page.getByRole('heading', { name: 'Este caso no está disponible', exact: true })).toBeVisible(); await expect(page.getByText(foreignCase!.anon_code, { exact: true })).toHaveCount(0);
      await capture(page, 'tutor-foreign-safe404');
      const foreignStudent = await record('Error', await page.request.get(`/api/v1/students/${study.foreign_student.id}?period_id=${study.period_id}`), 404);
      const missingStudent = await record('Error', await page.request.get(`/api/v1/students/${missing}?period_id=${study.period_id}`), 404);
      const { request_id: _c, ...foreignStudentError } = foreignStudent; const { request_id: _d, ...missingStudentError } = missingStudent;
      expect(foreignStudentError).toEqual(missingStudentError);
      await record('Error', await page.request.get(`/api/v1/students/${study.foreign_student.id}/timeline?period_id=${study.period_id}`), 404);
    }
    const studentId = closedCase && (role !== 'TUTOR' || closedCase.alert.section_id === study.own_section.id) ? closedCase.alert.student_id : study.own_student.id;
    await page.goto(path(`/estudiantes/${studentId}`)); const history = page.getByRole('heading', { name: 'Historial', exact: true }); await expect(history).toBeVisible();
    const student = await record('StudentDetail', await page.request.get(`/api/v1/students/${studentId}?period_id=${study.period_id}`)); expect(student.student.data_origin).toBe('SYNTHETIC');
    await page.getByRole('button', { name: 'Ir al historial ↓', exact: true }).focus(); await page.keyboard.press('Enter'); await expect(history).toBeFocused();
    const paged = page.waitForResponse(r => r.url().includes(`/students/${studentId}/timeline?`) && new URL(r.url()).searchParams.get('page') === '2');
    await page.getByRole('button', { name: 'Siguiente →', exact: true }).click(); const second = await record('TimelineEventPage', await paged); expect(second.page).toBe(2); await expect(history).toBeFocused();
    await page.getByLabel('Eventos por página', { exact: true }).selectOption('20');
    const timeline = await record('TimelineEventPage', await page.request.get(`/api/v1/students/${studentId}/timeline?period_id=${study.period_id}&page_size=100`));
    if (closedCase?.alert.student_id === studentId) { expect(timeline.items.some((event: { summary: string }) => event.summary.includes('realizada'))).toBe(true); expect(timeline.items.some((event: { summary: string }) => event.summary.includes('cancelada'))).toBe(true); }
    await capture(page, `${role.toLowerCase()}-student-history-long`);
    await page.goto(path(`/estudiantes/${study.insufficient_student.id}`));
    if (role !== 'TUTOR' || (await page.request.get(`/api/v1/students/${study.insufficient_student.id}?period_id=${study.period_id}`)).status() === 200) {
      const insufficient = await page.request.get(`/api/v1/students/${study.insufficient_student.id}?period_id=${study.period_id}`);
      if (insufficient.status() === 200) { const data = await record('StudentDetail', insufficient); expect(data.latest_prediction).toBeNull(); expect(data.student.risk_level).toBeNull(); await expect(page.getByText('Datos insuficientes', { exact: false }).first()).toBeVisible(); }
    }
    await navigate(page, 'Reportes'); await expect(page.getByRole('button', { name: 'Descargar CSV', exact: true })).toBeEnabled();
    const report = await record('ReportSummary', await page.request.get(`/api/v1/reports/summary?period_id=${study.period_id}&page_size=5`));
    const total = role === 'TUTOR' ? 30 : 60; expect(report.total).toBe(total); expect(report.items).toHaveLength(5);
    expect(report.evaluations.evaluated + report.evaluations.insufficient_data + report.evaluations.not_evaluated).toBe(total);
    expect(report.risks.low.count + report.risks.medium.count + report.risks.high.count).toBe(report.evaluations.evaluated);
    if (role === 'TUTOR' || phase === 's6-review') { expect(report.interventions.done).toBe(1); expect(report.interventions.cancelled).toBe(1); }
    await csv(page, total, role); await capture(page, `${role.toLowerCase()}-reports`);
    await page.getByLabel('Buscar código', { exact: true }).fill('NO-RESULT-S6'); await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'No hay matrículas con estos filtros', exact: true })).toBeVisible(); await capture(page, `${role.toLowerCase()}-reports-empty`);
    await page.getByRole('button', { name: 'Limpiar filtros', exact: true }).first().click(); await expect(page.locator('.report-rows-table tbody tr')).toHaveCount(20);
    await page.reload(); await expect(page.getByRole('heading', { name: 'Reportes', exact: true })).toBeVisible(); await navigate(page, 'Inicio'); await capture(page, `${role.toLowerCase()}-home`);
  }
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  const cookie = (await context.cookies()).find(item => item.name === 'session')!; expect(cookie.httpOnly).toBe(true); expect(cookie.sameSite).toBe('Lax');
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).focus(); await page.keyboard.press('Enter');
  await expect(page.getByText('Sesión cerrada correctamente.', { exact: true })).toBeVisible();
  await context.addCookies([cookie]); expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);
  expect((await page.request.get(`/api/v1/reports/export.csv?period_id=${study.period_id}`)).status()).toBe(401);
});

if (phase === 's6-period-lock') test('S6 instalación: periodo bloqueado real conserva lectura y rechaza escrituras', async ({ page }) => {
  test.setTimeout(150000); await login(page, 'ADMIN');
  const descriptor = process.env.E2E_TARGET_FILE; if (!descriptor) throw new Error('Descriptor de instalación requerido.');
  const control = (action: 'lock' | 'unlock') => execFileSync('py', ['-3.12', 'infra/review_s6.py', '--target', descriptor, '--period-id', study.period_id, '--control-period', action], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  try {
    control('lock'); await page.reload(); await navigate(page, 'Alertas');
    await expect(page.getByRole('button', { name: 'Actualizar alertas', exact: true })).toBeDisabled(); await capture(page, 'real-period-locked');
    const csrf = await token(page); const clock = await page.request.get('/api/v1/auth/csrf');
    const actual = new Date(Date.parse(clock.headers()['date'])).toISOString();
    for (const [route, data] of [['/alerts/sync', { period_id: study.period_id }], ['/predictions/run', { period_id: study.period_id, as_of: actual }]] as const) {
      const output = await record('Error', await page.request.post(`/api/v1${route}`, { data, headers: { 'X-CSRF-Token': csrf } }), 409); expect(output.code).toBe('PERIOD_LOCKED');
    }
    expect((await record('StudentPage', await page.request.get(`/api/v1/students?period_id=${study.period_id}`))).total).toBe(60);
    await navigate(page, 'Modelos'); await page.getByRole('link', { name: study.model.name, exact: true }).click();
    await expect(page.getByRole('button', { name: 'Evaluar ahora', exact: true })).toBeDisabled();
  } finally { control('unlock'); }
  await page.reload(); await navigate(page, 'Alertas'); await expect(page.getByRole('button', { name: 'Actualizar alertas', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click(); await expect(page.getByText('Sesión cerrada correctamente.', { exact: true })).toBeVisible();
});

if (phase === 's6-outage') test('S6 aislado: PostgreSQL realmente detenido, 503 sanitizado y recuperación', async ({ page }) => {
  test.setTimeout(150000); await login(page, 'ADMIN'); await navigate(page, 'Estudiantes');
  await expect(page.locator('.student-table tbody tr')).toHaveCount(20);
  const descriptor = process.env.E2E_TARGET_FILE; if (!descriptor) throw new Error('Descriptor explícito requerido para fallo aislado.');
  const control = (action: 'stop' | 'start') => execFileSync('py', ['-3.12', 'infra/review_s6.py', '--target', descriptor, '--control-db', action], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  try {
    control('stop');
    const health = await page.request.get('/api/v1/health/ready'); const body = await record('Health', health, 503); expect(body.status).toBe('unavailable');
    expect((await page.request.get('/api/v1/health/live')).status()).toBe(200);
    const failure = await record('Error', await page.request.get(`/api/v1/students?period_id=${study.period_id}`), 503);
    expect(failure.code).toBe('SERVICE_UNAVAILABLE'); expect(JSON.stringify(failure)).not.toMatch(/psycopg|SELECT |password|postgresql|Traceback/i);
    const query = page.waitForResponse(r => r.url().includes('/api/v1/students?')); await page.getByLabel('Buscar código', { exact: true }).fill('S6-OUTAGE');
    await page.getByRole('button', { name: 'Aplicar filtros', exact: true }).click(); expect((await query).status()).toBe(503);
    await expect(page.getByRole('alert')).toContainText('El servicio no está disponible temporalmente.');
    await expect(page.locator('.student-table tbody tr')).toHaveCount(0);
    await capture(page, 'real-postgresql-outage');
  } finally { control('start'); }
  await expect.poll(async () => (await page.request.get('/api/v1/health/ready')).status(), { timeout: 30000 }).toBe(200);
  expect((await record('StudentPage', await page.request.get(`/api/v1/students?period_id=${study.period_id}`))).total).toBe(60);
  await page.getByRole('button', { name: 'Limpiar filtros', exact: true }).click(); await expect(page.locator('.student-table tbody tr')).toHaveCount(20);
  await capture(page, 'real-postgresql-recovered'); await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
  await expect(page.getByText('Sesión cerrada correctamente.', { exact: true })).toBeVisible();
  writeFileSync(`tests/evidence/${prefix}-infrastructure-failure.json`, JSON.stringify({ status: 'COMPROBADO', target,
    real_postgresql_stop: true, web_and_api_kept_running: true, health_503_schema: 'Health', database_operation_503_schema: 'Error',
    sanitized_error: true, ui_no_false_success: true, real_database_recovery: true, http_mock: false }, null, 2) + '\n');
});
