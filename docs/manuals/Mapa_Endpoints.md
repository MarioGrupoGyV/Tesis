# Mapa de endpoints

Contrato vigente: [OpenAPI 0.5.0](../planning/Contrato_API.yaml), **27 operaciones
en 26 paths**, todas bajo `/api/v1`. Las rutas están implementadas en
[api/v1](../../backend/app/api/v1) y el navegador las consume mediante el
[cliente tipado](../../frontend/src/lib/api.ts). Los tipos se generan desde el
contrato; no se define un contrato distinto en cada pantalla.

Este mapa describe entradas, salidas y controles existentes. Las pruebas nuevas
del checkout S6 están en [Estado S6](../planning/Estado_Sprint_6.md) y la
[matriz final](Matriz_Trazabilidad_Final.md); una fila aquí no acredita una ejecución.

## Lectura de la matriz

**A** = ADMIN; **T** = TUTOR; **D** = DIRECTOR; **R** = RESEARCHER.
**ATD** siempre aplica alcance servidor: el tutor solo sus secciones. Un recurso
estudiante/predicción/caso/actividad ajeno y uno inexistente tienen el mismo 404
sanitizado. No basta con ocultar un botón. Los catálogos y filtros por sección
conservan sus controles explícitos: por ejemplo, pedir una sección ajena en el
listado de estudiantes puede dar 403, sin publicar sus registros.

Todas las consultas autenticadas usan cookie `session`, HttpOnly/SameSite=Lax,
Secure bajo HTTPS; el entorno local opera HTTP en loopback. Las escrituras incluyen
`X-CSRF-Token`, salvo login, que exige `Origin` exacto autorizado y límite de intentos.
El rol nunca procede de una cabecera del navegador. CSV es una lectura autorizada
que audita su solicitud; no exige CSRF ni admite acceso de RESEARCHER.

Las salidas indicadas son nombres de schemas OpenAPI. Los campos privados DB/ML
no se publican porque existan en una tabla. UUID de path/query es obligatorio
cuando se indica `{id}` o `period_id`. Fechas de instantes llevan zona; el servidor
normaliza a UTC y valida disponibilidad/incorporación temporal.

## Disponibilidad, acceso y contexto — 9 operaciones

| Método / ruta | Rol y control | Entrada | Salida correcta | Consumidor |
| --- | --- | --- | --- | --- |
| GET `/health/live` | Pública, sin sesión | Sin parámetros | 200 Health, status=ok | Healthcheck de proceso/diagnóstico |
| GET `/health/ready` | Pública, sin sesión | Sin parámetros | 200 Health o 503 Health, status=unavailable | Healthcheck de API y verificación DB |
| POST `/auth/login` | Cuenta activa, Origin autorizado; sin CSRF previo | LoginInput: email/password | 200 LoginResult: User, csrf_token, expires_at; cookie en Set-Cookie | Acceso |
| GET `/auth/me` | A/T/D/R autenticados | Cookie | 200 User sin hash de contraseña | Restauración de sesión/AppShell |
| GET `/auth/csrf` | A/T/D/R autenticados | Cookie | 200 Csrf de la sesión | Cliente API, solo memoria |
| POST `/auth/logout` | A/T/D/R, CSRF | Sin cuerpo | 204 sin JSON; cookie borrada y sesión revocada | Cerrar sesión |
| GET `/periods` | ATD | Sin filtros | 200 Period[] autorizados; [] si contexto vacío | Selector de periodo/Inicio |
| GET `/sections` | ATD | period_id UUID | 200 Section[] del periodo/año y alcance autorizado | Selector de sección |
| GET `/processing/status` | A/T/D/R | Sin parámetros | 200 ProcessingStatus: scope, notice, institutional_ready=false, synthetic_ready, operaciones disponibles/motivos | Inicio y controles de Datos/Modelos/seguimiento/Reportes |

`Health` solo informa disponibilidad. No acredita migración, registro del CSV,
compatibilidad del modelo o permiso de escritura. ProcessingStatus deriva de
registro/configuración/archivos/rol; su disponibilidad general tampoco sustituye
la comprobación del periodo concreto en una operación.

Login devuelve 401 por credenciales inválidas/inactivas, 403 por Origin y 429 con
Retry-After al superar 10 intentos por IP/correo en 300 segundos. También cuentan
los intentos correctos. No desactivar el límite para una revisión. Sesión vencida,
revocada o inactiva devuelve 401. Logout no elimina evidencia de sesiones/auditoría.

## Importación — 3 operaciones

