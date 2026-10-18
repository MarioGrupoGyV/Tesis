import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type IndicatorRatio, type IndicatorSummary, type IndicatorsResponse, type User, type ValidatedDetection } from '../../lib/api';
import { EmptyState, ErrorState, LoadingState, PageHeader } from '../../components/ui';
import { numberLabel, timestampLabel } from '../../lib/format';
import { RETROSPECTIVE_LABEL } from '../../lib/origin';
import './features.css';

const reasons: Record<string, string> = {
  REFERENCE_NOT_AVAILABLE: 'Sin riesgo de referencia almacenado: no se calcula.', NO_REFERENCE_MEDIUM_OR_HIGH: 'No hay estudiantes con referencia media o alta.',
  NO_ELIGIBLE_STUDENTS: 'No hay estudiantes elegibles.', NO_ALERTS: 'Todavía no hay alertas.', NO_RECEIVED_RECORDS: 'No se han recibido registros.',
  PERIOD_LEVEL_ONLY: 'Solo disponible para el periodo completo y con acceso a todas las secciones.', STUDY_INTEGRITY_ERROR: 'No se pudo verificar la procedencia del estudio.',
  STUDY_STORAGE_UNAVAILABLE: 'Almacenamiento del estudio no disponible.', NO_EVALUATED_STUDENTS_WITH_REFERENCE: 'Ningún estudiante evaluado tiene riesgo de referencia.', NO_DENOMINATOR: 'Sin denominador.', NO_INTERVENTIONS_LINKED_TO_ALERT: 'Todavía no hay intervenciones realizadas ligadas a una alerta.',
  RECEPTION_PROVENANCE_UNCONFIRMED: 'No se informa: la procedencia de la recepción real de registros no está confirmada.',
  NO_OUT_OF_SAMPLE_REPORT: 'El modelo activo no trae informe de validación cruzada: no hay métricas fuera de muestra.',
  NO_REAL_INTERVENTIONS: 'Todavía no hay intervenciones reales registradas: no se estima ni se rellena con ceros.' };
const riskName: Record<string, string> = { LOW: 'Bajo', MEDIUM: 'Medio', HIGH: 'Alto' };
const percent = (value: number | null | undefined) => value == null ? '—' : `${numberLabel(value)} %`;
const spreadLabel = (s: { mean: number | null; sd: number | null }) => s.mean == null ? 'Sin dato' : `${numberLabel(s.mean)} % ± ${s.sd == null ? '—' : numberLabel(s.sd)} %`;
const ratioDetail = (r: IndicatorRatio) => r.numerator == null || r.denominator == null ? 'Numerador y denominador no disponibles' : `${numberLabel(r.numerator)} de ${numberLabel(r.denominator)}`;

function Card({ title, value, detail, reason, formula, tag }: { title: string; value: string; detail: string; reason?: string | null; formula: string; tag: string }) {
  return <article className="indicator-card" aria-label={title}><h3>{title}</h3><span className="indicator-sim">{tag}</span><p className="big">{value}</p><p className="frac">{detail}</p>
    {reason && <p className="reason">{reasons[reason] ?? reason}</p>}<p className="muted student-list-note">{formula}</p></article>;
}

