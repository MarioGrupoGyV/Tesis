# Backend de Seguimiento Escolar — S3.1

Contrato público 0.4.0. S3.1 autoriza solo el estudio SYNTHETIC registrado; REAL sigue
bloqueado. Capas rutas/esquemas/servicios/repositorios/ML, riesgo_app y migraciones
revisadas con propietario temporal. 0001/0002 intactas; 0003 añade registro privado
mínimo y guards de simulación, sin convertir/eliminar datos históricos.

Generador explícito versionado, CSV/hash/contexto verificados antes de importar,
confirmación y bindings transaccionales. CLI authenticate ADMIN para comparar,
registrar/activar simulación. No entrenamiento/activación HTTP, startup o flags REAL.
Núcleo S3 conserva cuatro pipelines CPU/grupos/artefactos privados firmados; contratos
internos v2 para SYNTHETIC, v1 aislado compatible. Desarrollo y reserva temporal externos
se separan antes de medir. Cinco variables, probabilidades null, abstención y auditoría.

GET processing/status público para sesión, sanitizado por rol; las demás 18 rutas
S1/S2/S3 conservan funcionamiento. Consulte docs/manuals/Manual_Estudio_Sintetico.md.
Suite completa desde PowerShell, PostgreSQL aislado/Linux Python 3.12.12 dentro de Docker:

```powershell
$env:TEST_REPORT_NAME = 's3-1-backend'
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
```

No autogenerar sobre metadata parcial, borrar evidencias/volúmenes o ejecutar tests
sobre la base activa. Preservar cuatro cuentas/secretos Windows y locks; S4–S6 pendientes.
