import type { FullResult, Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import { writeFileSync } from 'node:fs';
export default class ReviewReporter implements Reporter {
  private cases: object[]=[];
  onTestEnd(test:TestCase,result:TestResult) {
    // No exportar argumentos, logs, cuerpos HTTP, trazas ni detalles de excepciones.
    const diagnostics=test.annotations.filter(annotation=>annotation.type==='inference-http-diagnostic').flatMap(annotation=>{
      try {
        const value=JSON.parse(annotation.description??'') as Record<string,unknown>;
        if(!['deferred-post','body-loss-post'].includes(String(value.stage))||typeof value.status!=='number'||!Number.isInteger(value.status)||value.status<100||value.status>599) return [];
        return [{stage:value.stage,status:value.status,
          code:typeof value.code==='string'&&/^[A-Z0-9_]{1,80}$/.test(value.code)?value.code:null,
          request_id:typeof value.request_id==='string'&&/^[0-9a-f-]{36}$/i.test(value.request_id)?value.request_id:null}];
      } catch { return []; }
    });
    const entry={title:test.title,status:result.status,duration_ms:result.duration,
      has_simulated_http_503:test.annotations.some(annotation=>annotation.type==='http-simulation'),
      has_simulated_processing_status_503:test.annotations.some(annotation=>annotation.type==='processing-status-simulation'),
      has_simulated_preview_stale_409:test.annotations.some(annotation=>annotation.type==='preview-stale-simulation'),
      has_simulated_response_body_loss:test.annotations.some(annotation=>annotation.type==='response-body-loss-simulation'),
      has_simulated_host_clock:test.annotations.some(annotation=>annotation.type==='host-clock-simulation'),
      real_intercepted_inference_diagnostics:diagnostics,
      failure:result.status==='passed'?null:'Comprobar criterio y captura de esta prueba'};
    this.cases.push(entry);
    console.log(`${result.status}: ${test.title}`);
  }
  onEnd(result:FullResult) {
    if(this.cases.length===0) return; // --list no acredita ejecución de navegador.
    writeFileSync(process.env.E2E_REPORT_FILE ?? 'tests/evidence/s4-isolated-playwright.json',
      JSON.stringify({status:result.status,scope:process.env.E2E_SCOPE,cases:this.cases},null,2)+'\n');
  }
}
