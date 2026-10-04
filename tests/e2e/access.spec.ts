import { expect, test } from '@playwright/test';
type Role = 'ADMIN' | 'TUTOR' | 'DIRECTOR' | 'RESEARCHER';
const roles: Role[] = ['ADMIN','TUTOR','DIRECTOR','RESEARCHER'];
const accounts = JSON.parse(process.env.E2E_ACCOUNTS ?? '{}') as Record<Role,{email:string;password:string}>;
const scope = process.env.E2E_SCOPE;
const prefix = process.env.E2E_EVIDENCE_PREFIX ?? 's2-2-isolated';
const base = process.env.E2E_BASE_URL;
if (!roles.every(r=>accounts[r]?.email && accounts[r]?.password) ||
    !((scope==='isolated' && base==='http://localhost:15174') || (scope==='active' && base==='http://localhost:15173'))) {
  throw new Error('Usa el runner explícito de revisión local o aislada.');
}
const sizes = [[1440,900],[768,1024],[390,844]];
for (const role of roles) {
  test(`${role}: acceso, contexto, teclado, permisos y revocación`,async({page,context})=>{
    const account=accounts[role];
    for (const [width,height] of sizes) {
      await page.setViewportSize({width,height});
      await page.goto('/');
      await expect(page.getByRole('heading',{name:'Iniciar sesión'})).toBeVisible();
      await page.getByLabel('Correo electrónico').focus();
      await expect(page.getByLabel('Correo electrónico')).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(page.getByLabel('Contraseña',{exact:true})).toBeFocused();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      if(role==='ADMIN') await page.screenshot({path:`tests/evidence/${prefix}-login-${width}x${height}.png`,fullPage:true});
    }
    await page.getByLabel('Correo electrónico').fill(account.email);
    await page.getByLabel('Contraseña',{exact:true}).fill(account.password);
    await page.getByRole('button',{name:'Iniciar sesión',exact:true}).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByText('Sesión activa',{exact:true})).toBeVisible();
    const user=await (await page.request.get('/api/v1/auth/me')).json();
    expect(user.role).toBe(role);
    for (const [width,height] of sizes) {
      await page.setViewportSize({width,height});
      await page.reload();
      await expect(page.getByText('Sesión activa',{exact:true})).toBeVisible();
      if(role==='RESEARCHER') {
        await expect(page.getByText(/Tu cuenta no tiene permiso|Tu rol de investigador/).first()).toBeVisible();
      } else {
        await expect(page.getByText('No hay periodos configurados para tu cuenta.')).toBeVisible();
      }
      await page.screenshot({path:`tests/evidence/${prefix}-${role.toLowerCase()}-${width}x${height}.png`,fullPage:true});
      if(role==='RESEARCHER') {
        await expect(page.getByText('Tu rol de investigador no tiene acceso al contexto escolar.')).toBeVisible();
        await expect(page.getByText('No hay secciones disponibles. Primero debe configurarse un periodo.')).toHaveCount(0);
      } else {
        await expect(page.getByText('No hay secciones disponibles. Primero debe configurarse un periodo.')).toBeVisible();
      }
      await expect(page.getByText(/DEMO|demostración|datos sintéticos/)).toHaveCount(0);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await page.getByRole('button',{name:'Cerrar sesión'}).focus();
      await expect(page.getByRole('button',{name:'Cerrar sesión'})).toBeFocused();
    }
    expect(await page.evaluate(()=>[localStorage.length,sessionStorage.length])).toEqual([0,0]);
    const cookie=(await context.cookies()).find(c=>c.name==='session')!;
    expect(cookie.httpOnly).toBe(true);
    expect(cookie.sameSite).toBe('Lax');
    const csrf=await (await page.request.get('/api/v1/auth/csrf')).json();
    expect((await page.request.get('/api/v1/periods',{headers:{'X-Role':'ADMIN'}})).status()).toBe(role==='RESEARCHER'?403:200);
    const blocked=await page.request.post('/api/v1/imports/preview',{headers:{'X-CSRF-Token':csrf.csrf_token}});
    expect(blocked.status()).toBe(role==='ADMIN'?422:403);
    expect((await blocked.json()).code).toBe(role==='ADMIN'?'INSTITUTIONAL_PROCESSING_NOT_READY':'FORBIDDEN');
    await page.keyboard.press('Enter');
    await expect(page.getByText('Sesión cerrada correctamente.')).toBeVisible();
    await context.addCookies([cookie]);
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);
  });
}
test('Error de credenciales no autoriza contexto',async({page})=>{
  await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(accounts.ADMIN.email);
  await page.getByLabel('Contraseña',{exact:true}).fill('invalid-test-password');
  await page.getByRole('button',{name:'Iniciar sesión',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Correo o contraseña incorrectos.');
  await expect(page.getByLabel('Contraseña',{exact:true})).toHaveValue('');
  expect((await page.request.get('/api/v1/periods')).status()).toBe(401);
  await page.screenshot({path:`tests/evidence/${prefix}-invalid-login.png`,fullPage:true});
});
