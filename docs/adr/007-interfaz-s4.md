# ADR 007 — Interfaz conectada S4

Estado: aceptada para implementación, 4 de octubre de 2026, America/Lima.
SHA inicial: `90a5e8492b9bdd7d1a37ae59e105fddbd7e116a7`; checkout limpio.

## Alcance y navegación

S4 completa acceso, Inicio, Estudiantes/lista/detalle/historial, Datos/importación
y consulta administrativa de Modelos/evaluación sintética con la API 0.4.0 existente.
Conservar identidad SE/verde, superficies claras, tablas comparables y ayuda breve.
Alertas y Reportes se identifican como pendientes de S5, sin enlaces o acciones
simuladas. RESEARCHER conserva un inicio limitado y su sesión.

Rutas de navegador estables mediante History API, sin dependencia nueva: Inicio,
Estudiantes, detalle de estudiante, Datos, Modelos y detalle de modelo. Periodo y
sección autorizados forman el contexto de URL; navegación, recarga y acceso directo
respetan rol. El servidor sigue siendo la autoridad de permisos y sección.

## Patrón de pantallas y estado

AppShell, navegación adaptable, contexto, encabezados, estados, paginación y badges
reutilizables; pantallas en features, cliente tipado en lib. TanStack Query conserva
keys por usuario/rol/contexto/filtros, cancelación y limpieza de caché al cambiar
sesión. Cookies HttpOnly y CSRF exclusivamente en memoria. Mutaciones sin reintentos
automáticos; errores sanitizados conservan detalles y referencia de solicitud.

Cada pantalla diferencia carga, vacío, filtros sin resultados, error, bloqueo y
éxito. Riesgo usa texto/icono/color; null nunca significa LOW. DATE conserva su día
y timestamps se muestran en America/Lima. ProcessingStatus gobierna acciones
sensibles; consulta fallida las deshabilita. Su estado general no acredita la
compatibilidad de un periodo concreto con el modelo activo.

## Importación e inferencia

Flujo Preparar → Revisar → Confirmar, CSV exacto registrado, expected_preview_version,
CSRF y confirmación humana. COMMITTED reutilizado se presenta como tal. Extensión
mínima del launcher exporta solo CSV verificado a destino local fuera de Git, sin
sobrescritura ni secretos. No nueva descarga HTTP ni generación en interfaz.

Evaluación ADMIN con period_id/as_of actual o fecha explícita Lima. El modo actual
usa la cabecera HTTP Date de la API del mismo origen, anclada a la recepción y al
tiempo transcurrido monótono (performance.now). Su resolución de segundos y latencia
dan una estimación conservadora; no se descuenta un margen arbitrario ni se cambia
AS_OF_IN_FUTURE. Sin referencia válida se informa el diagnóstico y se permite
actualizar o elegir la fecha manual; no fallback silencioso al reloj del host.
Las fechas manuales conservan su valor y zona. Sin controles
HTTP de entrenamiento/activación, métricas inventadas o probabilidades no calibradas.
No modificar migraciones, pipelines, criterios, origen ni restricciones de S3.1.
No regenerar/reentrenar el estudio activo. REAL, S5 y S6 permanecen pendientes.

## Criterios de comprobación

API/PostgreSQL efectivos en activo y aislado, cuatro cuentas, permisos directos,
primera importación aislada y repetición activa sin duplicados, evaluación/abstención,
filtros/paginación/revisión pendiente, errores y cancelación. Build/tipos/contrato,
regresión backend y persistencia. Capturar e inspeccionar 1440×900, 768×1024 y
390×844. Evidencias nuevas s4; preservar historia, cuentas, secretos, volúmenes y locks.
Pruebas HTTP simuladas se identifican aparte y no acreditan integración.
