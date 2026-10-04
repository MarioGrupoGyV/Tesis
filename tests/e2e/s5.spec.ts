import { expect, test, type Page, type APIResponse, type Response } from '@playwright/test';
import { createHash } from 'node:crypto';
import { writeFileSync } from 'node:fs';

type Role='ADMIN'|'TUTOR'|'DIRECTOR'|'RESEARCHER';
type Case={id:string;student_id:string;anon_code:string;section_id:string;version:number;status:string;assigned_to:string|null};
type Activity={id:string;objective:string;version:number;status:'PLANNED'|'DONE'|'CANCELLED';scheduled_at:string;performed_at:string|null};
type Detail={alert:Case;interventions:Activity[];history:{id:string;summary:string;entity_id:string}[]};
const roles:Role[]=['ADMIN','TUTOR','DIRECTOR','RESEARCHER'];
const accounts=JSON.parse(process.env.E2E_ACCOUNTS??'{}') as Record<Role,{email:string;password:string}>;
const study=JSON.parse(process.env.E2E_STUDY??'{}') as {period_id:string;student_count:number;real_period_id?:string;
  own_section:{id:string};foreign_section:{id:string};own_student:{id:string;anon_code:string};
  foreign_student:{id:string;anon_code:string};model:{id:string;name:string}};
const prefix=process.env.E2E_EVIDENCE_PREFIX??'s5-isolated';
const phase=process.env.E2E_PHASE;
const scope=process.env.E2E_SCOPE;
if(phase==='followup'&&(!prefix.startsWith('s5')||!study.period_id||!roles.every(role=>accounts[role]?.password))) throw new Error('Usa el runner S5 explícito y su contexto privado.');
const missing='00000000-0000-4000-8000-000000000555';
const sizes=[[1440,900],[768,1024],[390,844]];
const path=(url:string)=>`${url}?period_id=${encodeURIComponent(study.period_id)}`;
const samples:{schema:string;body:unknown}[]=[];
let foreignCase:Case|undefined;
const doneObjective='S5 interfaz: actividad exclusivamente simulada realizada';
const cancelledObjective='S5 interfaz: actividad exclusivamente simulada cancelada';

test.afterAll(()=>{if(samples.length) writeFileSync(`tests/evidence/${prefix}-response-samples.json`,JSON.stringify(samples,null,2)+'\n');});

