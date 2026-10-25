# Protocolo REAL (Bloques 3B-1 y 3B-2)

El protocolo REAL es un **interruptor técnico** de procesamiento local de una cohorte con registros reales. No es un expediente de
autorizaciones. Diseño: [ADR 012](../adr/012-procesamiento-real.md) y, para la regla de referencia, [ADR 013](../adr/013-riesgo-v2-sin-participacion.md).
Esquema: migración `0007_real_protocol`; `0009_riesgo_v2` admite la regla RIESGO_V2.

**Estado actual (3B-2):** con el protocolo **confirmado**, el periodo REAL queda habilitado para el ciclo local descrito abajo; sin
confirmar (o tras revocar) toda operación REAL devuelve `INSTITUTIONAL_PROCESSING_NOT_READY`. Las pruebas lo verifican endpoint por
endpoint, con datos ficticios etiquetados REAL (nunca datos del colegio). Los resultados son **análisis exploratorio local**: no
demuestran eficacia escolar ni sustituyen una validación externa.

## Qué guarda

Una fila por periodo REAL (`processing_protocols`):

| Campo | Contenido |
|---|---|
| Periodo | un periodo REAL (único); solo ADMIN lo registra |
| Colegio y cohorte | textos libres (p. ej. «3.º secundaria 2026») |
| Escalas | calificación (p. ej. 0–20) y participación (p. ej. 1–5, con etiquetas opcionales) |
| Bimestres | por cada uno: código, inicio, fecha de corte de datos, disponibilidad del corte, cierre, disponibilidad del cierre y días programados |
| Fuente | descripción de la base de origen |
| Reglas de calidad y de elegibilidad/faltantes | rangos y claves; fracción máxima de faltantes y variables requeridas |
| Regla de riesgo | versión `RIESGO_V2` en los protocolos nuevos (regla activa, sin participación) o `RIESGO_V1` en los anteriores; queda congelada al confirmar |
| Plazos de oportunidad | días de detección e intervención |
| `authorization_confirmed_by_admin` | booleano (por defecto `false`) con `confirmed_by` y `confirmed_at` coherentes |

## Qué NO guarda

**Quedan fuera del sistema:** consentimientos y asentimientos, el documento de autorización, el nombre de quien autoriza y la fecha del
permiso. No existe ningún campo para ellos y la API rechaza campos desconocidos. La autorización la custodia el colegio; el sistema solo
registra que **un administrador confirmó el interruptor**, con su identificador y el instante UTC.

Tampoco guarda nombres de estudiantes en el protocolo, indicadores, exportaciones ni evidencias (los nombres, si se usan, viven solo en la ficha del alumno).

## Cómo se confirma y se revoca

Solo ADMIN, con sesión, CSRF y `Origin` (como el resto de escrituras). Las operaciones son idempotentes: repetir el mismo estado no cambia nada ni genera auditoría.

1. **Crear:** `POST /processing-protocols` con el periodo REAL y los parámetros. Repetir el mismo contenido devuelve el mismo protocolo; otro contenido para el mismo periodo da 409.
   Los bimestres deben quedar dentro del periodo y el periodo debe ser REAL.
2. **Consultar:** `GET /processing-protocols?period_id=…`.
3. **Confirmar:** `POST /processing-protocols/{id}/confirm`. Registra quién y cuándo (UTC), incrementa la versión y audita `PROTOCOL_AUTHORIZATION_CONFIRMED`.
4. **Revocar:** `POST /processing-protocols/{id}/revoke`. Borra quién y cuándo de la fila (el historial queda en la auditoría), incrementa la versión y audita `PROTOCOL_AUTHORIZATION_REVOKED`.

Garantías de base de datos:

- Con el protocolo confirmado **no se editan** sus parámetros (ni siquiera el propietario de la base); tampoco se borra jamás un protocolo.
- Los eventos de auditoría llevan actor, instante UTC y **solo** `protocol_id` y `period_id`.
- Sin confirmar (o tras revocar), `require_real_protocol` mantiene `INSTITUTIONAL_PROCESSING_NOT_READY`.

## Elegibilidad REAL (preparada, sin activar)

Hoy `students_eligibility_check` exige consentimiento y asentimiento para marcar elegible a un alumno REAL; como el sistema no los guarda, nadie lo es.
La regla prevista para 3B-2 es: **REAL elegible solo si hay un protocolo confirmado que cubre su matrícula**. En 3B-1 queda preparada y sin efecto:

- SQL: `real_protocol_covers_period(periodo)` y `real_student_eligible(estudiante)`, más la función de trigger `check_real_student_eligibility()`, **sin trigger asociado**.
- Python: `real_student_processable(...)`, sin uso en los flujos.
- Se eligió dejarla sin activar (en vez de un interruptor en tiempo de ejecución) porque sustituir el CHECK de consentimientos cambia el comportamiento REAL y
  porque un interruptor persistente añadiría un segundo camino que podría enmascarar el CHECK vigente. 3B-2 sustituirá el CHECK por el trigger en una migración, junto con los guards.

## Relojes retrospectivos

Las evaluaciones retrospectivas distinguen dos relojes. `recorded_at`/`predicted_at`/`opened_at` siguen siendo el momento real del registro;
`predictions.as_of_at` y `alerts.detected_at` dicen qué momento simula la evaluación. En corridas normales `as_of_at = predicted_at` y
`detected_at = opened_at` (se rellenan por defecto; las alertas existentes se completaron con `opened_at`). Un CHECK impide declarar un instante simulado posterior al real.
Ninguna respuesta pública cambia en 3B-1.

