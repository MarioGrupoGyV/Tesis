import type { FullResult, Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import { writeFileSync } from 'node:fs';
export default class ReviewReporter implements Reporter {
  private cases: object[]=[];
  onTestEnd(test:TestCase,result:TestResult) {
    // No exportar argumentos, logs, cuerpos HTTP, trazas ni detalles de excepciones.
    const entry={title:test.title,status:result.status,duration_ms:result.duration,
      failure:result.status==='passed'?null:'Comprobar criterio y captura de esta prueba'};
    this.cases.push(entry);
    console.log(`${result.status}: ${test.title}`);
  }
  onEnd(result:FullResult) {
    writeFileSync(process.env.E2E_REPORT_FILE ?? 'tests/evidence/s2-2-isolated-playwright.json',
      JSON.stringify({status:result.status,scope:process.env.E2E_SCOPE,cases:this.cases},null,2)+'\n');
  }
}
