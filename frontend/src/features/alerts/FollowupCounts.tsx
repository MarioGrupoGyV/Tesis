import type { FollowupResult } from '../../lib/api';
import { numberLabel } from '../../lib/format';
export function FollowupCounts({ result }: { result: FollowupResult }) {
  return <div className="followup-results" role="status"><h3>Seguimiento sincronizado</h3><dl><div><dt>Casos nuevos</dt><dd>{numberLabel(result.created)}</dd></div><div><dt>Fuentes actualizadas</dt><dd>{numberLabel(result.updated)}</dd></div><div><dt>Señales bajas con caso</dt><dd>{numberLabel(result.retained_low)}</dd></div><div><dt>Sin nueva alerta</dt><dd>{numberLabel(result.no_alert)}</dd></div><div><dt>Decisiones reutilizadas</dt><dd>{numberLabel(result.reused)}</dd></div><div><dt>Omitidas por antigüedad</dt><dd>{numberLabel(result.ignored_stale)}</dd></div><div><dt>Sin evaluación actual</dt><dd>{numberLabel(result.skipped_missing)}</dd></div></dl><p>Se conserva un solo caso activo por matrícula. Una señal baja no concluye un caso automáticamente; las abstenciones no generan riesgo ni alertas.</p></div>;
}