## Carga de cierres (uso interno)

`infra/load_closings.py` carga insumos de cierre desde un CSV de códigos a un destino **aislado** (nunca el activo). El backend calcula los componentes y el nivel con la
regla **del protocolo del periodo** (sin protocolo, la regla activa RIESGO_V2); el CSV no puede traer el nivel y cualquier columna adicional (por ejemplo, nombres) rechaza el
archivo completo. Todo o nada. Con RIESGO_V2 la columna de participación puede venir vacía y, si trae un valor, se ignora.

## Regla de referencia (ADR 013)

| | RIESGO_V1 (se conserva) | RIESGO_V2 (activa) |
|---|---|---|
| Componentes (0–2 puntos cada uno) | promedio, asistencia, actividades, participación, incidencias | promedio, asistencia, actividades, incidencias |
| Total | 0–10 | 0–8 |
| Nivel | Bajo 0–1, Medio 2–4, Alto ≥ 5 | Bajo 0–1, Medio 2–3, Alto ≥ 4 |

Mismos umbrales y aritmética entera en los componentes comunes: promedio redondeado a 2 decimales (mitad hacia arriba) < 11 → 2, < 14 → 1; asistencia `100·asistidos`
frente a `80·programados` / `90·programados`; actividades frente a 60 % / 80 %; incidencias ≥ 3 → 2, 1–2 → 1. V2 se adoptó porque la institución confirmó que **no existe un
registro original de la participación en aula**; el corte de Alto conserva el 50 % del máximo (5 de 10 en V1, 4 de 8 en V2) y se fijó **antes** de reentrenar. Las filas V1
existentes no se tocan: V2 se agrega como filas nuevas de `risk_references` (`rule_version = RIESGO_V2`, `revision = 1`), con participación y su puntaje en NULL.

## Ciclo REAL local (Bloque 3B-2)

Orden de trabajo de un ADMIN en un destino aislado (nunca sobre la instalación activa sin autorización expresa). Todo usa códigos; los
nombres de menores no se importan ni salen de la ficha del estudiante.

1. **Protocolo.** Registrarlo y confirmarlo (página *Protocolo REAL*, o `POST /processing-protocols` y `/confirm`). Al confirmar, los
   estudiantes activos ya matriculados en el periodo pasan a ser elegibles (no se fabrican consentimientos); los nuevos se marcan
   elegibles al matricularse o importarse mientras el protocolo esté confirmado.
2. **Estudio institucional.** `py -3.12 infra/study.py register-study --target <destino.json> --operator-profile <perfil> --protocol-id <id> --csv <cortes.csv>`.
   El CSV canónico tiene las 12 cabeceras de la plantilla (o las 13 del formato anterior: en periodos REAL la participación se ignora y no se guarda), un corte por
   estudiante y bimestre, y el mismo horizonte (días entre la disponibilidad del último dato y el cierre) en todos los bimestres.
   El sistema guarda el archivo exacto en el almacenamiento privado y solo acepta ese contenido en la importación.
3. **Importación.** `study.py import --study-id <id>` (o la pantalla *Datos* con el mismo archivo). Escalas de nota y participación
   (1–5) salen del protocolo.
4. **Cierres.** `py -3.12 infra/load_closings.py ...` registra los insumos de cierre; el backend calcula la regla del protocolo, RIESGO_V2 en los nuevos (`risk_references`,
   solo inserción). Sin cierres no hay etiquetas y la comparación responde `INSUFFICIENT_DATA_FOR_STUDY`.
5. **Comparación exploratoria.** `study.py compare --study-id <id> [--repetitions N] [--loso]`: validación cruzada agrupada por
   estudiante (5 pliegues, ≥ 20 repeticiones con semillas derivadas), RF/SVM/XGBoost/Dummy, media ± DE y matriz de confusión agregada;
   selección por la regla del estudio sobre la media. Aviso de n pequeño en el informe, en *Modelos* y en el manifiesto.
6. **Registro y activación.** `study.py register --study-id <id>` y `study.py activate --model-id <id>`. Un solo modelo activo por
   origen; activar uno REAL nunca desactiva el SYNTHETIC. Aprobación `LOCAL_EXPLORATORY`.
7. **Evaluación retrospectiva.** `study.py run --period-id <id> --as-of <fecha-corte>` (una corrida por corte). Las predicciones y
   alertas conservan el instante real (`predicted_at`, `opened_at`) y guardan el simulado (`as_of_at`, `detected_at`); la API y la
   interfaz las rotulan «simulación retrospectiva». Las mediciones manuales REAL no se evalúan.
8. **Indicadores.** Página *Indicadores* con selector de bimestre: PDER usa la fecha simulada de detección frente al cierre; NIA e
   intervención oportuna son `null` con motivo `NO_REAL_INTERVENTIONS` mientras no haya intervenciones reales registradas por el flujo
   existente. Los CSV llevan solo códigos.

**Revocar** el protocolo bloquea de inmediato todo lo anterior, retira la elegibilidad de los alumnos REAL del periodo y conserva lo ya guardado (estudio, referencias, predicciones, alertas). Confirmar de nuevo los habilita otra vez. La auditoría guarda solo quién (actor) y cuándo (UTC), con identificadores.

Límites vigentes: cohorte única (60 estudiantes, dos bimestres de las mismas personas: la unidad de partición es el estudiante); una sola
alerta activa por matrícula (la alerta de B1 se actualiza en B2, pero PDER y CRA se calculan con la predicción de cada corte); sin calibración; sin validación externa; la procedencia de los
reportes PRV 120/126 y 113/120 no está confirmada y no se importa.