| Método / ruta | Rol y control | Entrada | Salida correcta | Consumidor |
| --- | --- | --- | --- | --- |
| POST `/imports/preview` | A + CSRF + procedencia registrada | Multipart exacto: file, period_id | 201 ImportBatch nuevo o 200 reutilizado | Datos, Revisar archivo |
| GET `/imports/{id}` | A | UUID de lote | 200 ImportBatch público | Datos, Consultar lote/resultado |
| POST `/imports/{id}/commit` | A + CSRF + versión/procedencia | UUID; JSON expected_preview_version entero positivo | 200 ImportCommit, lote/cantidades/reused_result | Datos, Confirmar importación |

CSV UTF-8, BOM opcional, coma, 5 MiB máximo y 10000 filas de datos. Cabeceras exactas:

```text
student_code,grade,section,cutoff_at,target_date,available_at,window_start,average_grade,attendance_pct,activities_pct,participation_level,behavior_incidents,age_years
```

SYNTHETIC admite solo el archivo/hash/contexto registrado por preparación ADMIN
explícita. No acepta un origen enviado por el cliente como autorización. Archivo
modificado/no registrado devuelve 422 UNREGISTERED_SYNTHETIC_FILE; REAL devuelve
422 INSTITUTIONAL_PROCESSING_NOT_READY sin guardar archivo ni registros académicos.

Preview guarda lote/archivo/metadatos, sin estudiantes/matrículas/cortes. Errores de
estructura devuelven 422; errores por fila quedan en lote FAILED con fila, campo y
corrección esperada, sin confirmación parcial. Las mediciones ausentes son null;
missing_fraction se calcula en servidor. Días académicos se comparan en Lima.

Commit revalida lo observado y usa locks/transacción/auditoría. Estado cambiado:
409 IMPORT_PREVIEW_STALE; lote inválido: 422 IMPORT_INVALID; conflicto de integridad:
409, nunca 503. El mismo archivo/periodo y un commit ya confirmado reutilizan el
resultado. Un lote COMMITTED puede consultarse/reutilizarse con el periodo bloqueado
porque no crea otra escritura académica. Correcciones del motor crean nuevas
revisiones; el protocolo sintético vigente no admite editar manualmente su CSV exacto.

## Estudiantes e historial — 3 operaciones

| Método / ruta | Rol y control | Entrada | Salida correcta | Consumidor |
| --- | --- | --- | --- | --- |
| GET `/students` | ATD, filtros/alcance servidor | period_id obligatorio; section_id, search, risk_level, sort, page, page_size opcionales | 200 StudentPage | Estudiantes/lista |
| GET `/students/{id}` | ATD, recurso autorizado | UUID estudiante, period_id | 200 StudentDetail, corte/predicción actual sanitizados | Estudiante/detalle |
| GET `/students/{id}/timeline` | ATD, recurso autorizado | UUID, period_id; page/page_size | 200 TimelineEventPage | Estudiante/historial paginado |

Lista: search hasta 40 caracteres, risk_level LOW/MEDIUM/HIGH; sort anon_code
(predeterminado), risk_desc o updated_desc, con desempate estable. Page >=1;
page_size 1–100, predeterminado 20. Timeline conserva esos límites; la interfaz
puede pedir páginas de 5/10/20 eventos. No se descarga toda la población para
filtrarla en React. Una revisión nueva sin su propia predicción sigue pendiente.
Sin evaluación o ante insuficiencia, riesgo null; no LOW fabricado.

## Modelos e inferencia — 4 operaciones

| Método / ruta | Rol y control | Entrada | Salida correcta | Consumidor |
| --- | --- | --- | --- | --- |
| GET `/models` | A | page 1–10000, default 1; page_size 1–100, default 25 | 200 ModelPage | Modelos/lista |
| GET `/models/{id}` | A | UUID modelo | 200 Model público | Modelos/detalle |
| GET `/predictions/{id}` | ATD, sección servidor | UUID predicción | 200 Prediction | Evaluación histórica/detalle de caso |
| POST `/predictions/run` | A + CSRF + protocolo/modelo/periodo | PredictionRunInput: period_id, as_of con zona no futuro | 200 PredictionRunResult: selected/created/reused/abstentions/followup | Modelos, Evaluar periodo |

Modelos lista por created_at DESC/id ASC y publica nombre/versión/algoritmo/origen,
esquema/criterio, estado técnico y actividad. No hashes, artefactos, métricas,
etiquetas o particiones privadas. No hay entrenamiento, upload/download o
activación HTTP. Comparar/registrar/activar SYNTHETIC son comandos ADMIN explícitos.