async function login(page:Page,role:Role) {
  await page.goto(path('/'));
  await page.getByLabel('Correo electrónico').fill(accounts[role].email);
  await page.getByLabel('Contraseña',{exact:true}).fill(accounts[role].password);
  await page.getByRole('button',{name:'Iniciar sesión',exact:true}).focus();await page.keyboard.press('Enter');
  const label={ADMIN:'Administrador',TUTOR:'Tutor',DIRECTOR:'Directivo',RESEARCHER:'Investigador'}[role];
  await expect(page.locator('.user-summary').getByText(label,{exact:true})).toBeVisible();
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
    await page.setViewportSize({width,height});await page.locator('#main-content h1').first().focus();
    await page.evaluate(()=>window.scrollTo(0,0));
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:`tests/evidence/${prefix}-${name}-${width}x${height}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:900});
}
async function token(page:Page) {
  const response=await page.request.get('/api/v1/auth/csrf');expect(response.status()).toBe(200);
  return (await response.json()).csrf_token as string;
}
async function currentCases(page:Page):Promise<Case[]> {
  const response=await page.request.get(`/api/v1/alerts?period_id=${study.period_id}&page_size=100`);
  expect(response.status()).toBe(200);return (await response.json()).items;
}
async function detail(page:Page,id:string):Promise<Detail> {
  const response=await page.request.get(`/api/v1/alerts/${id}`);expect(response.status()).toBe(200);return response.json();
}
async function record(schema:string,response:APIResponse|Response) {expect(response.status()).toBe(200);samples.push({schema,body:await response.json()});}
function parseCsv(csv:string) {
  const rows:string[][]=[];let row:string[]=[];let cell='';let quoted=false;
  for(let i=0;i<csv.length;i++) {
    const character=csv[i];
    if(character==='"') {if(quoted&&csv[i+1]==='"') {cell+='"';i++;}else quoted=!quoted;}
    else if(character===','&&!quoted) {row.push(cell);cell='';}
    else if(character==='\n'&&!quoted) {row.push(cell.replace(/\r$/,''));rows.push(row);row=[];cell='';}
    else cell+=character;
  }
  if(cell||row.length) {row.push(cell);rows.push(row);}
  return rows;
}
async function download(page:Page,total:number,role:Role) {
  const response=page.waitForResponse(r=>r.url().includes('/api/v1/reports/export.csv'));
  const event=page.waitForEvent('download');await page.getByRole('button',{name:'Descargar CSV',exact:true}).click();
  const actual=await response;expect(actual.status()).toBe(200);
  expect(actual.headers()['content-type']).toContain('text/csv');expect(actual.headers()['cache-control']).toBe('no-store');
  const file=await event;expect(file.suggestedFilename()).toBe('seguimiento-escolar-reporte.csv');
  const stream=await file.createReadStream();expect(stream).not.toBeNull();
  const chunks:Buffer[]=[];for await(const chunk of stream!)chunks.push(Buffer.from(chunk));
  const bytes=Buffer.concat(chunks);expect([...bytes.subarray(0,3)]).toEqual([239,187,191]);
  const rows=parseCsv(bytes.toString('utf8').replace(/^\uFEFF/,''));expect(rows).toHaveLength(total+1);
  expect(rows[0]).toHaveLength(19);expect(rows[0]).toContain('codigo_sintetico');
  const codeIndex=rows[0].indexOf('codigo_sintetico');expect(new Set(rows.slice(1).map(row=>row[codeIndex])).size).toBe(total);
  expect(bytes.toString('utf8')).not.toContain('password_hash');expect(bytes.toString('utf8')).not.toContain(doneObjective);
  if(role==='TUTOR')expect(bytes.toString('utf8')).not.toContain(study.foreign_student.anon_code);
  writeFileSync(`tests/evidence/${prefix}-${role.toLowerCase()}-csv.json`,JSON.stringify({
    status:'COMPROBADO',role,rows:total,headers:rows[0],sha256:createHash('sha256').update(bytes).digest('hex'),
    utf8_bom:true,complete_filtered_scope:true,no_free_notes:true,actual_browser_download_response:true},null,2)+'\n');
}

for(const role of roles)test(`S5 ${role}: seguimiento, alcance y reportes reales`,async({page,context})=>{
  test.skip(phase!=='followup');test.setTimeout(180000);
  await login(page,role);
  if(role==='RESEARCHER') {
    for(const route of ['/alertas','/reportes',`/alertas/${missing}`]) {
      await page.goto(path(route));await expect(page.getByRole('heading',{name:'Acceso no disponible',exact:true})).toBeVisible();
    }
    for(const route of ['/alerts','/reports/summary','/reports/export.csv']) {
      const response=await page.request.get(`/api/v1${route}?period_id=${study.period_id}`);
      expect(response.status()).toBe(403);samples.push({schema:'Error',body:await response.json()});
    }
    expect((await page.request.get(`/api/v1/alerts/${missing}`)).status()).toBe(403);
    await capture(page,'researcher-restricted');
  } else {
    if(role==='ADMIN'&&scope==='isolated') {
      await navigate(page,'Modelos');await page.getByRole('link',{name:study.model.name,exact:true}).click();
      await page.getByRole('radio',{name:'Instante actual',exact:true}).check();
      const firstEvaluationButton=page.getByRole('button',{name:'Evaluar ahora',exact:true});
      await expect(firstEvaluationButton).toBeEnabled();
      const firstInference=page.waitForResponse(r=>r.url().endsWith('/api/v1/predictions/run'));
      await firstEvaluationButton.focus();await page.keyboard.press('Enter');
      const created=await firstInference;await record('PredictionRunResult',created);
      const firstRun=await created.json();expect(firstRun.selected).toBe(60);expect(firstRun.created).toBe(55);
      expect(firstRun.reused).toBe(0);expect(firstRun.abstentions).toHaveLength(5);
      expect(firstRun.followup.created).toBeGreaterThan(0);expect(firstRun.followup.skipped_missing).toBe(5);
      await expect(page.getByRole('heading',{name:'Evaluación completada',exact:true})).toBeVisible();
      await capture(page,'first-ui-inference-followup-created');
    }
    await navigate(page,'Alertas');await expect(page.getByRole('heading',{name:'Alertas',exact:true})).toBeVisible();
    if(role==='ADMIN') {
      const csrf=await token(page);
      expect((await page.request.post('/api/v1/alerts/sync',{data:{period_id:study.period_id}})).status()).toBe(403);
      const synchronizationButton=page.getByRole('button',{name:'Actualizar alertas',exact:true});
      await expect(synchronizationButton).toBeEnabled();
      const synchronization=page.waitForResponse(r=>r.url().endsWith('/api/v1/alerts/sync'));
      await synchronizationButton.focus();await page.keyboard.press('Enter');
      const first=await synchronization;await record('FollowupResult',first);
      await expect(page.getByRole('heading',{name:'Seguimiento sincronizado',exact:true})).toBeVisible();
      const repeated=await page.request.post('/api/v1/alerts/sync',{data:{period_id:study.period_id},headers:{'X-CSRF-Token':csrf}});
      await record('FollowupResult',repeated);expect((await repeated.json()).created).toBe(0);
      expect((await repeated.json()).reused).toBe(55);
      await capture(page,'admin-alerts');
      await navigate(page,'Modelos');await page.getByRole('link',{name:study.model.name,exact:true}).click();
      await page.getByRole('radio',{name:'Instante actual',exact:true}).check();
      const inferred=page.waitForResponse(r=>r.url().endsWith('/api/v1/predictions/run'));
      await page.getByRole('button',{name:'Evaluar ahora',exact:true}).click();
      const evaluated=await inferred;await record('PredictionRunResult',evaluated);
      const run=await evaluated.json();expect(run.created).toBe(0);expect(run.reused).toBe(55);
      expect(run.abstentions).toHaveLength(5);expect(run.followup.created).toBe(0);expect(run.followup.reused).toBe(55);
      await navigate(page,'Alertas');
    } else await expect(page.getByRole('button',{name:'Actualizar alertas',exact:true})).toHaveCount(0);
    const cases=await currentCases(page);expect(cases.length).toBeGreaterThan(0);
    if(role==='ADMIN')foreignCase=cases.find(item=>item.section_id===study.foreign_section.id);
    await page.getByLabel('Buscar código',{exact:true}).fill(cases[0].anon_code);
    const filtered=page.waitForResponse(r=>r.url().includes('/api/v1/alerts?')&&new URL(r.url()).searchParams.get('search')===cases[0].anon_code);
    await page.getByRole('button',{name:'Aplicar filtros',exact:true}).click();expect((await filtered).status()).toBe(200);
    await expect(page.locator('.followup-table tbody tr')).toHaveCount(1);
    await page.getByRole('button',{name:'Limpiar filtros',exact:true}).click();
    await expect(page.getByLabel('Buscar código',{exact:true})).toHaveValue('');
    await page.getByRole('link',{name:`Ver caso de ${cases[0].anon_code}`,exact:true}).first().click();
    await expect(page.getByRole('heading',{name:`Caso de ${cases[0].anon_code}`,exact:true})).toBeVisible();
    await page.reload();await expect(page.getByRole('heading',{name:'Motivo y fuente del caso',exact:true})).toBeVisible();
    if(role==='DIRECTOR') {
      await expect(page.getByRole('button',{name:'Guardar estado',exact:true})).toHaveCount(0);
      await expect(page.getByRole('button',{name:'Planificar actividad',exact:true})).toHaveCount(0);
      const denied=await page.request.patch(`/api/v1/alerts/${cases[0].id}`,{data:{expected_version:cases[0].version,status:'IN_REVIEW'},headers:{'X-CSRF-Token':await token(page)}});
      expect(denied.status()).toBe(403);samples.push({schema:'Error',body:await denied.json()});
      await capture(page,'director-case');
    }
    if(role==='TUTOR') {
      // Reanudar una revisión fallida reutiliza el mismo caso con los objetivos
      // identificables de prueba; nunca planifica otro par en una repetición.
      let selected:Detail|undefined;
      for(const candidate of cases) {
        const record=await detail(page,candidate.id);
        if(record.interventions.some(item=>[doneObjective,cancelledObjective].includes(item.objective))) {selected=record;break;}
      }
      selected??=await detail(page,cases.find(item=>['OPEN','IN_REVIEW'].includes(item.status))!.id);
      let caseRecord=selected.alert;
      await page.goto(path(`/alertas/${caseRecord.id}`));
      await expect(page.getByRole('heading',{name:`Caso de ${caseRecord.anon_code}`,exact:true})).toBeVisible();
      for(const [objective,status] of [[doneObjective,'DONE'],[cancelledObjective,'CANCELLED']] as const) {
        let activity=selected.interventions.find(item=>item.objective===objective);
        if(!activity) {
          await page.getByLabel('Objetivo',{exact:true}).fill(objective);
          await page.getByLabel('Fecha y hora programadas (Lima)',{exact:true}).fill('2027-01-05T14:00');
          await page.getByLabel('Notas opcionales',{exact:true}).fill('Actividad de simulación; no se contactó a personas.');
          if(status==='DONE')await capture(page,'tutor-plan-form');
          const created=page.waitForResponse(r=>r.url().endsWith('/api/v1/interventions')&&r.request().method()==='POST');
          await page.getByRole('button',{name:'Planificar actividad',exact:true}).click();
          const response=await created;expect(response.status()).toBe(201);samples.push({schema:'InterventionCreateResult',body:await response.json()});
          activity=(await response.json()).intervention;
          await expect(page.getByText(objective,{exact:true})).toBeVisible();
        }
        if(activity!.status==='PLANNED') {
          const item=page.locator('.followup-interventions > li').filter({has:page.getByText(objective,{exact:true})});
          await item.getByRole('button',{name:'Registrar actividad',exact:true}).click();
          await item.getByLabel('Estado de actividad',{exact:true}).selectOption(status);
          if(status==='DONE') {
            const clock=await page.request.get('/api/v1/auth/csrf');
            const server=Date.parse(clock.headers()['date']);expect(Number.isFinite(server)).toBe(true);
            await item.getByLabel('Fecha y hora efectiva (Lima)',{exact:true}).fill(new Date(server-5*3600000-60000).toISOString().slice(0,16));
            await item.getByLabel('Notas o evidencia de la actividad',{exact:true}).fill('Realización exclusivamente simulada y verificable en esta prueba.');
            await capture(page,'tutor-done-form');
          }
          const updated=page.waitForResponse(r=>r.url().endsWith(`/api/v1/interventions/${activity!.id}`)&&r.request().method()==='PATCH');
          await item.getByRole('button',{name:'Guardar actividad',exact:true}).click();
          const response=await updated;await record('InterventionView',response);
          const output=await response.json();expect(output.status).toBe(status);
          expect(output.performed_at===null).toBe(status==='CANCELLED');
          if(status==='DONE')expect(output.performed_at).not.toBe(output.scheduled_at);
          await item.getByRole('button',{name:'Cerrar formulario',exact:true}).click();
        }
        selected=await detail(page,caseRecord.id);
      }
      if(['OPEN','IN_REVIEW'].includes(selected.alert.status)) {
        await page.getByLabel('Estado del caso',{exact:true}).selectOption('RESOLVED');
        const reason='Seguimiento concluido exclusivamente en simulación S5; no implica mejoría académica.';
        await page.getByLabel('Motivo de cierre',{exact:true}).fill(reason);
        if(selected.alert.status==='OPEN') {
          // Conflicto efectivo de PostgreSQL, sin respuesta 409 inventada.
          const changed=await page.request.patch(`/api/v1/alerts/${caseRecord.id}`,{data:{expected_version:selected.alert.version,status:'IN_REVIEW'},headers:{'X-CSRF-Token':await token(page)}});
          expect(changed.status()).toBe(200);
          const stale=page.waitForResponse(r=>r.url().endsWith(`/api/v1/alerts/${caseRecord.id}`)&&r.request().method()==='PATCH');
          await page.getByRole('button',{name:'Guardar estado',exact:true}).click();
          const rejected=await stale;expect(rejected.status()).toBe(409);samples.push({schema:'Error',body:await rejected.json()});
          await expect(page.getByLabel('Motivo de cierre',{exact:true})).toHaveValue(reason);
          await expect(page.getByRole('button',{name:'Guardar estado',exact:true})).toBeDisabled();
          await capture(page,'tutor-real-version-conflict');
          await page.getByRole('button',{name:'Revisar cambios del caso',exact:true}).click();
          await page.getByLabel('He revisado el recurso actualizado',{exact:true}).check();
        }
        const closed=page.waitForResponse(r=>r.url().endsWith(`/api/v1/alerts/${caseRecord.id}`)&&r.request().method()==='PATCH');
        await page.getByRole('button',{name:'Guardar estado',exact:true}).click();
        const response=await closed;await record('AlertDetail',response);expect((await response.json()).alert.status).toBe('RESOLVED');
      }
      const completed=await detail(page,caseRecord.id);
      expect(completed.interventions.filter(item=>[doneObjective,cancelledObjective].includes(item.objective))).toHaveLength(2);
      expect(completed.interventions.find(item=>item.objective===doneObjective)?.status).toBe('DONE');
      expect(completed.interventions.find(item=>item.objective===cancelledObjective)?.status).toBe('CANCELLED');
      expect(completed.alert.status).toBe('RESOLVED');
      await capture(page,'tutor-case-completed');
      const foreignList=await page.request.get(`/api/v1/alerts?period_id=${study.period_id}&section_id=${study.foreign_section.id}`);
      expect(foreignList.status()).toBe(404);
      const nonexistent=await page.request.get(`/api/v1/alerts/${missing}`);expect(nonexistent.status()).toBe(404);
      expect(foreignCase).toBeDefined();
      const inaccessible=await page.request.get(`/api/v1/alerts/${foreignCase!.id}`);expect(inaccessible.status()).toBe(404);
      const {request_id:_missingId,...missingError}=await nonexistent.json();
      const {request_id:_foreignId,...foreignError}=await inaccessible.json();expect(foreignError).toEqual(missingError);
      expect((await page.request.patch(`/api/v1/alerts/${foreignCase!.id}`,{data:{expected_version:foreignCase!.version,status:'IN_REVIEW'},headers:{'X-CSRF-Token':await token(page)}})).status()).toBe(404);
      const foreignRead=page.waitForResponse(r=>r.url().endsWith(`/api/v1/alerts/${foreignCase!.id}`)&&r.request().method()==='GET');
      await page.goto(path(`/alertas/${foreignCase!.id}`));
      const foreignResponse=await foreignRead;expect(foreignResponse.status()).toBe(404);
      samples.push({schema:'Error',body:await foreignResponse.json()});
      await expect(page.getByRole('heading',{name:'Este caso no está disponible',exact:true})).toBeVisible();
      await expect(page.getByText(foreignCase!.anon_code,{exact:true})).toHaveCount(0);
      await capture(page,'tutor-foreign-safe404');
      await page.goto(path(`/estudiantes/${caseRecord.student_id}`));
      await expect(page.getByRole('heading',{name:'Historial',exact:true})).toBeVisible();
      const timeline=await page.request.get(`/api/v1/students/${caseRecord.student_id}/timeline?period_id=${study.period_id}&page_size=100`);
      await record('TimelineEventPage',timeline);const history=(await timeline.json()).items;
      expect(history.some((event:{summary:string})=>event.summary.includes('realizada'))).toBe(true);
      expect(history.some((event:{summary:string})=>event.summary.includes('cancelada'))).toBe(true);
      expect(history.filter((event:{summary:string;entity_id:string})=>event.summary==='Apertura de alerta'&&event.entity_id===caseRecord.id)).toHaveLength(1);
      await capture(page,'tutor-student-followup');
    }
    await navigate(page,'Reportes');await expect(page.getByRole('heading',{name:'Reportes',exact:true})).toBeVisible();
    const summary=await page.request.get(`/api/v1/reports/summary?period_id=${study.period_id}&page_size=5`);await record('ReportSummary',summary);
    const report=await summary.json();expect(report.total).toBe(role==='TUTOR'?study.student_count/2:study.student_count);
    expect(report.total).toBe(report.evaluations.evaluated+report.evaluations.not_evaluated+report.evaluations.insufficient_data);
    expect(report.evaluations.evaluated).toBe(report.risks.low.count+report.risks.medium.count+report.risks.high.count);
    expect(report.items).toHaveLength(5);expect(report.risks.low.denominator).toBe(report.evaluations.evaluated);
    if(role==='TUTOR') {expect(report.interventions.done).toBeGreaterThanOrEqual(1);expect(report.interventions.cancelled).toBeGreaterThanOrEqual(1);}
    await expect(page.getByRole('button',{name:'Descargar CSV',exact:true})).toBeEnabled();
    await capture(page,`${role.toLowerCase()}-reports`);await download(page,report.total,role);
    await page.getByLabel('Buscar código',{exact:true}).fill('NO-RESULT-S5');await page.getByRole('button',{name:'Aplicar filtros',exact:true}).click();
    await expect(page.getByRole('heading',{name:'No hay matrículas con estos filtros',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Limpiar filtros',exact:true}).first().click();
    await expect(page.locator('.report-rows-table tbody tr')).toHaveCount(20);
    await page.reload();await expect(page.getByRole('heading',{name:'Reportes',exact:true})).toBeVisible();
    await navigate(page,'Alertas');await page.goBack();await expect(page.getByRole('heading',{name:'Reportes',exact:true})).toBeVisible();
    await page.goForward();await expect(page.getByRole('heading',{name:'Alertas',exact:true})).toBeVisible();
    // Recarga real en Inicio: verifica su resumen propio, sin depender de una
    // respuesta anterior en la caché del resumen completo de Reportes.
    await navigate(page,'Inicio');
    const compactResponse=page.waitForResponse(r=>r.url().includes('/api/v1/reports/summary?')&&new URL(r.url()).searchParams.get('page_size')==='1');
    await page.reload();const compact=await compactResponse;await record('ReportSummary',compact);
    const homeReport=await compact.json();expect(homeReport.total).toBe(role==='TUTOR'?study.student_count/2:study.student_count);
    expect(homeReport.items).toHaveLength(1);
    const home=page.locator('.report-summary');
    await expect(home.getByRole('heading',{name:'Resumen del seguimiento',exact:true})).toBeVisible();
    await expect(home.locator('.badge')).toHaveText(`${homeReport.total} matrículas`);
    await expect(home.getByText('Matrículas con caso activo',{exact:true})).toBeVisible();
    await expect(home.getByText('Actividades realizadas',{exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Ver alertas →',exact:true})).toBeEnabled();
    await expect(page.getByRole('button',{name:'Ver reportes →',exact:true})).toBeEnabled();
    await capture(page,`${role.toLowerCase()}-home-followup`);
  }
  expect(await page.evaluate(()=>[localStorage.length,sessionStorage.length])).toEqual([0,0]);
  const cookie=(await context.cookies()).find(value=>value.name==='session')!;expect(cookie.httpOnly).toBe(true);
  await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();
  await expect(page.getByText('Sesión cerrada correctamente.',{exact:true})).toBeVisible();
  await context.addCookies([cookie]);expect((await page.request.get(`/api/v1/alerts?period_id=${study.period_id}`)).status()).toBe(401);
  expect((await page.request.get(`/api/v1/reports/export.csv?period_id=${study.period_id}`)).status()).toBe(401);
});

test('S5 aislado: fallos HTTP identificados y descarte tardío entre sesiones',async({page})=>{
  test.skip(phase!=='followup'||scope!=='isolated');test.setTimeout(150000);
  await login(page,'ADMIN');
  const open=(await currentCases(page)).find(item=>item.status==='OPEN'&&item.section_id===study.foreign_section.id)!;
  await page.goto(path(`/alertas/${open.id}`));
  await page.getByLabel('Objetivo',{exact:true}).fill('S5 aislado: planificación con respuesta incierta');
  await page.getByLabel('Fecha y hora programadas (Lima)',{exact:true}).fill('2027-01-06T12:00');
  test.info().annotations.push({type:'response-body-loss-simulation',description:'POST intervención real 201; únicamente se trunca el cuerpo para verificar conservación de creation_key y reutilización 200.'});
  let originalPayload:unknown;let originalId='';let calls=0;
  await page.route('**/api/v1/interventions',async route=>{
    if(route.request().method()!=='POST'){await route.continue();return;}
    calls++;originalPayload=route.request().postDataJSON();
    const actual=await route.fetch();expect(actual.status()).toBe(201);originalId=(await actual.json()).intervention.id;
    await route.fulfill({status:201,contentType:'application/json',body:'{"intervention":'});
  });
  const uncertain=page.waitForResponse(r=>r.url().endsWith('/api/v1/interventions')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Planificar actividad',exact:true}).click();expect((await uncertain).status()).toBe(201);
  await expect(page.getByRole('button',{name:'Repetir el mismo intento de planificación',exact:true})).toBeVisible();
  expect(calls).toBe(1);await page.unroute('**/api/v1/interventions');
  const reused=page.waitForResponse(r=>r.url().endsWith('/api/v1/interventions')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Repetir el mismo intento de planificación',exact:true}).click();
  const recovered=await reused;expect(recovered.status()).toBe(200);
  expect(recovered.request().postDataJSON()).toEqual(originalPayload);
  const recoveredBody=await recovered.json();expect(recoveredBody.reused_result).toBe(true);expect(recoveredBody.intervention.id).toBe(originalId);
  samples.push({schema:'InterventionCreateResult',body:recoveredBody});
  await expect(page.getByText('La actividad ya estaba registrada. Se reutilizó el mismo intento sin duplicarla.',{exact:true})).toBeVisible();
  await capture(page,'simulated-body-loss-reused-creation');
  await navigate(page,'Reportes');
  await expect(page.getByRole('button',{name:'Descargar CSV',exact:true})).toBeEnabled();
  test.info().annotations.push({type:'http-simulation',description:'Únicamente 503 de exportación está simulado; no acredita caída real de PostgreSQL.'});
  let downloads=0;page.on('download',()=>downloads++);
  await page.route('**/api/v1/reports/export.csv?*',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'SERVICE_UNAVAILABLE',message:'Temporalmente no disponible.',details:[],request_id:missing})}));
  const failure=page.waitForResponse(r=>r.url().includes('/api/v1/reports/export.csv'));
  await page.getByRole('button',{name:'Descargar CSV',exact:true}).click();expect((await failure).status()).toBe(503);
  await expect(page.getByRole('alert')).toContainText('El servicio no está disponible temporalmente.');
  expect(downloads).toBe(0);await capture(page,'simulated-csv503-no-download');
  await page.unroute('**/api/v1/reports/export.csv?*');
  // GET real de ADMIN de una sección ajena a TUTOR, retenido hasta cambiar sesión.
  let release!:()=>void,received!:()=>void,finished!:()=>void;
  const gate=new Promise<void>(resolve=>release=resolve),captured=new Promise<void>(resolve=>received=resolve),complete=new Promise<void>(resolve=>finished=resolve);
  await page.route('**/api/v1/reports/summary?*',async route=>{
    if(new URL(route.request().url()).searchParams.get('section_id')!==study.foreign_section.id) {await route.continue();return;}
    try {const actual=await route.fetch();expect(actual.status()).toBe(200);received();await gate;try{await route.fulfill({response:actual});}catch{/* Cancelada por logout. */}}
    finally{finished();}
  });
  await page.getByLabel('Sección autorizada',{exact:true}).selectOption(study.foreign_section.id);await captured;
  await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Iniciar sesión',exact:true})).toBeVisible();
  await page.getByLabel('Correo electrónico').fill(accounts.TUTOR.email);await page.getByLabel('Contraseña',{exact:true}).fill(accounts.TUTOR.password);
  await page.getByRole('button',{name:'Iniciar sesión',exact:true}).click();
  await expect(page.locator('.user-summary').getByText('Tutor',{exact:true})).toBeVisible();
  release();await complete;await page.unroute('**/api/v1/reports/summary?*');
  await navigate(page,'Reportes');await expect(page.locator('.report-rows-table tbody tr')).toHaveCount(20);
  await expect(page.getByText(study.foreign_student.anon_code,{exact:true})).toHaveCount(0);
  const authorized=await page.request.get(`/api/v1/reports/summary?period_id=${study.period_id}&page_size=100`);
  expect((await authorized.json()).items.every((row:{section_id:string})=>row.section_id===study.own_section.id)).toBe(true);
  await capture(page,'late-admin-response-discarded');
  await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();
});