export function IndicatorsPage({ user, initialPeriodId }: { user: User; initialPeriodId: string }) {
  const contexts = useQuery({ queryKey: [user.id, user.role, 'indicator-contexts'], queryFn: ({ signal }) => api.indicatorContexts(signal), retry: false });
  const [periodId, setPeriodId] = useState(initialPeriodId);
  const [sectionId, setSectionId] = useState('');
  const [bimester, setBimester] = useState('');
  const [busy, setBusy] = useState(false);
  const [downloadError, setDownloadError] = useState<unknown>(null);
  const [notice, setNotice] = useState('');
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const list = contexts.data ?? [];
  const current = list.find(item => item.period_id === periodId) ?? list[0] ?? null;
  const activeSection = current?.sections.some(item => item.id === sectionId) ? sectionId : '';
  const activeBimester = current?.bimesters?.includes(bimester) ? bimester : '';
  const params = current ? { period_id: current.period_id, section_id: activeSection || undefined, bimester: activeBimester || undefined } : null;
  const data = useQuery({ queryKey: [user.id, user.role, 'indicators', params], queryFn: ({ signal }) => api.indicators(params!, signal), enabled: !!params, retry: false });
  async function download(kind: 'students' | 'interventions' = 'students') {
    if (!params || busy) return;
    setBusy(true); setDownloadError(null); setNotice('');
    try {
      const blob = kind === 'students' ? await api.exportIndicatorsCsv(params) : await api.exportInterventionsCsv(params);
      if (!alive.current) return;
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
      anchor.href = url; anchor.download = kind === 'students' ? 'seguimiento-escolar-indicadores.csv' : 'seguimiento-escolar-intervenciones.csv'; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 0);
      setNotice('Respuesta CSV recibida. Contiene códigos anónimos, sin nombres.');
    } catch (error) { if (alive.current) setDownloadError(error); } finally { if (alive.current) setBusy(false); }
  }
  const header = <PageHeader title="Indicadores" eyebrow="INDICADORES DE LA TESIS" description="PRV, CRA, PDER, NIA e intervención oportuna por periodo y sección, calculados con los datos del sistema."
    action={<div className="indicator-downloads"><button className="button primary" type="button" disabled={!params || busy || data.isPending || data.isError} aria-busy={busy} onClick={() => void download('students')}>{busy ? 'Obteniendo CSV…' : 'Descargar CSV'}</button><button className="button secondary" type="button" disabled={!params || busy || data.isPending || data.isError} onClick={() => void download('interventions')}>Descargar CSV por intervención</button></div>} />;
  if (contexts.isPending) return <div className="indicators-feature">{header}<LoadingState label="Cargando periodos autorizados…" /></div>;
  if (contexts.isError) return <div className="indicators-feature">{header}<ErrorState error={contexts.error} onRetry={() => void contexts.refetch()} /></div>;
  if (!current) return <div className="indicators-feature">{header}<EmptyState title="Todavía no hay indicadores"><p>No hay periodos con indicadores disponibles para tu cuenta. Un periodo real aparece cuando su protocolo está confirmado.</p></EmptyState></div>;
  return <div className="indicators-feature">{header}
    <section className="panel" aria-label="Filtros de indicadores"><div className="indicator-filters">
      <div><label htmlFor="ind-period">Periodo</label><select id="ind-period" value={current.period_id} onChange={event => { setPeriodId(event.target.value); setSectionId(''); setBimester(''); }}>{list.map(item => <option key={item.period_id} value={item.period_id}>{item.period_code} · {item.school_year} · {item.data_origin === 'REAL' ? 'datos reales locales' : 'sintético'}</option>)}</select></div>
      {current.bimesters && current.bimesters.length > 0 && <div><label htmlFor="ind-bimester">Bimestre</label><select id="ind-bimester" value={activeBimester} onChange={event => setBimester(event.target.value)}><option value="">Último corte disponible</option>{current.bimesters.map(code => <option key={code} value={code}>{code}</option>)}</select></div>}
      <div><label htmlFor="ind-section">Sección</label><select id="ind-section" value={activeSection} onChange={event => setSectionId(event.target.value)}><option value="">Todas las autorizadas</option>{current.sections.map(item => <option key={item.id} value={item.id}>{item.grade}.º · {item.code}</option>)}</select></div>
    </div></section>
    {notice && <p className="notice" role="status">{notice}</p>}{downloadError != null && <ErrorState error={downloadError} />}
    {data.isPending ? <LoadingState label="Calculando indicadores…" /> : data.isError ? <ErrorState error={data.error} onRetry={() => void data.refetch()} /> : <Results data={data.data} />}
  </div>;
}

