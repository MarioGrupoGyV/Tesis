# Infraestructura S1 DEMO

La raíz contiene Compose con web/api/db, volumen PostgreSQL y puertos loopback.
docker/ fija los runtimes S0; db/init-app-role.sh crea riesgo_app sin privilegios DDL.
compose.migrate.yaml monta la credencial del propietario solo para Alembic;
compose.seed.yaml monta las credenciales sintéticas solo para la semilla.

Desde la raíz: py -3.12 infra/s1.py up y py -3.12 infra/s1.py seed-demo.
prepare_demo.py genera secretos privados una sola vez. down conserva el volumen;
restart no siembra ni migra. Véase README raíz para requisitos, rutas y puertos.

check_s0.py conserva la validación OpenAPI/SQL/tipos/locks y ahora acepta y comprueba
Compose S1. No prueba ejecución funcional. El resultado actual se guarda en
tests/evidence/s1-contracts.json y conserva la evidencia histórica S0.

Con .venv-s1 y requirements-dev.txt instalado:
- test_s1.py prepare-db crea/migra DB aislada con nombre test.
- test_s1.py pytest ejecuta pruebas con rollback y produce XML.
- smoke_s1.py usa la demo real, comprueba HTTP, detiene/recrea servicios sin -v,
  compara hashes y cantidades de las trece tablas, recupera sesión y la revoca.
- capture_s1.mjs captura acceso vacío y contexto autorizado en tres dimensiones,
  comprueba teclado y no captura contraseñas/tokens.

No ejecutar smoke mientras otros recorridos estén usando estos tres servicios.
Las pruebas no eliminan DBs ni volúmenes. train-demo/demo/backup siguen pendientes.