Inferencia usa la última revisión por matrícula con corte, disponibilidad e
incorporación <=as_of, y modelo activo compatible disponible para ese instante.
REAL sigue bloqueado antes de procesar información institucional. Errores:
409 MODEL_NOT_AVAILABLE/MODEL_INCOMPATIBLE/PERIOD_LOCKED, 422 AS_OF_IN_FUTURE o
INSTITUTIONAL_PROCESSING_NOT_READY. Una abstención devuelve snapshot/status/reason
y no inserta una predicción con riesgo inventado. Probabilidades null/no calibradas.

Predicción, seguimiento followup-policy-v1 y auditoría se confirman juntos; no hay
commit parcial previo. UNIQUE corte/modelo reutiliza resultados en repetición y
concurrencia. Solo las predicciones seleccionadas que siguen actuales sincronizan
seguimiento; las históricas se cuentan ignored_stale y no retroceden la fuente.

## Seguimiento — 6 operaciones

| Método / ruta | Rol y control | Entrada | Salida correcta | Consumidor |
| --- | --- | --- | --- | --- |
| POST `/alerts/sync` | A + CSRF | SyncInput: period_id | 200 FollowupResult | Alertas, Actualizar alertas |
| GET `/alerts` | ATD | period_id; section_id/search/status/severity/sort/page/page_size opcionales | 200 AlertPage | Alertas/lista |
| GET `/alerts/{id}` | ATD, recurso autorizado | UUID caso | 200 AlertDetail | Caso/fuente/estado/actividades/historia |
| PATCH `/alerts/{id}` | A/T autorizados + CSRF | AlertPatch: expected_version, status, resolution_reason al cerrar | 200 AlertDetail | Cambiar estado/concluir/descartar |
| POST `/interventions` | A/T autorizados + CSRF | InterventionCreate: alert_id, expected_alert_version, creation_key, kind, objective, scheduled_at; notes opcionales | 201 InterventionCreateResult nuevo o 200 reutilizado | Planificar actividad |
| PATCH `/interventions/{id}` | A/T autorizados + CSRF | InterventionPatch: expected_version y al menos un cambio permitido | 200 InterventionView | Editar planificación/registrar realizada o cancelada |

Alertas: search máximo 40; status OPEN/IN_REVIEW/RESOLVED/DISMISSED; severity
MEDIUM/HIGH de la fuente; sort anon_code/severity_desc/updated_desc, default updated_desc.
Page 1–10000; page_size 1–100, default 20; desempate UUID. AlertDetail diferencia
source_prediction, latest_snapshot/latest_prediction, capacidades servidor,
actividades y últimos 100 eventos públicos; history_truncated indica más historia.

Sync procesa la evaluación actual compatible. FollowupResult contiene
created/updated/retained_low/no_alert/reused/ignored_stale/skipped_missing.
MEDIUM/HIGH motivan seguimiento; LOW conserva el caso humano previo o registra
NO_ALERT. Decisión única por predicción: repetir no duplica ni reabre el caso cerrado.
Sin predicción actual no se inventa LOW ni decisión evaluada.

Versiones son enteros estrictos positivos. OPEN→IN_REVIEW/RESOLVED/DISMISSED;
IN_REVIEW→RESOLVED/DISMISSED; cierres terminales con motivo no vacío hasta 1000 y
closed_at servidor. Cambio efectivo incrementa una vez; no-op no incrementa.
Conflictos: 409 VERSION_CONFLICT/INVALID_TRANSITION/FOLLOWUP_CONFLICT.

Actividad: kind TUTORING/REINFORCEMENT/FAMILY_MEETING/OTHER; objetivo no vacío
máximo 1000; notas máximo 2000; scheduled_at con zona. Creación deriva actor,
matrícula/origen y empieza PLANNED. UUID creation_key identifica intención del actor
con digest del payload **original**, incluida expected_alert_version. Misma clave y
payload reutilizan aun tras editar la actividad; distinto contenido da 409
CREATION_KEY_CONFLICT. Caso cerrado rechaza una actividad nueva con 409 ALERT_CLOSED.

PATCH permite kind/objective/scheduled_at/notes/status/performed_at. PLANNED puede
editarse o pasar a DONE/CANCELLED; terminales no se editan. DONE exige performed_at
explícito con zona y no futuro: 422 si falta/inválido o PERFORMED_AT_IN_FUTURE.
CANCELLED conserva null. Una actividad ya planificada puede terminarse después del
cierre del caso si el periodo sigue abierto. El cierre no la completa automáticamente.