function Results({ data }: { data: IndicatorsResponse }) {
  const t = data.total;
  const prv = data.prv;
  const real = data.data_origin === 'REAL';
  const tag = real ? 'Exploratorio local' : 'Simulación';
  return <>
    <p className="notice" role="status">{data.notice} Corte: {timestampLabel(data.as_of)}. Cierre considerado: {timestampLabel(data.close_at)}. Ventana de intervención oportuna: {data.opportune_window_days} días.{data.bimester ? ` Bimestre: ${data.bimester}.` : ''}</p>
    {real && data.retrospective_alerts > 0 && <p className="notice" role="status">{data.retrospective_alerts} alertas son {RETROSPECTIVE_LABEL}: el modelo las generó ahora sobre cortes pasados, no se emitieron en su momento. La detección se mide en la fecha simulada; la intervención oportuna usa el instante real de la alerta.</p>}
    <section className="indicator-cards" aria-label="Indicadores principales">
      <Card title="PRV · registros válidos procesados" tag={tag} value={percent(prv.percent)} detail={prv.received == null ? ratioDetail(prv) : `${numberLabel(prv.numerator)} de ${numberLabel(prv.received)} recibidos`} reason={prv.reason} formula="Válidos procesados ÷ registros recibidos × 100 (lotes CSV; los omitidos por inelegibilidad se informan aparte)." />
      <Card title="CRA · cobertura de reportes y alertas" tag={tag} value={percent(t.cra.percent)} detail={ratioDetail(t.cra)} reason={t.cra.reason} formula={`Elegibles evaluados con reporte (y alerta si el riesgo es medio o alto) ÷ elegibles × 100.${real ? ' Mide que el sistema no pierde casos de su propia salida (todo riesgo medio o alto genera alerta); la medida de calidad predictiva es la detección validada, más abajo.' : ''}`} />
      <Card title={real ? 'PDER del sistema · en muestra' : 'PDER · detección oportuna'} tag={real ? 'En muestra · dato de funcionamiento' : tag} value={percent(t.pder.percent)} detail={ratioDetail(t.pder)} reason={t.pder.reason} formula={`Con riesgo de referencia medio/alto y alerta antes del cierre ÷ con riesgo de referencia medio/alto × 100.${real ? ' El modelo se ajustó con estos mismos estudiantes, por eso suele dar 100 %: describe que el sistema funciona, no qué tan bien detecta. La cifra validada está en la tarjeta siguiente.' : ''}`} />
      <Card title="NIA · intervenciones realizadas por estudiante" tag={tag} value={t.nia.mean == null ? '—' : numberLabel(t.nia.mean)} detail={t.nia.total == null ? 'Sin intervenciones reales registradas' : `${numberLabel(t.nia.total)} realizadas · ${numberLabel(t.nia.students)} elegibles`} reason={t.nia.reason} formula={`Solo intervenciones realizadas; las planificadas no cuentan. Entre alertados: media ${t.nia.mean_alerted == null ? '—' : numberLabel(t.nia.mean_alerted)}.`} />
      <Card title="Intervención oportuna · por estudiante" tag={tag} value={percent(t.opportune.percent)} detail={ratioDetail(t.opportune)} reason={t.opportune.reason} formula={`Al menos una realizada en ≤ ${data.opportune_window_days} días de la alerta. Mediana alerta→primera: ${t.opportune.median_days_to_first == null ? '—' : numberLabel(t.opportune.median_days_to_first) + ' días'}. Insumo de la prueba por estudiante (McNemar).`} />
      <Card title="Intervención oportuna · por intervención" tag={tag} value={percent(t.opportune_by_intervention.percent)} detail={ratioDetail(t.opportune_by_intervention)} reason={t.opportune_by_intervention.reason} formula={`Intervenciones realizadas a ≤ ${data.opportune_window_days} días de la alerta de su caso ÷ realizadas ligadas a una alerta. Sin alerta ligada (aparte): ${numberLabel(t.opportune_by_intervention.without_alert)}. Comparable con la Tabla 6 de la tesis; la tarjeta anterior cuenta estudiantes, no intervenciones.`} />
    </section>
    {real && <DetectionPanel detection={t.validated_detection ?? null} reason={t.validated_detection_reason ?? null} bimester={data.bimester ?? null} />}
    {prv.received != null && <p className="muted report-note">PRV: recibidos {numberLabel(prv.received)}, válidos procesados {numberLabel(prv.valid_processed)}, rechazados {numberLabel(prv.rejected)}, válidos sin confirmar {numberLabel(prv.valid_not_committed)}, omitidos por inelegibilidad {numberLabel(prv.ineligible_omitted)}. Mediciones manuales aparte: {numberLabel(prv.manual_measurements)}.</p>}
    <section className="panel indicator-table" aria-labelledby="ind-sections-title"><h2 id="ind-sections-title">Por sección</h2>
      <div className="table-container" tabIndex={0} role="region" aria-label="Tabla de indicadores por sección; desplazamiento horizontal disponible"><table><caption>Indicadores por sección autorizada</caption>
        <thead><tr><th scope="col">Sección</th><th scope="col">Elegibles</th><th scope="col">CRA</th><th scope="col">PDER</th><th scope="col">NIA medio</th><th scope="col">Oportuna (estudiantes)</th><th scope="col">Oportuna (intervenciones)</th></tr></thead>
        <tbody>{data.sections.map(row => <SectionRow key={row.section_id ?? 'total'} row={row} />)}</tbody></table></div></section>
    <section className="panel" aria-labelledby="ind-model-title"><h2 id="ind-model-title">Métricas del modelo frente al riesgo de referencia</h2>
      {t.model_metrics ? <Metrics metrics={t.model_metrics} basis={t.metric_label ?? null} /> : <p className="muted">No estimables: {reasons[t.model_metrics_reason ?? ''] ?? t.model_metrics_reason ?? 'sin datos'}</p>}</section>
    <section className="panel" aria-labelledby="ind-performance-title"><h2 id="ind-performance-title">Rendimiento (último corte de cada estudiante elegible)</h2>
      <div className="table-container" tabIndex={0} role="region" aria-label="Estadísticos descriptivos"><table><caption>Estadísticos descriptivos</caption><thead><tr><th scope="col">Variable</th><th scope="col">n</th><th scope="col">Media</th><th scope="col">DE</th><th scope="col">Mediana</th><th scope="col">Mín.</th><th scope="col">Máx.</th></tr></thead>
        <tbody>{([['Promedio', t.performance.average_grade], ['Asistencia %', t.performance.attendance_pct]] as const).map(([name, d]) => <tr key={name}><th scope="row">{name}</th><td>{d.n}</td><td>{numberLabel(d.mean)}</td><td>{numberLabel(d.sd)}</td><td>{numberLabel(d.median)}</td><td>{numberLabel(d.minimum)}</td><td>{numberLabel(d.maximum)}</td></tr>)}</tbody></table></div></section>
    <p className="muted report-note">Excluidos: {numberLabel(t.exclusions.ineligible)} no elegibles; {numberLabel(t.exclusions.no_snapshot)} sin medición; {numberLabel(t.exclusions.no_reference)} sin riesgo de referencia{t.exclusions.reference_reason ? ` (${reasons[t.exclusions.reference_reason] ?? t.exclusions.reference_reason})` : ''}. Un estudiante sin riesgo de referencia no entra al denominador de PDER ni a las métricas. {real ? 'Datos reales locales: análisis exploratorio que no demuestra eficacia escolar.' : 'Los indicadores de este periodo son una simulación y no corresponden a resultados del colegio.'}</p>
  </>;
}

