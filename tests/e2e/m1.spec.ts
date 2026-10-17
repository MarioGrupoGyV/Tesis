import { test, expect, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
const accounts = JSON.parse(process.env.M1_ACCOUNTS ?? '{}') as Record<string, { email: string; password: string }>;
const prefix = process.env.M1_PREFIX ?? 'm1-browser-first';
if (process.env.M1_BASE !== 'http://localhost:15275') throw new Error('M1 requires isolated destination');
async function login(page: Page, role: string) {
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(accounts[role].email);
  await page.getByLabel('Contraseña', { exact: true }).fill(accounts[role].password);
  await page.getByRole('button', { name: 'Iniciar sesión', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Cerrar sesión', exact: true })).toBeVisible();
}
async function screenshot(page: Page, label: string, width: number, height: number) {
  await page.setViewportSize({ width, height });
  await page.screenshot({ path: `tests/evidence/${prefix}-${label}-${width}x${height}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
}
async function newStudent(page: Page, code: string, name: string, createSection = false) {
  await page.goto('/estudiantes');
  await page.getByRole('button', { name: 'Nuevo estudiante', exact: true }).click();
  await page.getByLabel('Código del estudiante', { exact: true }).fill(code);
  await page.getByLabel('Nombre completo', { exact: true }).fill(name);
  if (createSection) {
    await page.getByRole('button', { name: 'Crear sección', exact: true }).click();
    await page.getByLabel('Código de sección').fill('B');
    await page.getByLabel('Tutor responsable').selectOption({ label: 'Prueba M1 TUTOR' });
    await page.getByRole('button', { name: 'Guardar nueva sección' }).click();
    await expect(page.getByLabel('Código del estudiante', { exact: true })).toHaveValue(code);
    await expect(page.getByLabel('Nombre completo', { exact: true })).toHaveValue(name);
  } else await page.getByLabel('Grado / sección', { exact: true }).selectOption({ label: '1.º / A' });
  await page.getByRole('button', { name: 'Guardar estudiante y matrícula' }).click();
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  return new URL(page.url());
}

test('M1: preparación vacía, registro, revisiones, persistencia y cuatro roles', async ({ page, browser }) => {
  await login(page, 'ADMIN');
  await page.goto('/estudiantes');
  await expect(page.getByText('Todavía no hay periodos disponibles', { exact: true })).toBeVisible();
  for (const [w,h] of [[1440,900],[768,1024],[390,844]]) await screenshot(page, 'vacio', w,h);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: 'Periodos', exact: true }).click();
  await page.getByRole('button', { name: 'Nuevo periodo', exact: true }).click();
  await page.getByLabel('Código del periodo').fill('M1-B1');
  await page.getByLabel('Fecha de inicio').fill('2026-01-01');
  await page.getByLabel('Fecha de fin').fill('2026-12-31');
  await page.getByRole('button', { name: 'Crear periodo', exact: true }).click();
  await expect(page.getByLabel('Periodo de consulta')).toContainText('M1-B1');
  await page.getByRole('button', { name: 'Secciones', exact: true }).click();
  await page.getByRole('button', { name: 'Nueva sección', exact: true }).click();
  await page.getByLabel('Código de sección').fill('A');
  await page.getByLabel('Tutor responsable').selectOption({ label: 'Prueba M1 TUTOR' });
  await page.getByRole('button', { name: 'Guardar nueva sección' }).click();
  await expect(page.getByText('Cambios guardados en el servidor.', { exact: true })).toBeVisible();
  const first = await newStudent(page, 'M1-001', 'Álvarez · alumno de prueba M1');
  const second = await newStudent(page, 'M1-002', 'Segundo alumno de prueba M1');
  const foreign = await newStudent(page, 'M1-003', 'Tercer alumno de prueba M1', true);
  await page.goto(first.pathname + first.search);
  await expect(page.getByRole('heading', { name: 'Sin mediciones', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Nueva medición', exact: true }).click();
  await page.getByLabel('Fecha y hora de corte · Lima', { exact: true }).fill('2026-05-01T18:00:00');
  await page.getByLabel('Todo lo informado estaba disponible desde · Lima', { exact: true }).fill('2026-05-01T17:00:00');
  await page.getByLabel('Promedio · 0–20', { exact: true }).fill('25');
  await page.getByRole('button', { name: 'Guardar medición', exact: true }).click();
  expect(await page.getByLabel('Promedio · 0–20', { exact: true }).evaluate(el => (el as HTMLInputElement).validity.rangeOverflow)).toBeTruthy();
  await page.getByLabel('Promedio · 0–20', { exact: true }).fill('0');
  await page.getByLabel('Entrega de actividades · 0–100 %', { exact: true }).fill('80');
  await page.getByLabel('Incidencias · entero ≥ 0', { exact: true }).fill('0');
  await screenshot(page, 'medicion', 768,1024);
  await screenshot(page, 'medicion', 390,844);
  let writes = 0;
  page.on('request', req => { if (req.method() === 'POST' && req.url().includes('/measurements?')) writes++; });
  await page.getByRole('button', { name: 'Guardar medición', exact: true }).evaluate(el => { (el as HTMLButtonElement).click(); (el as HTMLButtonElement).click(); });
  await expect(page.getByText('Medición guardada en el servidor · pendiente de evaluación.', { exact: true })).toBeVisible();
  expect(writes).toBe(1);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Álvarez · alumno de prueba M1', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Corregir medición · revisión 1', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Corregir medición · revisión 1', exact: true }).click();
  await page.getByLabel('Promedio · 0–20', { exact: true }).fill('14');
  await page.getByLabel('Motivo de corrección', { exact: false }).fill('Corregir digitación de prueba');
  const id = first.pathname.split('/').at(-1)!;
  const period = first.searchParams.get('period_id')!;
  const csrf = (await (await page.request.get('/api/v1/auth/csrf')).json()).csrf_token;
  const original = (await (await page.request.get(`/api/v1/students/${id}/measurements?period_id=${period}`)).json()).items[0];
  const concurrent = await page.request.post(`/api/v1/students/${id}/measurements?period_id=${period}`, { headers: { 'Origin': process.env.M1_BASE!, 'X-CSRF-Token': csrf }, data: {
    creation_key: randomUUID(), window_start: original.window_start, cutoff_at: original.cutoff_at, available_at: original.available_at,
    purpose: 'PARTIAL', average_grade: 12, supersedes_id: original.id, expected_revision: 1, correction_reason: 'Cambio concurrente de prueba',
  } });
  expect(concurrent.status()).toBe(200);
  await page.getByRole('button', { name: 'Guardar nueva revisión', exact: true }).click();
  await expect(page.getByText('Esta medición ya tiene una revisión posterior.', { exact: false })).toBeVisible();
  await expect(page.getByLabel('Promedio · 0–20', { exact: true })).toHaveValue('14');
  await page.getByRole('button', { name: 'Consultar revisión actual conservando valores del borrador' }).click();
  await expect(page.getByLabel('Motivo de corrección', { exact: false })).toHaveAttribute('name','correction_reason');
  await page.getByRole('button', { name: 'Guardar nueva revisión', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Corregir medición · revisión 3', exact: true })).toBeVisible();
  await page.reload();
  for (const r of [1,2,3]) await expect(page.getByRole('button', { name: `Corregir medición · revisión ${r}`, exact: true })).toBeVisible();
  await screenshot(page, 'historial', 1440,900);
  await page.getByRole('button', { name: 'Editar datos / desactivar', exact: true }).click();
  await page.getByLabel('Estudiante activo', { exact: true }).uncheck();
  await page.getByLabel('Motivo del cambio', { exact: true }).fill('Desactivación de prueba');
  await page.getByLabel('Confirmo este cambio de datos y estado').check();
  await page.getByRole('button', { name: 'Confirmar cambio del estudiante' }).click();
  await expect(page.getByRole('button', { name: 'Editar datos / reactivar', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Nueva medición', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Editar datos / reactivar', exact: true }).click();
  await page.getByLabel('Estudiante activo', { exact: true }).check();
  await page.getByLabel('Motivo del cambio', { exact: true }).fill('Reactivación explícita de prueba');
  await page.getByLabel('Confirmo este cambio de datos y estado').check();
  await page.getByRole('button', { name: 'Confirmar cambio del estudiante' }).click();
  await expect(page.getByRole('button', { name: 'Nueva medición', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Nueva medición', exact: true }).click();
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Nueva medición', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ir al historial ↓' }).click();
  await expect(page.getByRole('heading', { name: 'Historial', exact: true })).toBeFocused();
  // Cambiar la asignación de la segunda sección por API real ADMIN.
  const section = (await (await page.request.get(`/api/v1/sections?period_id=${period}`)).json()).find((g: {code:string}) => g.code === 'B');
  const otherTutor = (await (await page.request.get('/api/v1/catalogs/tutors')).json()).find((t:{display_name:string}) => t.display_name === 'Prueba M1 TUTOR_OTHER');
  const reassigned = await page.request.patch(`/api/v1/sections/${section.id}`, { headers: { 'Origin': process.env.M1_BASE!, 'X-CSRF-Token': csrf }, data: {
    creation_key: randomUUID(), expected_version: section.version, code: section.code, grade: section.grade,
    school_year: section.school_year, data_origin: section.data_origin, tutor_id: otherTutor.id,
  }});
  expect(reassigned.status()).toBe(200);
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
  for (const role of ['TUTOR','DIRECTOR','RESEARCHER']) {
    await login(page, role);
    await page.goto(first.pathname + first.search);
    if (role === 'RESEARCHER') await expect(page.getByText('Tu rol no permite abrir esta vista', { exact: true })).toBeVisible();
    else {
      await expect(page.getByRole('heading', { name: 'Álvarez · alumno de prueba M1', exact: true })).toBeVisible();
      if (role === 'TUTOR') {
        await page.getByRole('button', { name: 'Nueva medición', exact: true }).click();
        await page.getByLabel('Fecha y hora de corte · Lima', { exact: true }).fill('2026-06-01T18:00:00');
        await page.getByLabel('Todo lo informado estaba disponible desde · Lima', { exact: true }).fill('2026-06-01T17:00:00');
        await page.getByLabel('Promedio · 0–20', { exact: true }).fill('15');
        await page.getByRole('button', { name: 'Guardar medición', exact: true }).click();
        await expect(page.getByText('Medición guardada en el servidor · pendiente de evaluación.', { exact: true })).toBeVisible();
        await page.goto(foreign.pathname + foreign.search);
        await expect(page.getByRole('heading', { name: 'Este registro no está disponible', exact: true })).toBeVisible();
      } else await expect(page.getByRole('button', { name: 'Nueva medición', exact: true })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Editar datos / desactivar', exact: true })).toHaveCount(0);
    }
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
  }
});
