import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
type Role='ADMIN'|'TUTOR'|'DIRECTOR'|'RESEARCHER';
type Student={id:string;anon_code:string;section_id:string;risk_level:'LOW'|'MEDIUM'|'HIGH'|null;evaluation_status:string};
type Reference={id:string;anon_code:string;section_id:string;snapshot_id:string;revision:number};
type Study={study_id:string;period_id:string;csv_file:string;csv_sha256:string;student_count:number;
  real_period_id?:string;own_section:{id:string;code:string};foreign_section:{id:string;code:string};
  own_student:Reference;foreign_student:Reference;insufficient_student:Reference;pending_student:Reference|null;
  model:{id:string;name:string}};
const roles:Role[]=['ADMIN','TUTOR','DIRECTOR','RESEARCHER'];
const accounts=JSON.parse(process.env.E2E_ACCOUNTS??'{}') as Record<Role,{email:string;password:string}>;
const study=JSON.parse(process.env.E2E_STUDY??'{}') as Study;
const scope=process.env.E2E_SCOPE;
const phase=process.env.E2E_PHASE;
const prefix=process.env.E2E_EVIDENCE_PREFIX??'s4-isolated';
const base=process.env.E2E_BASE_URL;
if(!prefix.startsWith('s4')||!roles.every(role=>accounts[role]?.email&&accounts[role]?.password)||
  !study.period_id||!study.csv_file||!((scope==='isolated'&&base==='http://localhost:15174')||
  (scope==='active'&&base==='http://localhost:15173'))) throw new Error('Usa el runner S4 explícito con su contexto privado.');
const sizes=[[1440,900],[768,1024],[390,844]];
const notice='Estudio con datos sintéticos. No corresponde a estudiantes reales.';
const roleLabels:Record<Role,string>={ADMIN:'Administrador',TUTOR:'Tutor',DIRECTOR:'Directivo',RESEARCHER:'Investigador'};
const missing='00000000-0000-4000-8000-000000000222';
const contextPath=(path:string)=>`${path}?period_id=${encodeURIComponent(study.period_id)}`;