## Resumen y CSV — 2 operaciones

| Método / ruta | Rol y control | Entrada | Salida correcta | Consumidor |
| --- | --- | --- | --- | --- |
| GET `/reports/summary` | ATD, conjunto autorizado servidor | period_id; section_id/search/risk_level/evaluation_status/alert_status/page/page_size | 200 ReportSummary | Inicio compacto y Reportes |
| GET `/reports/export.csv` | ATD, mismo alcance; solicitud auditada | Mismos filtros, sin page/page_size | 200 text/csv, conjunto filtrado completo | Reportes, Descargar CSV |

Summary: search máximo 40; risk LOW/MEDIUM/HIGH; evaluation_status
EVALUATED/NOT_EVALUATED/INSUFFICIENT_DATA; alert_status estados de caso. Page 1–10000;
page_size 1–100, default 20. Items son paginados, agregados del conjunto completo.
Una matrícula por unidad. Total=evaluados+pendientes+insuficientes;
evaluados=LOW+MEDIUM+HIGH. Porcentaje de riesgo usa evaluados como denominador;
cero produce null con motivo. Casos/actividades se agregan separadamente, sin
multiplicar filas. generated_at servidor y rango de últimos cortes visibles.

CSV: UTF-8 BOM, CRLF, quoting y 19 cabeceras:

```text
origen,alcance,periodo,generado_en_utc,codigo_sintetico,grado,seccion,ultimo_corte_utc,estado_evaluacion,riesgo_actual,caso_activo,estado_caso_activo,casos_abiertos,casos_en_revision,casos_concluidos,casos_descartados,actividades_planificadas,actividades_realizadas,actividades_canceladas
```

Nombre fijo `seguimiento-escolar-reporte.csv`, Content-Disposition attachment,
Cache-Control no-store y X-Content-Type-Options nosniff. Ausencias como celdas vacías;
sin notas/motivos narrativos/etiquetas/métricas privadas. Quita controles y neutraliza
prefijos de fórmula =,+,-,@ con apóstrofo en la proyección, sin cambiar DB. La
auditoría registra solicitud/actor/filtros/alcance/instante/conteo, no apertura/guardado.
Fallo devuelve JSON Error, nunca un CSV aparente de éxito.

## Errores y orden de validación

Excepto ready, los errores documentados usan Error: code, message, details[] y
request_id; no SQL, parámetros, trazas, rutas privadas o secretos. X-Request-ID es
generado en servidor. El contrato enumera errores transversales: no significa que
cada combinación sea una rama alcanzable de todas las operaciones.

| HTTP | Interpretación | Acción del cliente |
| --- | --- | --- |
| 401 | Sesión/credenciales no válidas | Regresar al acceso, limpiar estado de sesión |
| 403 | Rol/alcance/Origin/CSRF no autorizado | No repetir con otro rol/cabecera inventados |
| 404 | Recurso inexistente o ajeno | Mismo aviso seguro, sin identificar un recurso ajeno |
| 409 | Versión/estado/periodo/modelo/integridad/concurrencia | Consultar/revisar el estado antes de una nueva acción explícita |
| 422 | Entrada/esquema/fechas/protocolo/origen no válidos | Corregir solicitud; REAL no tiene flag de habilitación |
| 429 | Límite de login | Respetar Retry-After y la ventana |
| 503 | DB/almacenamiento indisponibles | Mostrar error; no afirmar escritura ni reintentar automáticamente |
| 500 | Fallo interno inesperado sanitizado | Conservar referencia de soporte y revisar el resultado |

Escrituras de importación/inferencia/seguimiento: sesión→rol→CSRF→preparación→
entrada→contexto/origen→procedencia/modelo/recurso/versión. Sin estudio preparado,
el bloqueo institucional precede al procesamiento del cuerpo académico. Validaciones
de tipos de query/path propias de FastAPI no prueban acceso a un recurso. Los
servicios vuelven a validar permisos y locks al escribir.

Integridad/versión/periodo bloqueado corresponden a 409/422, **no 503**. Ready mantiene
Health aun en 503. Una escritura de respuesta perdida es incierta: consultar y
repetir solo mediante acción explícita preservando clave/payload o versión revisada.
Mutaciones y exportaciones no se reintentan automáticamente.

No hay endpoints de entrenamiento/activación/borrado, comunicaciones, gestión pública
de cuentas, eficacia escolar o integración institucional. Los comandos de
instalación/perfiles y recuperación pertenecen a infraestructura, no a la API pública.
