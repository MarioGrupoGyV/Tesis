import { expect, test } from '@playwright/test';
type Role = 'ADMIN' | 'TUTOR' | 'DIRECTOR' | 'RESEARCHER';
const roles: Role[] = ['ADMIN','TUTOR','DIRECTOR','RESEARCHER'];
const accounts = JSON.parse(process.env.E2E_ACCOUNTS ?? '{}') as Record<Role,{email:string;password:string}>;
const scope = process.env.E2E_SCOPE;
const prefix = process.env.E2E_EVIDENCE_PREFIX ?? 's3-1-isolated';
const base = process.env.E2E_BASE_URL;
if (!roles.every(r=>accounts[r]?.email && accounts[r]?.password) ||
    !((scope==='isolated' && base==='http://localhost:15174') || (scope==='active' && base==='http://localhost:15173'))) {
  throw new Error('Usa el runner explícito de revisión local o aislada.');
}
const sizes = [[1440,900],[768,1024],[390,844]];
const syntheticNotice = 'Estudio con datos sintéticos. No corresponde a estudiantes reales.';
const roleLabels: Record<Role, string> = {ADMIN:'Administrador',TUTOR:'Tutor',DIRECTOR:'Directivo',RESEARCHER:'Investigador'};
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
    const processingResponse=await page.request.get('/api/v1/processing/status');
    expect(processingResponse.status()).toBe(200);
    const processing=await processingResponse.json();
    expect(processing.scope).toBe('SYNTHETIC_STUDY');
    expect(processing.notice).toBe(syntheticNotice);
    expect(processing.institutional_ready).toBe(false);
    expect(typeof processing.synthetic_ready).toBe('boolean');
    for(const operation of Object.values(processing.operations) as {available:boolean;reason:string|null}[]) {
      expect(typeof operation.available).toBe('boolean');
      if(role==='RESEARCHER') expect(operation.available).toBe(false);
    }
    const periods=role==='RESEARCHER'?[]:await (await page.request.get('/api/v1/periods')).json() as {id:string;data_origin:string}[];
    if(scope==='isolated') expect(periods).toEqual([]);
    for (const [width,height] of sizes) {
      await page.setViewportSize({width,height});
      await page.reload();
      await expect(page.getByText('Sesión activa',{exact:true})).toBeVisible();
      await expect(page.getByText(roleLabels[role],{exact:true})).toBeVisible();
      await expect(page.getByText(syntheticNotice,{exact:true})).toBeVisible();
      if(role==='RESEARCHER') {
        await expect(page.getByText(/Tu cuenta no tiene permiso|Tu rol de investigador/).first()).toBeVisible();
      } else if(periods.length===0) {
        await expect(page.getByText('No hay periodos configurados para tu cuenta.')).toBeVisible();
        await expect(page.getByText('No hay secciones disponibles. Primero debe configurarse un periodo.')).toBeVisible();
      } else {
        const selectedPeriod=periods[0];
        await expect(page.getByLabel('Selecciona un periodo')).toHaveValue(selectedPeriod.id);
        if(selectedPeriod.data_origin==='SYNTHETIC') await expect(page.getByText('Datos sintéticos',{exact:true})).toBeVisible();
        const sectionsResponse=await page.request.get(`/api/v1/sections?period_id=${encodeURIComponent(selectedPeriod.id)}`);
        expect(sectionsResponse.status()).toBe(200);
        const sections=await sectionsResponse.json() as {id:string;code:string}[];
        if(sections.length===0) await expect(page.getByText('No hay secciones asignadas en este periodo.')).toBeVisible();
        else {
          await expect(page.getByRole('table')).toBeVisible();
          await expect(page.getByRole('row')).toHaveCount(sections.length+1);
          for(const section of sections) await expect(page.getByRole('cell',{name:section.code,exact:true})).toBeVisible();
        }
      }
      await page.screenshot({path:`tests/evidence/${prefix}-${role.toLowerCase()}-${width}x${height}.png`,fullPage:true});
      if(role==='RESEARCHER') {
        await expect(page.getByText('Tu rol de investigador no tiene acceso al contexto escolar.')).toBeVisible();
        await expect(page.getByText('No hay secciones disponibles. Primero debe configurarse un periodo.')).toHaveCount(0);
      }
      await expect(page.getByText(/DEMO/)).toHaveCount(0);
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
    const blockedCode=(await blocked.json()).code;
    if(role==='ADMIN') expect(['INSTITUTIONAL_PROCESSING_NOT_READY','UNREGISTERED_SYNTHETIC_FILE','INVALID_FORM']).toContain(blockedCode);
    else expect(blockedCode).toBe('FORBIDDEN');
    await page.keyboard.press('Enter');
    await expect(page.getByText('Sesión cerrada correctamente.')).toBeVisible();
    await context.addCookies([cookie]);
    expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);
    expect((await page.request.get('/api/v1/processing/status')).status()).toBe(401);
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
  expect((await page.request.get('/api/v1/processing/status')).status()).toBe(401);
  await page.screenshot({path:`tests/evidence/${prefix}-invalid-login.png`,fullPage:true});
});