function DetectionPanel({ detection, reason, bimester }: { detection: ValidatedDetection | null; reason: string | null; bimester: string | null }) {
  const scope = bimester ? `bimestre ${bimester}` : 'todos los bimestres';
  return <section className="panel detection-panel" aria-labelledby="ind-detection-title"><h2 id="ind-detection-title">Detección validada (fuera de muestra)</h2>
    {!detection ? <p className="muted">No disponible: {reasons[reason ?? ''] ?? reason ?? 'sin datos'}</p> : <>
      <p className="muted"><strong>{detection.metric_label}. </strong>Qué proporción de los estudiantes con riesgo de referencia medio o alto habría detectado el modelo si no lo hubiera visto: {scope}.</p>
      <p className="big detection-big" aria-label="Detección validada">{spreadLabel(detection.detection)}</p>
      <p className="frac">Media ± desviación entre {detection.repetitions} repeticiones de validación cruzada. {numberLabel(detection.pooled.detected)} de {numberLabel(detection.pooled.reference_at_risk)} observaciones medias o altas marcadas como medias o altas (suma de las repeticiones; {numberLabel(detection.reference_at_risk_per_repetition)} por repetición).</p>
      <div className="table-container" tabIndex={0} role="region" aria-label="Detalle de la detección validada"><table><caption>Detalle por clase de referencia ({scope})</caption>
        <thead><tr><th scope="col">Qué se mide</th><th scope="col">Media ± desviación</th></tr></thead>
        <tbody><tr><th scope="row">Medio detectado como Medio o Alto</th><td>{spreadLabel(detection.medium_detected)}</td></tr>
          <tr><th scope="row">Alto detectado como Medio o Alto</th><td>{spreadLabel(detection.high_detected)}</td></tr>
          <tr><th scope="row">Alto confundido como Bajo (caso perdido)</th><td>{spreadLabel(detection.high_as_low)}</td></tr>
          <tr><th scope="row">Bajo marcado como Medio o Alto (falsa alarma)</th><td>{spreadLabel(detection.low_flagged)}</td></tr></tbody></table></div>
      <p className="notice" role="status">Con n pequeño (60 estudiantes; las observaciones de un mismo estudiante no son independientes) la incertidumbre es alta. La desviación entre repeticiones no es un intervalo de confianza ni sustituye una validación externa. {detection.note}</p></>}
  </section>;
}

