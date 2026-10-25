-- Bloque 8 (ADR 013): RIESGO_V2, cuatro componentes sin participación (no existe registro original de la participación en aula).
-- SOLO AMPLÍA las reglas: RIESGO_V1 conserva exactamente sus CHECK y las filas V1 existentes siguen siendo válidas sin modificarse.
-- Las referencias son de solo inserción: V2 se agrega como filas nuevas (rule_version='RIESGO_V2', revision=1).

-- 1. Retirar los CHECK que solo admitían V1 (se localizan por su definición: Postgres les puso nombre automático en 0007).
DO $$
DECLARE item record;
BEGIN
 FOR item IN SELECT conname, pg_get_constraintdef(oid) AS definition FROM pg_constraint
             WHERE conrelid='risk_school.risk_references'::regclass AND contype='c' LOOP
  IF item.definition LIKE '%rule_version%'
     OR item.definition LIKE '%participation_level%'
     OR item.definition LIKE '%total_points%' THEN
   EXECUTE format('ALTER TABLE risk_school.risk_references DROP CONSTRAINT %I', item.conname);
  END IF;
 END LOOP;
 FOR item IN SELECT conname, pg_get_constraintdef(oid) AS definition FROM pg_constraint
             WHERE conrelid='risk_school.processing_protocols'::regclass AND contype='c' LOOP
  IF item.definition LIKE '%risk_rule%' THEN
   EXECUTE format('ALTER TABLE risk_school.processing_protocols DROP CONSTRAINT %I', item.conname);
  END IF;
 END LOOP;
END $$;

-- 2. Reglas por versión. V1: exactamente las de 0007. V2: participación y su puntaje NULL, suma de cuatro componentes,
--    Bajo 0–1, Medio 2–3, Alto ≥ 4.
ALTER TABLE risk_school.risk_references ALTER COLUMN participation_level DROP NOT NULL;
ALTER TABLE risk_school.risk_references ALTER COLUMN points_participation DROP NOT NULL;
ALTER TABLE risk_school.risk_references
 ADD CONSTRAINT risk_reference_rule_version CHECK(rule_version IN ('RIESGO_V1','RIESGO_V2')),
 ADD CONSTRAINT risk_reference_participation_by_rule CHECK(
  (rule_version='RIESGO_V1' AND participation_level IS NOT NULL AND participation_level BETWEEN 1 AND 5
   AND points_participation IS NOT NULL
   AND points_participation=CASE WHEN participation_level<=2 THEN 2 WHEN participation_level=3 THEN 1 ELSE 0 END)
  OR (rule_version='RIESGO_V2' AND participation_level IS NULL AND points_participation IS NULL)),
 ADD CONSTRAINT risk_reference_total_by_rule CHECK(
  (rule_version='RIESGO_V1' AND total_points=points_grade+points_attendance+points_activities+points_participation+points_conduct)
  OR (rule_version='RIESGO_V2' AND total_points=points_grade+points_attendance+points_activities+points_conduct)),
 ADD CONSTRAINT risk_reference_level_by_rule CHECK(
  (rule_version='RIESGO_V1' AND risk_level=CASE WHEN total_points>=5 THEN 'HIGH' WHEN total_points>=2 THEN 'MEDIUM' ELSE 'LOW' END)
  OR (rule_version='RIESGO_V2' AND risk_level=CASE WHEN total_points>=4 THEN 'HIGH' WHEN total_points>=2 THEN 'MEDIUM' ELSE 'LOW' END));

-- 3. El protocolo REAL puede declarar cualquiera de las dos reglas (los protocolos confirmados siguen inmutables).
ALTER TABLE risk_school.processing_protocols ADD CONSTRAINT protocol_risk_rule_version CHECK(
 jsonb_typeof(risk_rule)='object' AND risk_rule->>'version' IN ('RIESGO_V1','RIESGO_V2'));
