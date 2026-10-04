# ADR 006 — Estudio con datos sintéticos S3.1

Estado: aceptada para implementación, 4 de octubre de 2026, America/Lima.
Registrada antes del desarrollo. SHA inicial: `412c370519900351f37bf2d444df9c943e58288d`; checkout limpio.

## Alcance autorizado

La solicitud S3.1 autoriza un estudio sintético nuevo y sustituye la prohibición
anterior de generar registros ficticios. No recupera la antigua DEMO ni habilita
REAL. Se distinguen tres evidencias: funcionamiento del software; comparación
experimental condicionada por el generador; evaluación con estudiantes reales,
fuera del alcance. Aprobación técnica permite únicamente simulación local.

## Decisiones y criterios previos

- Origen explícito SYNTHETIC, contexto separado y migración 0003 posterior a las
  migraciones inmutables. Mantener valores históricos, claves compuestas,
  revisiones, transacciones, auditoría e idempotencia. REAL nunca puede activarse.
- Registro privado del estudio enlaza configuración versionada, semilla, CSV exacto
  y resultados futuros separados. El importador verifica registro/hash/contexto;
  el cliente no declara ni habilita el origen. Los datos académicos solo ingresan
  por preview/commit. Las credenciales y cuatro cuentas S2.2 se conservan.
- Protocolo `synthetic-study-v1`: 60 estudiantes ficticios configurables, cinco
  variables base, calendario cerrado en Lima y criterio numérico hipotético sobre
  resultados futuros. UUID/fechas/dataset reproducibles; tiempos operativos aparte.
- Desarrollo y reserva externa se fijan por estudiante antes de medir. CV de grupos
  en desarrollo y reserva de estudiantes diferentes con cortes posteriores al
  ajuste son evaluaciones distintas. Todas las etiquetas de desarrollo disponibles
  antes del ajuste/reserva. Selección por macro-F1 de desarrollo, luego balanced
  accuracy, luego orden fijo DUMMY/RANDOM_FOREST/SVM/XGBOOST; sin usar la reserva.
- Reutilizar cuatro pipelines CPU, parámetros/locks vigentes y artefactos privados
  firmados. Sin tuning, calibración o exactitud mínima. Probabilidades null.
  Abstenerse por faltantes/incompatibilidad; nunca imputar una clase de riesgo bajo.
- Comandos explícitos con ADMIN autenticado generan, comparan, registran y activan
  simulación. Sin entrenamiento/activación HTTP ni tareas al arrancar. Activación
  atómica/auditada con comprobación de manifiesto, hashes, versión y procedencia.
- API publica estado de procesamiento y procedencia sanitizada, sin etiquetas,
  particiones o artefactos privados. Aviso servidor en el inicio; sin pantallas S4.
- Comprobar migración limpia/desde S3, aislamiento de orígenes, determinismo,
  integridad de archivos, permisos/CSRF, reserva temporal, idempotencia/abstención,
  recorrido API/DB real y persistencia sin borrar volúmenes. Conservar evidencias
  anteriores; clasificar resultados comprobados, fallidos y no ejecutados.

## Revisión académica pendiente

Revisar con el asesor objetivos e hipótesis dependientes de alumnos reales, unidad
de análisis (estudiantes simulados independientes frente a cortes), origen y
mecanismo de generación, instrumentos, análisis, discusión y generalización.
No se editan documentos académicos oficiales ni se afirma aprobación del asesor,
autorización del colegio, eficacia escolar o validación de la tesis. El trabajo
de software continúa bajo el alcance sintético autorizado. S4–S6 pendientes.
