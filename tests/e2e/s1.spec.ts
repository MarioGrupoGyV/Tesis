/** S1 only: actual login, server catalogs, session restoration and revocation. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

type DemoAccount = { role: 'ADMIN' | 'TUTOR' | 'DIRECTOR'; email: string; password: string };
type DemoCredentials = Record<'admin' | 'tutor' | 'director', { email: string; password: string }>;

test.use({
  baseURL: process.env.S1_BASE_URL ?? 'http://localhost:15173',
  trace: 'off',
  screenshot: 'off',
  video: 'off',
});

function accountFor(role: DemoAccount['role']): DemoAccount {
  const file = process.env.DEMO_CREDENTIALS_FILE;
  if (!file) throw new Error('Set DEMO_CREDENTIALS_FILE to the private file written by the explicit demo seed');
  const credentials = JSON.parse(readFileSync(file, 'utf8')) as DemoCredentials;
  const account = credentials[role.toLowerCase() as keyof DemoCredentials];
  if (!account?.email || !account?.password) throw new Error(`Missing demo account for ${role} in the private seed file`);
  return { ...account, role };
}

for (const role of ['ADMIN', 'TUTOR', 'DIRECTOR'] as const) {
  test(`${role}: login, contexto real, restauración y logout revocado`, async ({ page, context }) => {
    const account = accountFor(role);
    await page.goto('/');
    await expect(page.getByText('DEMO · datos sintéticos', { exact: false }).first()).toBeVisible();
    await page.getByLabel('Correo electrónico').fill(account.email);
    await page.getByLabel('Contraseña', { exact: true }).fill(account.password);
    const loginResponse = page.waitForResponse((response) => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
    expect((await loginResponse).status()).toBe(200);
    await expect(page.getByText('Sesión activa', { exact: true })).toBeVisible();
    await expect(page.getByText('✓ Contexto autorizado cargado.', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Selecciona un periodo')).toBeVisible();

    const serverUser = await page.request.get('/api/v1/auth/me');
    expect(serverUser.status()).toBe(200);
    const user = await serverUser.json() as { id: string; role: string };
    expect(user.role).toBe(role);
    const periodId = await page.getByLabel('Selecciona un periodo').inputValue();
    const serverSections = await page.request.get(`/api/v1/sections?period_id=${encodeURIComponent(periodId)}`);
    expect(serverSections.status()).toBe(200);
    const sections = await serverSections.json() as Array<{ code: string; grade: number; tutor_id: string | null }>;
    expect(sections.length).toBe(role === 'TUTOR' ? 1 : 2);
    if (role === 'TUTOR') expect(sections.every((section) => section.tutor_id === user.id)).toBe(true);
    else expect(sections.map((section) => `${section.grade}/${section.code}`).sort()).toEqual(['1/A', '2/A']);
    await expect(page.locator('tbody tr')).toHaveCount(sections.length);

    const sessionCookie = (await context.cookies()).find((cookie) => cookie.name === 'session');
    expect(sessionCookie).toBeDefined();
    expect(sessionCookie!.httpOnly).toBe(true);
    expect(sessionCookie!.sameSite).toBe('Lax');
    expect(sessionCookie!.secure).toBe(new URL(process.env.S1_BASE_URL ?? 'http://localhost:15173').protocol === 'https:');
    expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });

    await page.reload();
    await expect(page.getByText('Sesión activa', { exact: true })).toBeVisible();
    await expect(page.getByText('✓ Contexto autorizado cargado.', { exact: true })).toBeVisible();
    const logoutResponse = page.waitForResponse((response) => response.url().endsWith('/api/v1/auth/logout') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click();
    expect((await logoutResponse).status()).toBe(204);
    await expect(page.getByText('Sesión cerrada correctamente.', { exact: true })).toBeVisible();
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);

    // Replaying the old cookie must fail at the server, independently of UI state.
    await context.addCookies([sessionCookie!]);
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);
    expect((await page.request.get('/api/v1/auth/csrf')).status()).toBe(401);
    await context.clearCookies();
  });
}

test('credenciales inválidas muestran error y no autorizan catálogo', async ({ page }) => {
  const account = accountFor('ADMIN');
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(account.email);
  await page.getByLabel('Contraseña', { exact: true }).fill('S1-invalid-fixture-password');
  const loginResponse = page.waitForResponse((response) => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Iniciar sesión', exact: true }).click();
  expect((await loginResponse).status()).toBe(401);
  await expect(page.getByRole('alert')).toBeVisible();
  expect((await page.request.get('/api/v1/periods')).status()).toBe(401);
});
