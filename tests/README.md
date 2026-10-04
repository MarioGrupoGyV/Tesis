# Comprobaciones S1

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
Pytest exige una DB con nombre test distinta de la demo. Fixtures hacen rollback;
los privilegios se comprueban con el rol real riesgo_app.

Las credenciales privadas se leen de .local/secrets/demo-credentials.json. No se
guardan trazas/videos/capturas durante ingreso. Las evidencias públicas contienen
resultados, cifras y hashes, sin contraseñas ni tokens de sesión/CSRF.

No se probó importación/evaluación/atención/exportación: S2–S6 siguen pendientes.
Las capturas S1 no aceptan S4 ni el recorrido completo de S6.
