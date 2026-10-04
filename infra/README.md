# Infraestructura S1/S2 DEMO

La raíz contiene Compose con web/api/db, volúmenes PostgreSQL/CSV privados y puertos loopback.
docker/ fija los runtimes S0; db/init-app-role.sh crea riesgo_app sin privilegios DDL.
compose.migrate.yaml monta la credencial del propietario solo para Alembic;
compose.seed.yaml monta las credenciales sintéticas solo para la semilla.

Desde la raíz: py -3.12 infra/s1.py up y py -3.12 infra/s1.py seed-demo.
prepare_demo.py genera secretos privados una sola vez. down conserva el volumen;
restart no siembra ni migra. Véase README raíz para requisitos, rutas y puertos.

check_s0.py conserva la validación OpenAPI/SQL/tipos/locks y ahora acepta y comprueba
Compose S2 y OpenAPI 0.1.2. No prueba ejecución funcional. El resultado actual se
guarda en tests/evidence/s2-contracts.json y conserva las evidencias históricas.

La suite completa usa Linux/Python 3.12.12 y PostgreSQL aislado:

```powershell
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
```

run_linux_tests.py crea otra base por ejecución, migra como propietario y ejecuta
peticiones como riesgo_app. No comparte red ni volumen con la demo ni publica
puertos. TEST_REPORT_NAME permite conservar distintos reportes. Las bases quedan
conservadas. import_data guarda CSV mediante UUID internos fuera del checkout.

Con .venv-s1 y requirements-dev.txt instalado:
- test_s1.py prepare-db crea/migra DB aislada con nombre test.
- test_s1.py pytest ejecuta solo las pruebas S1 con rollback y produce XML.
- smoke_s2.py importa muestras sintéticas, comprueba las seis operaciones, CSRF,
  revisión y permisos; recrea servicios y compara las trece tablas y archivos privados.
- smoke_s1.py usa la demo real, comprueba HTTP, detiene/recrea servicios sin -v,
  compara hashes y cantidades de las trece tablas, recupera sesión y la revoca.
- capture_s1.mjs captura acceso vacío y contexto autorizado en tres dimensiones,
  comprueba teclado y no captura contraseñas/tokens.

No ejecutar smoke mientras otros recorridos estén usando estos tres servicios.
Las pruebas no eliminan DBs ni volúmenes. train-demo/demo/backup siguen pendientes.
