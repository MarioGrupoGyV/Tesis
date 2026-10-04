# Comprobaciones S1/S2

S2 conserva los casos S1. La suite final tiene 104 casos aprobados en Linux/Python
3.12.12 y PostgreSQL 17.6: 57 de S1 y 47 de importación/estudiantes. El runner crea
una base aislada por ejecución; S2 confirma transacciones y no debe ejecutarse en
la base de la demo. Consultar docs/planning/Estado_Sprint_2.md para comandos,
fallos corregidos, resultados y omisiones. Las pruebas incluyen riesgo_app,
concurrencia real, rollback, 10000 filas y fechas Lima/UTC.

fixtures/synthetic contiene solo CSV inventados para pruebas. s2-response-samples.json
contiene once respuestas públicas validadas frente al contrato 0.1.2. smoke_s2.py
comprueba HTTP y persistencia de PostgreSQL/archivos privados tras recrear servicios.
Playwright conserva los cuatro recorridos S1; S2 no añade pantallas.

Las evidencias S0 se conservan. S1 incluye:
- backend/tests: 57 casos PostgreSQL de sesiones/CSRF, roles, alcance, integridad,
  permisos de base, transacciones, semilla y configuración.
- tests/e2e/s1.spec.ts: cuatro recorridos contra Compose real con tres roles y
  credenciales inválidas; recuperación al recargar y rechazo de cookie revocada.
- infra/smoke_s1.py: HTTP real y comparación de trece tablas antes/después de
  detener/recrear Compose, sin borrar volumen ni ejecutar semilla.
- infra/capture_s1.mjs: seis capturas de acceso/contexto S1 en 1440×900, 768×1024
  y 390×844, más capturas completas cuando hay desplazamiento vertical.

Consultar README raíz y docs/planning/Estado_Sprint_1.md para comandos y resultados.
Pytest exige una DB con nombre test distinta de la demo. Fixtures S1 hacen rollback;
los privilegios se comprueban con el rol real riesgo_app.

Las credenciales privadas se leen de .local/secrets/demo-credentials.json. No se
guardan trazas/videos/capturas durante ingreso. Las evidencias públicas contienen
resultados, cifras y hashes, sin contraseñas ni tokens de sesión/CSRF.

Se probó importación por API. Evaluación/atención/exportación siguen pendientes S3–S6.
Las capturas S1 no aceptan S4 ni el recorrido completo de S6.
