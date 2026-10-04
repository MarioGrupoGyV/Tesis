import type { ReportSummary } from '../../lib/api';
import { numberLabel, timestampLabel } from '../../lib/format';

export function ReportSummaryView({ report, compact = false }: { report: ReportSummary; compact?: boolean }) {
  const rows = [
    { unit: 'Matrículas', label: 'Total autorizado filtrado', count: numberLabel(report.total), context: 'Denominador del contexto' },
    { unit: 'Matrículas', label: 'Evaluadas', count: numberLabel(report.evaluations.evaluated), context: `De ${numberLabel(report.total)} matrículas` },
    { unit: 'Matrículas', label: 'Sin evaluar', count: numberLabel(report.evaluations.not_evaluated), context: `De ${numberLabel(report.total)} matrículas` },
    { unit: 'Matrículas', label: 'Datos insuficientes', count: numberLabel(report.evaluations.insufficient_data), context: `De ${numberLabel(report.total)} matrículas` },
    ...(['low', 'medium', 'high'] as const).map((key, index) => { const metric = report.risks[key]; return { unit: 'Matrículas evaluadas', label: `Riesgo ${['bajo', 'medio', 'alto'][index]}`, count: numberLabel(metric.count), context: metric.percentage === null ? 'No estimable: no hay matrículas evaluadas' : `${numberLabel(metric.percentage, ' %')} · ${metric.count} de ${metric.denominator} evaluadas` }; }),
    { unit: 'Matrículas', label: 'Con caso activo', count: numberLabel(report.cases.active_enrollments), context: `De ${numberLabel(report.total)} matrículas` },
    { unit: 'Casos', label: 'Abiertos / en revisión', count: `${numberLabel(report.cases.open)} / ${numberLabel(report.cases.in_review)}`, context: 'Conteo de casos' },
    { unit: 'Casos', label: 'Concluidos / descartados', count: `${numberLabel(report.cases.resolved)} / ${numberLabel(report.cases.dismissed)}`, context: 'Conteo de casos históricos' },
    { unit: 'Actividades', label: 'Planificadas', count: numberLabel(report.interventions.planned), context: 'No cuentan como realizadas' },
    { unit: 'Actividades', label: 'Realizadas', count: numberLabel(report.interventions.done), context: 'Estado DONE con fecha efectiva' },
    { unit: 'Actividades', label: 'Canceladas', count: numberLabel(report.interventions.cancelled), context: 'No cuentan como realizadas' },
  ];
  return <section className="panel report-summary" aria-labelledby="report-summary-title"><div className="report-summary-heading"><div><p className="eyebrow">ESTADO ACTUAL AUTORIZADO</p><h2 id="report-summary-title">{compact ? 'Resumen del seguimiento' : 'Resumen operativo'}</h2></div><span className="badge">{report.total} matrículas</span></div><p className="muted">Periodo {report.period_code} · {report.section_id ? 'Sección seleccionada' : `${report.authorized_section_ids.length} secciones autorizadas`} · Actualizado {timestampLabel(report.generated_at)}</p>
    {compact ? <dl className="report-compact-counts"><div><dt>Evaluadas</dt><dd>{numberLabel(report.evaluations.evaluated)} <small>de {numberLabel(report.total)}</small></dd></div><div><dt>Sin evaluar</dt><dd>{numberLabel(report.evaluations.not_evaluated)}</dd></div><div><dt>Datos insuficientes</dt><dd>{numberLabel(report.evaluations.insufficient_data)}</dd></div><div><dt>Matrículas con caso activo</dt><dd>{numberLabel(report.cases.active_enrollments)}</dd></div><div><dt>Actividades planificadas</dt><dd>{numberLabel(report.interventions.planned)}</dd></div><div><dt>Actividades realizadas</dt><dd>{numberLabel(report.interventions.done)}</dd></div></dl> : <>
      <p className="report-scroll-help muted">↔ Desplaza la tabla para consultar las unidades y los denominadores.</p>
      <div className="table-container report-summary-table" tabIndex={0} role="region" aria-label="Tabla de indicadores operativos; desplazamiento horizontal disponible"><table><caption>Indicadores del conjunto filtrado</caption><colgroup><col className="report-state-column" /><col className="report-count-column" /><col className="report-unit-column" /><col /></colgroup><thead><tr><th scope="col">Estado</th><th scope="col">Cantidad</th><th scope="col">Unidad</th><th scope="col">Porcentaje / denominador</th></tr></thead><tbody>{rows.map(row => <tr key={`${row.unit}:${row.label}`}><th scope="row">{row.label}</th><td>{row.count}</td><td>{row.unit}</td><td>{row.context}</td></tr>)}</tbody></table></div>
      <p className="muted report-note">Últimos cortes del conjunto: {report.cutoff_min && report.cutoff_max ? `${timestampLabel(report.cutoff_min)} — ${timestampLabel(report.cutoff_max)}` : 'Sin cortes disponibles'}. Los cortes pertenecen al calendario sintético; las acciones de seguimiento tienen su fecha operativa propia.</p>
    </>}
    <p className="muted report-note">Cada matrícula se cuenta una vez: total = evaluadas + sin evaluar + datos insuficientes. Solo las evaluadas se distribuyen en bajo, medio y alto. Los conteos de seguimiento describen simulación, sin afirmar eficacia escolar.</p>
  </section>;
}