async function login(page:Page,role:Role) {
  await page.goto(contextPath('/'));
  await expect(page.getByRole('heading',{name:'Iniciar sesión',exact:true})).toBeVisible();
  await page.getByLabel('Correo electrónico').fill(accounts[role].email);
  await page.getByLabel('Contraseña',{exact:true}).fill(accounts[role].password);
  await page.getByRole('button',{name:'Iniciar sesión',exact:true}).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.user-summary').getByText(roleLabels[role],{exact:true})).toBeVisible();
  expect((await (await page.request.get('/api/v1/auth/me')).json()).role).toBe(role);
}
async function navigate(page:Page,name:string) {
  if(await page.getByRole('button',{name:'Abrir menú',exact:true}).isVisible()) {
    await page.getByRole('button',{name:'Abrir menú',exact:true}).click();
    await page.getByRole('dialog').getByRole('link',{name,exact:true}).click();
  } else await page.locator('.desktop-sidebar').getByRole('link',{name,exact:true}).click();
}
async function capture(page:Page,name:string) {
  for(const [width,height] of sizes) {
    await page.setViewportSize({width,height});
    await page.locator('#main-content h1').first().focus();
    await page.evaluate(()=>window.scrollTo(0,0));
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:`tests/evidence/${prefix}-${name}-${width}x${height}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:900});
}
async function students(page:Page):Promise<{items:Student[];total:number}> {
  const response=await page.request.get(`/api/v1/students?period_id=${study.period_id}&page_size=100`);
  expect(response.status()).toBe(200);
  return response.json();
}
async function inferenceDiagnostic(response:APIResponse,stage:'deferred-post'|'body-loss-post') {
  // Diagnóstico mínimo antes de la aserción: no conservar mensajes, registros,
  // cuerpos, cookies, CSRF ni parámetros privados de la petición.
  const body=response.ok()?null:await response.json().catch(()=>null) as {code?:unknown;request_id?:unknown}|null;
  const candidate=body?.request_id??response.headers()['x-request-id'];
  const requestId=typeof candidate==='string'&&/^[0-9a-f-]{36}$/i.test(candidate)?candidate:null;
  const code=typeof body?.code==='string'&&/^[A-Z0-9_]{1,80}$/.test(body.code)?body.code:null;
  test.info().annotations.push({type:'inference-http-diagnostic',description:JSON.stringify({stage,status:response.status(),code,request_id:requestId})});
}

test('ADMIN: primera importación registrada mediante interfaz y API reales',async({page})=>{
  test.skip(scope!=='isolated'||phase!=='import');
  test.setTimeout(120000);
  await login(page,'ADMIN');
  await expect(page.getByLabel('Periodo de consulta')).toHaveValue(study.period_id);
  expect((await students(page)).total).toBe(0);
  const emptyModels=await page.request.get('/api/v1/models');expect(emptyModels.status()).toBe(200);
  expect((await emptyModels.json()).items).toEqual([]);
  await navigate(page,'Modelos');
  await expect(page.getByRole('heading',{name:'Modelo no disponible',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Evaluar ahora',exact:true})).toBeDisabled();
  await capture(page,'first-models-empty');
  await navigate(page,'Datos');
  await expect(page.getByRole('heading',{name:'Importar información',exact:true})).toBeVisible();
  const headerDownload=page.waitForEvent('download');
  await page.getByRole('button',{name:'Descargar cabeceras CSV',exact:true}).click();
  const headerStream=await (await headerDownload).createReadStream();
  expect(headerStream).not.toBeNull();
  const headerChunks:Buffer[]=[];
  for await(const chunk of headerStream!) headerChunks.push(Buffer.from(chunk));
  const expectedHeaders=['student_code','grade','section','cutoff_at','target_date','available_at',
    'window_start','average_grade','attendance_pct','activities_pct','participation_level','behavior_incidents','age_years'];
  const headerRows=Buffer.concat(headerChunks).toString('utf8').replace(/\r?\n$/,'').split(/\r?\n/);
  expect(headerRows).toEqual([expectedHeaders.join(',')]);expect(expectedHeaders).toHaveLength(13);
  const fileChooser=page.waitForEvent('filechooser');
  await page.getByRole('button',{name:'Seleccionar CSV',exact:true}).click();
  await (await fileChooser).setFiles(study.csv_file);
  const previewRequest=page.waitForResponse(response=>response.url().endsWith('/api/v1/imports/preview')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Revisar archivo',exact:true}).click();
  const preview=await previewRequest;
  expect(preview.status()).toBe(201);
  let batch=await preview.json();
  expect(batch.status).toBe('READY');expect(batch.file_sha256).toBe(study.csv_sha256);
  expect(batch.invalid_rows).toBe(0);expect(batch.planned_students).toBeGreaterThan(20);
  expect((await students(page)).total).toBe(0);
  await expect(page.getByRole('button',{name:'Confirmar importación',exact:true})).toBeDisabled();
  await capture(page,'first-import-review');
  await page.getByRole('checkbox',{name:'Revisé las validaciones y confirmo importar este archivo sintético en el periodo seleccionado.'}).check();
  // Solo la respuesta negativa se simula. El lote/CSV/vista previa anteriores y
  // la revisión/confirmación posteriores siguen siendo del servidor real.
  test.info().annotations.push({type:'preview-stale-simulation',description:'Respuesta 409 de interfaz simulada; no acredita conflicto de versión del backend.'});
  const staleVersion=batch.preview_version;
  const stalePath=`**/api/v1/imports/${batch.id}/commit`;
  await page.route(stalePath,route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({
    code:'IMPORT_PREVIEW_STALE',message:'La vista previa cambió; vuelve a revisar el archivo.',details:[],request_id:missing})}));
  const stale=page.waitForResponse(response=>response.url().endsWith(`/imports/${batch.id}/commit`));
  await page.getByRole('button',{name:'Confirmar importación',exact:true}).click();expect((await stale).status()).toBe(409);
  await expect(page.getByRole('heading',{name:'La vista previa necesita otra revisión',exact:true})).toBeVisible();
  await expect(page.getByRole('checkbox',{name:'Revisé las validaciones y confirmo importar este archivo sintético en el periodo seleccionado.'})).not.toBeChecked();
  await expect(page.getByRole('button',{name:'Confirmar importación',exact:true})).toBeDisabled();
  expect((await students(page)).total).toBe(0);
  await page.screenshot({path:`tests/evidence/${prefix}-http-simulated-preview-stale-409.png`,fullPage:true});
  await page.unroute(stalePath);
  const reviewed=page.waitForResponse(response=>response.url().endsWith('/api/v1/imports/preview'));
  await page.getByRole('button',{name:'Revisar archivo de nuevo',exact:true}).click();
  const refreshed=await reviewed;expect(refreshed.status()).toBe(200);batch=await refreshed.json();
  expect(batch.status).toBe('READY');expect(batch.file_sha256).toBe(study.csv_sha256);
  expect(batch.preview_version).toBeGreaterThan(staleVersion);
  await expect(page.getByRole('button',{name:'Confirmar importación',exact:true})).toBeDisabled();
  await page.getByRole('checkbox',{name:'Revisé las validaciones y confirmo importar este archivo sintético en el periodo seleccionado.'}).check();
  const commitRequest=page.waitForResponse(response=>response.url().endsWith(`/imports/${batch.id}/commit`));
  await page.getByRole('button',{name:'Confirmar importación',exact:true}).click();
  const commit=await commitRequest;expect(commit.status()).toBe(200);
  const result=await commit.json();expect(result.reused_result).toBe(false);
  expect(result.created_snapshots).toBe(batch.planned_snapshots);
  expect(commit.request().postDataJSON().expected_preview_version).toBe(batch.preview_version);
  expect(commit.request().headers()['x-csrf-token']).toBeTruthy();
  await expect(page.getByRole('heading',{name:'Estudiantes',exact:true})).toBeVisible();
  expect((await students(page)).total).toBe(batch.planned_students);
  await capture(page,'first-import-committed');
  await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();
  await expect(page.getByText('Sesión cerrada correctamente.',{exact:true})).toBeVisible();
});

for(const role of roles) test(`${role}: navegación S4, datos efectivos, permisos y sesión`,async({page,context})=>{
  test.skip(phase==='import');test.setTimeout(180000);
  const schoolRequests:string[]=[];
  page.on('request',request=>{if(/\/api\/v1\/(periods|sections|students|models|imports|predictions)(?:[/?]|$)/.test(request.url())) schoolRequests.push(request.url());});
  if(role==='ADMIN') {
    for(const [width,height] of sizes) {
      await page.setViewportSize({width,height});await page.goto(contextPath('/'));
      await expect(page.getByRole('heading',{name:'Iniciar sesión',exact:true})).toBeVisible();
      await page.getByLabel('Correo electrónico').focus();await page.keyboard.press('Tab');
      await expect(page.getByLabel('Contraseña',{exact:true})).toBeFocused();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await page.screenshot({path:`tests/evidence/${prefix}-login-${width}x${height}.png`,fullPage:true});
    }
  }
  await page.setViewportSize({width:1440,height:900});await login(page,role);
  const status=await (await page.request.get('/api/v1/processing/status')).json();
  expect(status.scope).toBe('SYNTHETIC_STUDY');expect(status.notice).toBe(notice);
  expect(status.institutional_ready).toBe(false);
  for(const operation of Object.values(status.operations) as {available:boolean;reason:string|null}[]) {
    expect(typeof operation.available).toBe('boolean');if(role==='RESEARCHER') expect(operation.available).toBe(false);
  }
  await expect(page.getByText(notice,{exact:true}).first()).toBeVisible();
  await capture(page,`${role.toLowerCase()}-home`);
  await page.setViewportSize({width:390,height:844});
  const menu=page.getByRole('button',{name:'Abrir menú',exact:true});await menu.click();
  await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');
  await expect(menu).toBeFocused();await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.setViewportSize({width:1440,height:900});
  if(role==='RESEARCHER') {
    await expect(page.getByText('Tu rol de investigador no tiene acceso al contexto escolar.',{exact:true})).toBeVisible();
    await expect(page.getByLabel('Periodo de consulta')).toHaveCount(0);
    expect(schoolRequests).toEqual([]);
    for(const path of ['/estudiantes','/datos','/modelos']) {
      await page.goto(contextPath(path));await expect(page.getByRole('heading',{name:'Acceso no disponible',exact:true})).toBeVisible();
    }
    expect(schoolRequests).toEqual([]);
    expect((await page.request.get('/api/v1/periods',{headers:{'X-Role':'ADMIN'}})).status()).toBe(403);
    expect((await page.request.get(`/api/v1/students?period_id=${study.period_id}`)).status()).toBe(403);
  } else {
    await expect(page.getByLabel('Periodo de consulta')).toHaveValue(study.period_id);
    const sections=await (await page.request.get(`/api/v1/sections?period_id=${study.period_id}`)).json();
    if(role==='TUTOR') {
      expect(sections.map((item:{id:string})=>item.id)).toContain(study.own_section.id);
      expect(sections.map((item:{id:string})=>item.id)).not.toContain(study.foreign_section.id);
    }
    await navigate(page,'Estudiantes');await expect(page.getByRole('heading',{name:'Estudiantes',exact:true})).toBeVisible();
    const data=await students(page);expect(data.total).toBe(role==='TUTOR'?data.items.length:study.student_count);
    expect(data.total).toBeGreaterThan(20);
    await expect(page.locator('.student-table tbody tr')).toHaveCount(20);
    await expect(page.getByLabel('Buscar código')).toHaveAttribute('maxlength','40');
    const firstCodes=await page.locator('.student-code-link').allTextContents();
    await page.getByRole('button',{name:'Siguiente →',exact:true}).click();
    await expect(page.getByRole('navigation',{name:'Paginación'})).toContainText('Página 2');
    const secondCodes=await page.locator('.student-code-link').allTextContents();
    expect(firstCodes.some(code=>secondCodes.includes(code))).toBe(false);
    await page.getByRole('button',{name:'← Anterior',exact:true}).click();
    await expect(page.getByRole('navigation',{name:'Paginación'})).toContainText('Página 1');
    expect(await page.locator('.student-code-link').allTextContents()).toEqual(firstCodes);
    await page.getByLabel('Buscar código').fill(study.own_student.anon_code);
    await page.getByRole('button',{name:'Aplicar filtros',exact:true}).click();
    await expect(page.locator('.student-table tbody tr')).toHaveCount(1);
    await page.getByLabel('Buscar código').fill('SIN-COINCIDENCIAS-PRUEBA');
    await page.getByRole('button',{name:'Aplicar filtros',exact:true}).click();
    await expect(page.getByRole('heading',{name:'No hay registros con estos filtros',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Limpiar filtros',exact:true}).first().click();
    await expect(page.locator('.student-table tbody tr')).toHaveCount(20);
    const risk=data.items.find(item=>item.risk_level)?.risk_level;
    expect(risk).toBeTruthy();await page.getByLabel('Riesgo estimado').selectOption(risk!);
    await page.getByLabel('Orden',{exact:true}).selectOption('risk_desc');
    const filteredResponse=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/v1/students'&&new URL(response.url()).searchParams.get('risk_level')===risk);
    await page.getByRole('button',{name:'Aplicar filtros',exact:true}).click();
    expect((await (await filteredResponse).json()).items.every((item:Student)=>item.risk_level===risk)).toBe(true);
    await page.getByRole('button',{name:'Limpiar filtros',exact:true}).first().click();
    await expect(page.locator('.student-table tbody tr')).toHaveCount(20);
    if(role==='ADMIN') await capture(page,'students');
    await page.getByRole('link',{name:`Ver registro de ${study.own_student.anon_code}`,exact:true}).click();
    await expect(page.getByRole('heading',{name:'Datos observados',exact:true})).toBeVisible();
    await expect(page.getByRole('heading',{name:'Historial',exact:true})).toBeVisible();
    await page.reload();await expect(page.getByRole('heading',{name:study.own_student.anon_code,exact:true})).toBeVisible();
    const detail=await (await page.request.get(`/api/v1/students/${study.own_student.id}?period_id=${study.period_id}`)).json();
    if(detail.latest_prediction) {
      expect(detail.latest_prediction.probabilities_calibrated).toBe(false);
      expect(['probability_low','probability_medium','probability_high'].every(name=>detail.latest_prediction[name]===null)).toBe(true);
      await expect(page.getByText(/Esta evaluación no dispone de probabilidades calibradas/)).toBeVisible();
    }
    const history=page.locator('section').filter({has:page.getByRole('heading',{name:'Historial',exact:true})});
    await expect(history.locator('ol > li')).toHaveCount(5);
    const firstHistory=await (await page.request.get(`/api/v1/students/${study.own_student.id}/timeline?period_id=${study.period_id}&page_size=5`)).json();
    const nextHistory=page.waitForResponse(response=>new URL(response.url()).pathname===`/api/v1/students/${study.own_student.id}/timeline`&&new URL(response.url()).searchParams.get('page')==='2');
    await history.getByRole('button',{name:'Siguiente →',exact:true}).click();
    const secondHistory=await (await nextHistory).json();
    expect(secondHistory.items.length).toBeGreaterThan(0);
    expect(secondHistory.items.some((event:{id:string})=>firstHistory.items.some((first:{id:string})=>first.id===event.id))).toBe(false);
    await expect(history.getByRole('navigation',{name:'Paginación'})).toContainText('Página 2');
    await page.getByLabel('Eventos por página').selectOption('10');
    await expect(history.getByRole('navigation',{name:'Paginación'})).toContainText('Página 1');
    await page.getByLabel('Eventos por página').selectOption('5');
    await expect(history.locator('ol > li')).toHaveCount(5);
    await page.getByRole('button',{name:'Consultar evaluación',exact:true}).first().click();
    await expect(page.getByRole('heading',{name:'Evaluación del historial',exact:true})).toBeVisible();
    if(role==='ADMIN') await capture(page,'student-detail');
    await page.goBack();await expect(page.getByRole('heading',{name:'Estudiantes',exact:true})).toBeVisible();
    if(role==='TUTOR') {
      await page.goto(contextPath(`/estudiantes/${study.foreign_student.id}`));
      await expect(page.getByRole('heading',{name:'Este registro no está disponible',exact:true})).toBeVisible();
      await expect(page.getByText(study.foreign_student.anon_code,{exact:true})).toHaveCount(0);
      await page.goto(contextPath(`/estudiantes/${missing}`));
      await expect(page.getByRole('heading',{name:'Este registro no está disponible',exact:true})).toBeVisible();
    }
    if(role==='ADMIN') {
      await page.goto(contextPath(`/estudiantes/${study.insufficient_student.id}`));
      await expect(page.getByText(/Datos insuficientes para estimar el riesgo/)).toBeVisible();
      await expect(page.locator('.student-detail-panel').filter({has:page.getByRole('heading',{name:'Datos observados',exact:true})}).getByText('Sin dato',{exact:true})).toHaveCount(5);
      await expect(page.locator('.student-detail-panel').filter({has:page.getByRole('heading',{name:'Última evaluación',exact:true})}).getByText(/Sin estimación/)).toBeVisible();
      if(study.pending_student) {
        await page.goto(contextPath(`/estudiantes/${study.pending_student.id}`));
        await expect(page.getByText('El corte actual está pendiente de evaluación. Una evaluación anterior no se aplica a esta revisión.',{exact:true})).toBeVisible();
        const pending=await (await page.request.get(`/api/v1/students/${study.pending_student.id}?period_id=${study.period_id}`)).json();
        expect(pending.latest_snapshot.revision).toBe(study.pending_student.revision);expect(pending.latest_prediction).toBeNull();
        await expect(page.getByRole('button',{name:'Consultar evaluación',exact:true}).first()).toBeVisible();
        await page.screenshot({path:`tests/evidence/${prefix}-revision-pending.png`,fullPage:true});
      }
      await navigate(page,'Datos');await page.getByLabel('Archivo CSV registrado').setInputFiles(study.csv_file);
      const repeated=page.waitForResponse(response=>response.url().endsWith('/api/v1/imports/preview'));
      await page.getByRole('button',{name:'Revisar archivo',exact:true}).click();
      const reused=await repeated;expect(reused.status()).toBe(200);expect((await reused.json()).status).toBe('COMMITTED');
      await expect(page.getByRole('heading',{name:'Se reutilizó la importación existente',exact:true})).toBeVisible();
      await expect(page.getByRole('button',{name:'Confirmar importación',exact:true})).toHaveCount(0);
      await page.getByRole('button',{name:'Consultar lote',exact:true}).click();await capture(page,'data-reused');
      await page.getByLabel('Archivo CSV registrado').setInputFiles({name:'modified.csv',mimeType:'text/csv',buffer:Buffer.concat([readFileSync(study.csv_file),Buffer.from('\n')])});
      const invalid=page.waitForResponse(response=>response.url().endsWith('/api/v1/imports/preview'));
      await page.getByRole('button',{name:'Revisar archivo',exact:true}).click();
      expect((await invalid).status()).toBe(422);
      await expect(page.getByText('Usa el CSV exacto registrado por el generador local para este periodo. No se guardó el archivo.',{exact:true})).toBeVisible();
      await expect(page.getByText(/Referencia de soporte/)).toBeVisible();
      await navigate(page,'Modelos');await expect(page.getByRole('heading',{name:'Modelos',exact:true})).toBeVisible();
      await expect(page.getByRole('link',{name:study.model.name,exact:true})).toBeVisible();await capture(page,'models');
      test.info().annotations.push({type:'processing-status-simulation',description:'Solo el error 503 de ProcessingStatus está simulado; recuperación consulta API real.'});
      await page.route('**/api/v1/processing/status',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({
        code:'SERVICE_UNAVAILABLE',message:'Temporalmente no disponible.',details:[],request_id:missing})}));
      await page.goto(contextPath('/datos'));
      await expect(page.getByRole('heading',{name:'Importación no disponible',exact:true})).toBeVisible();
      await expect(page.getByLabel('Archivo CSV registrado')).toBeDisabled();
      await expect(page.getByRole('button',{name:'Revisar archivo',exact:true})).toBeDisabled();
      await page.screenshot({path:`tests/evidence/${prefix}-http-simulated-processing-503-import.png`,fullPage:true});
      await navigate(page,'Modelos');
      await expect(page.getByRole('radio',{name:'Instante actual',exact:true})).toBeDisabled();
      await expect(page.getByRole('button',{name:'Evaluar ahora',exact:true})).toBeDisabled();
      await page.screenshot({path:`tests/evidence/${prefix}-http-simulated-processing-503-model.png`,fullPage:true});
      await page.unroute('**/api/v1/processing/status');
      const readiness=page.waitForResponse(response=>response.url().endsWith('/api/v1/processing/status'));
      await page.getByRole('button',{name:'Volver a intentar',exact:true}).click();
      expect((await readiness).status()).toBe(200);
      await expect(page.getByRole('button',{name:'Evaluar ahora',exact:true})).toBeEnabled();
      await navigate(page,'Datos');await expect(page.getByLabel('Archivo CSV registrado')).toBeEnabled();
      await page.getByLabel('Archivo CSV registrado').setInputFiles(study.csv_file);
      await expect(page.getByRole('button',{name:'Revisar archivo',exact:true})).toBeEnabled();
      await navigate(page,'Modelos');
      await page.getByRole('link',{name:study.model.name,exact:true}).click();
      await expect(page.getByRole('heading',{name:'Información del modelo',exact:true})).toBeVisible();
      await page.reload();await expect(page.getByRole('heading',{name:study.model.name,exact:true})).toBeVisible();
      await expect(page.getByRole('button',{name:/Entrenar|Activar/})).toHaveCount(0);
      const token=(await (await page.request.get('/api/v1/auth/csrf')).json()).csrf_token;
      const requestBody={period_id:study.period_id,as_of:new Date().toISOString()};
      expect((await page.request.post('/api/v1/predictions/run',{data:requestBody})).status()).toBe(403);
      expect((await page.request.post('/api/v1/predictions/run',{data:requestBody,headers:{'X-CSRF-Token':'incorrecto'}})).status()).toBe(403);
      await page.getByRole('radio',{name:'Elegir fecha y hora (America/Lima)',exact:true}).check();
      await page.getByLabel('Fecha y hora en Lima').fill('2025-10-01T12:00');
      const unavailable=page.waitForResponse(response=>response.url().endsWith('/api/v1/predictions/run'));
      await page.getByRole('button',{name:'Evaluar ahora',exact:true}).click();expect((await unavailable).status()).toBe(409);
      await expect(page.getByText('Modelo no disponible.',{exact:true})).toBeVisible();
      await page.getByRole('radio',{name:'Instante actual',exact:true}).check();
      // El reloj de Windows se adelanta sin alterar performance, la petición ni
      // la regla temporal del servidor. La UI debe usar el Date observado de API.
      test.info().annotations.push({type:'host-clock-simulation',description:'Date del navegador adelantado diez minutos; API, as_of y validación temporal reales.'});
      const advancedHost=Date.now()+10*60*1000;
      await page.clock.setFixedTime(advancedHost);
      expect(await page.evaluate(()=>Date.now())).toBe(advancedHost);
      const inference=page.waitForResponse(response=>response.url().endsWith('/api/v1/predictions/run'));
      await page.getByRole('button',{name:'Evaluar ahora',exact:true}).click();
      const evaluated=await inference;expect(evaluated.status()).toBe(200);
      const output=await evaluated.json();expect(output.selected).toBe(study.student_count);
      const evaluatedServerDate=Date.parse(evaluated.headers()['date']??'');
      expect(Number.isFinite(evaluatedServerDate)).toBe(true);
      const acceptedInstant=Date.parse(evaluated.request().postDataJSON().as_of);
      expect(acceptedInstant).toBeLessThanOrEqual(evaluatedServerDate+1000);
      expect(advancedHost-acceptedInstant).toBeGreaterThan(9*60*1000);
      await page.clock.setFixedTime(Date.now());
      if(scope==='active') expect(output.created).toBe(0);
      expect(output.reused).toBeGreaterThan(0);expect(output.abstentions.length).toBeGreaterThan(0);
      expect(evaluated.request().headers()['x-csrf-token']).toBeTruthy();
      expect(new Date(evaluated.request().postDataJSON().as_of).getUTCFullYear()).toBe(new Date().getUTCFullYear());
      await expect(page.getByRole('heading',{name:'Evaluación completada',exact:true})).toBeVisible();
      await capture(page,'model-detail-evaluated');
      // Se retrasa la respuesta REAL ya procesada, sin fabricar datos. Cambiar
      // de pantalla debe cancelar/descartar el resultado del contexto anterior.
      let release!:()=>void;let received!:()=>void;let finished!:()=>void;let delayedCalls=0;
      const gate=new Promise<void>(resolve=>{release=resolve;});
      const intercepted=new Promise<void>(resolve=>{received=resolve;});
      const completed=new Promise<void>(resolve=>{finished=resolve;});
      await page.route('**/api/v1/predictions/run',async route=>{
        delayedCalls+=1;
        try {
          const actual=await route.fetch();await inferenceDiagnostic(actual,'deferred-post');expect(actual.status()).toBe(200);
          received();await gate;
          try { await route.fulfill({response:actual}); } catch { /* Fetch cancelado al salir de la vista. */ }
        } finally { finished(); }
      });
      await page.getByRole('button',{name:'Evaluar ahora',exact:true}).click();
      await intercepted;await navigate(page,'Inicio');
      await expect(page.getByRole('heading',{name:'Un contexto claro para consultar',exact:true})).toBeVisible();
      release();await completed;expect(delayedCalls).toBe(1);
      await expect(page.getByRole('heading',{name:'Evaluación completada',exact:true})).toHaveCount(0);
      await page.unroute('**/api/v1/predictions/run');
      await navigate(page,'Modelos');await page.getByRole('link',{name:study.model.name,exact:true}).click();
      await expect(page.getByRole('heading',{name:'Información del modelo',exact:true})).toBeVisible();
      test.info().annotations.push({type:'response-body-loss-simulation',description:'POST real 200; solo su cuerpo de respuesta se trunca para comprobar incertidumbre de interfaz.'});
      let lostBodyCalls=0;
      await page.route('**/api/v1/predictions/run',async route=>{
        lostBodyCalls+=1;
        const actual=await route.fetch();await inferenceDiagnostic(actual,'body-loss-post');expect(actual.status()).toBe(200);
        await route.fulfill({status:200,contentType:'application/json',body:'{"period_id":'});
      });
      const lostBodyResponse=page.waitForResponse(response=>response.url().endsWith('/api/v1/predictions/run')&&response.request().method()==='POST');
      await page.getByRole('button',{name:'Evaluar ahora',exact:true}).click();
      expect((await lostBodyResponse).status()).toBe(200);
      await expect(page.getByRole('alert')).toContainText('No pudimos leer la respuesta del sistema.');
      await expect(page.getByText('No recibimos la confirmación del servidor. Consulta los registros antes de repetir; una evaluación ya registrada se reutiliza.',{exact:true})).toBeVisible();
      await expect(page.getByRole('heading',{name:'Evaluación completada',exact:true})).toHaveCount(0);
      await page.waitForLoadState('networkidle');expect(lostBodyCalls).toBe(1);
      expect((await students(page)).total).toBe(study.student_count);
      await page.screenshot({path:`tests/evidence/${prefix}-http-simulated-response-body-loss.png`,fullPage:true});
      await page.unroute('**/api/v1/predictions/run');
      await navigate(page,'Inicio');await navigate(page,'Modelos');
      await page.getByRole('link',{name:study.model.name,exact:true}).click();
      await expect(page.getByRole('heading',{name:'Información del modelo',exact:true})).toBeVisible();
      if(study.real_period_id) {
        await page.getByLabel('Periodo de consulta').selectOption(study.real_period_id);
        await expect(page.getByLabel('Sección autorizada')).toHaveValue('');
        await expect(page.getByRole('button',{name:'Evaluar ahora',exact:true})).toBeDisabled();
        const real=await page.request.post('/api/v1/predictions/run',{data:{...requestBody,period_id:study.real_period_id},headers:{'X-CSRF-Token':token}});
        expect(real.status()).toBe(422);expect((await real.json()).code).toBe('INSTITUTIONAL_PROCESSING_NOT_READY');
        await navigate(page,'Datos');await expect(page.getByRole('heading',{name:'Importación no disponible',exact:true})).toBeVisible();
        await expect(page.getByLabel('Archivo CSV registrado')).toBeDisabled();
        await navigate(page,'Estudiantes');await expect(page.getByRole('heading',{name:'Este contexto todavía no tiene registros',exact:true})).toBeVisible();
        await expect(page.getByLabel('Buscar código')).toHaveValue('');
        await page.getByLabel('Periodo de consulta').selectOption(study.period_id);
      }
      // Estado de error HTTP simulado: complementa el recorrido real anterior.
      test.info().annotations.push({type:'http-simulation',description:'Solo el estado 503 de interfaz está simulado; no acredita API/PostgreSQL.'});
      await page.route('**/api/v1/students?*',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'SERVICE_UNAVAILABLE',message:'Temporalmente no disponible.',details:[],request_id:missing})}));
      await page.goto(contextPath('/estudiantes'));await expect(page.getByRole('alert')).toContainText('El servicio no está disponible temporalmente.');
      await expect(page.getByText(`Referencia de soporte: ${missing}`,{exact:true})).toBeVisible();
      await page.screenshot({path:`tests/evidence/${prefix}-http-simulated-503.png`,fullPage:true});
      await page.unroute('**/api/v1/students?*');await page.reload();await expect(page.locator('.student-table tbody tr')).toHaveCount(20);
    } else {
      for(const path of ['/datos','/modelos']) {
        await page.goto(contextPath(path));await expect(page.getByRole('heading',{name:'Acceso no disponible',exact:true})).toBeVisible();
      }
      expect((await page.request.get('/api/v1/models')).status()).toBe(403);
      const token=(await (await page.request.get('/api/v1/auth/csrf')).json()).csrf_token;
      expect((await page.request.post('/api/v1/predictions/run',{data:{period_id:study.period_id,as_of:new Date().toISOString()},headers:{'X-CSRF-Token':token}})).status()).toBe(403);
    }
  }
  await page.goto('/ruta-no-existe');
  await expect(page.getByRole('heading',{name:role==='RESEARCHER'?'Acceso no disponible':'Página no encontrada',exact:true})).toBeVisible();
  let releaseSessionResponse:(()=>void)|undefined;
  let completedSessionResponse:Promise<void>|undefined;
  if(role==='ADMIN') {
    let release!:()=>void;let received!:(status:number)=>void;let finished!:()=>void;
    const gate=new Promise<void>(resolve=>{release=resolve;});
    const captured=new Promise<number>(resolve=>{received=resolve;});
    completedSessionResponse=new Promise<void>(resolve=>{finished=resolve;});
    releaseSessionResponse=release;
    await page.getByLabel('Sección autorizada').selectOption(study.foreign_section.id);
    await page.route('**/api/v1/students?*',async route=>{
      if(new URL(route.request().url()).searchParams.get('section_id')!==study.foreign_section.id) {
        await route.continue();return;
      }
      try {
        const actual=await route.fetch();received(actual.status());await gate;
        try { await route.fulfill({response:actual}); } catch { /* Logout canceló el GET. */ }
      } catch { received(-1); } finally { finished(); }
    });
    await navigate(page,'Estudiantes');expect(await captured).toBe(200);
  }
  expect(await page.evaluate(()=>[localStorage.length,sessionStorage.length])).toEqual([0,0]);
  const cookie=(await context.cookies()).find(item=>item.name==='session')!;expect(cookie.httpOnly).toBe(true);expect(cookie.sameSite).toBe('Lax');
  await page.getByRole('button',{name:'Cerrar sesión',exact:true}).focus();await page.keyboard.press('Enter');
  await expect(page.getByText('Sesión cerrada correctamente.',{exact:true})).toBeVisible();
  if(role==='ADMIN') {
    // El formulario se usa en la misma SPA, sin recarga que ocultaría una fuga
    // de caché/resultado tardío entre sesiones.
    await page.getByLabel('Correo electrónico').fill(accounts.TUTOR.email);
    await page.getByLabel('Contraseña',{exact:true}).fill(accounts.TUTOR.password);
    await page.getByRole('button',{name:'Iniciar sesión',exact:true}).click();
    await expect(page.locator('.user-summary').getByText(roleLabels.TUTOR,{exact:true})).toBeVisible();
    await expect(page.getByLabel('Periodo de consulta')).toHaveValue(study.period_id);
    await navigate(page,'Estudiantes');
    await expect(page.getByRole('link',{name:`Ver registro de ${study.own_student.anon_code}`,exact:true})).toBeVisible();
    releaseSessionResponse!();await completedSessionResponse;
    await expect(page.getByRole('link',{name:`Ver registro de ${study.foreign_student.anon_code}`,exact:true})).toHaveCount(0);
    expect((await students(page)).items.every(item=>item.section_id===study.own_section.id)).toBe(true);
    await page.unroute('**/api/v1/students?*');
    await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();
    await expect(page.getByText('Sesión cerrada correctamente.',{exact:true})).toBeVisible();
  }
  await context.addCookies([cookie]);expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);
  expect((await page.request.get('/api/v1/processing/status')).status()).toBe(401);
  await page.goto(contextPath(`/estudiantes/${study.own_student?.id??missing}`));
  await expect(page.getByRole('heading',{name:'Iniciar sesión',exact:true})).toBeVisible();
  await expect(page.getByText(study.own_student?.anon_code??'UNUSED-CODE',{exact:true})).toHaveCount(0);
  await expect(page.getByLabel('Contraseña',{exact:true})).toHaveValue('');
});

test('Error de credenciales no autoriza contexto',async({page})=>{
  test.skip(phase==='import');await page.goto('/');
  await page.getByLabel('Correo electrónico').fill(accounts.ADMIN.email);
  await page.getByLabel('Contraseña',{exact:true}).fill('invalid-test-password');
  await page.getByRole('button',{name:'Iniciar sesión',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('Correo o contraseña incorrectos.');
  await expect(page.getByLabel('Contraseña',{exact:true})).toHaveValue('');
  expect((await page.request.get('/api/v1/periods')).status()).toBe(401);
  expect((await page.request.get('/api/v1/processing/status')).status()).toBe(401);
  await page.screenshot({path:`tests/evidence/${prefix}-invalid-login.png`,fullPage:true});
});
