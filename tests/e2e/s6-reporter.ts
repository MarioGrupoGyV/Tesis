import type { TestCase, TestResult } from '@playwright/test/reporter';
import { writeFileSync } from 'node:fs';
import ReviewReporter from './review-reporter';

// Conserva el reporte histórico. Solo S6 añade ubicaciones de fallo, sin
// argumentos, mensajes de excepción, valores de formulario ni cuerpos HTTP.
export default class S6Reporter extends ReviewReporter {
  private failures: { test: string; locations: { line: number; column: number }[] }[] = [];
  onTestEnd(test: TestCase, result: TestResult) {
    super.onTestEnd(test, result);
    if (result.status === 'passed') return;
    const locations = (result.errors ?? []).flatMap(error => [...(error.stack ?? '').matchAll(/s6\.spec\.ts:(\d+):(\d+)/g)]
      .map(match => ({ line: Number(match[1]), column: Number(match[2]) })));
    this.failures.push({ test: test.title, locations });
    const prefix = process.env.E2E_EVIDENCE_PREFIX ?? '';
    if (/^s6[a-z0-9-]+$/.test(prefix)) writeFileSync(`tests/evidence/${prefix}-failure-locations.json`, JSON.stringify(this.failures, null, 2) + '\n');
    console.log(`S6: ubicaciones sanitizadas ${JSON.stringify(locations)}`);
  }
}
