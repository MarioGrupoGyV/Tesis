# Protocolo REAL (Bloque 3B-1)

El protocolo REAL es un **interruptor técnico** de procesamiento local de una cohorte con registros reales. No es un expediente de
autorizaciones. Diseño: [ADR 012](../adr/012-procesamiento-real.md). Esquema: migración `0007_real_protocol`.

**Estado actual (3B-1):** el protocolo se puede crear, confirmar y revocar, pero **todavía no desbloquea nada**. Toda operación REAL
(importar, evaluar, alertas, reportes, indicadores, modelos) sigue devolviendo `INSTITUTIONAL_PROCESSING_NOT_READY`, incluso con el protocolo
confirmado; la activación llega en 3B-2. Las pruebas lo verifican endpoint por endpoint.

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
| Regla de riesgo | versión `RIESGO_V1` (umbrales fijos de la regla) |
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

`infra/load_closings.py` carga insumos de cierre desde un CSV de códigos a un destino **aislado** (nunca el activo). El backend calcula los cinco componentes y el nivel
RIESGO_V1; el CSV no puede traer el nivel y cualquier columna adicional (por ejemplo, nombres) rechaza el archivo completo. Todo o nada.