function SectionRow({ row }: { row: IndicatorSummary }) {
  return <tr><th scope="row">{row.grade}.º · {row.section_code}</th><td>{numberLabel(row.eligible_students)}</td><td>{percent(row.cra.percent)} <small>({ratioDetail(row.cra)})</small></td><td>{percent(row.pder.percent)} <small>({row.pder.reason ? reasons[row.pder.reason] ?? row.pder.reason : ratioDetail(row.pder)})</small></td><td>{row.nia.mean == null ? '—' : numberLabel(row.nia.mean)}</td><td>{percent(row.opportune.percent)} <small>({ratioDetail(row.opportune)})</small></td><td>{percent(row.opportune_by_intervention.percent)} <small>({ratioDetail(row.opportune_by_intervention)})</small></td></tr>;
}

function Metrics({ metrics, basis }: { metrics: NonNullable<IndicatorSummary['model_metrics']>; basis: string | null }) {
  const cv = metrics.repetitions != null;
  return <><p className="muted">{basis && <strong>{basis}. </strong>}{cv ? `Media de ${metrics.repetitions} repeticiones de validación cruzada agrupada por estudiante (F1 macro: DE ${numberLabel(metrics.macro_sd?.f1 ?? null)}). La matriz suma todas las repeticiones.` : `n = ${metrics.n} estudiantes evaluados con riesgo de referencia.`} Exactitud: {percent(metrics.accuracy == null ? null : metrics.accuracy * 100)}.</p>
    <div className="table-container indicator-matrix" tabIndex={0} role="region" aria-label="Matriz de confusión"><table><caption>Matriz de confusión: filas = referencia, columnas = predicho</caption>
      <thead><tr><th scope="col">Referencia \ Predicho</th>{metrics.class_order.map(name => <th key={name} scope="col">{riskName[name]}</th>)}</tr></thead>
      <tbody>{metrics.confusion_matrix.map((cells, index) => <tr key={index}><th scope="row">{riskName[metrics.class_order[index]]}</th>{cells.map((value, column) => <td key={column}>{value}</td>)}</tr>)}</tbody></table></div>
    <div className="table-container" tabIndex={0} role="region" aria-label="Métricas por clase"><table><caption>Precisión, sensibilidad y F1 por clase</caption><thead><tr><th scope="col">Clase</th><th scope="col">Soporte</th><th scope="col">Precisión</th><th scope="col">Sensibilidad</th><th scope="col">F1</th></tr></thead>
      <tbody>{metrics.class_order.map(name => { const m = metrics.per_class[name]; return <tr key={name}><th scope="row">{riskName[name]}</th><td>{m.support}</td><td>{numberLabel(m.precision)}</td><td>{numberLabel(m.recall)}</td><td>{numberLabel(m.f1)}</td></tr>; })}
        <tr><th scope="row">Promedio macro</th><td>—</td><td>{numberLabel(metrics.macro.precision)}</td><td>{numberLabel(metrics.macro.recall)}</td><td>{numberLabel(metrics.macro.f1)}</td></tr></tbody></table></div>
    <p className="muted student-list-note">«Sin dato» significa no estimable (sin soporte). Sin calibración ni evaluación prospectiva institucional.</p>{cv && <p className="notice" role="status">Datos reales locales: cifras fuera de muestra del informe de comparación del modelo activo. Con n pequeño tienen alta incertidumbre y no sustituyen una validación externa.</p>}</>;
}
