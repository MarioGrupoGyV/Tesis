# Seguimiento Escolar

Sistema local integrado para **simulación con datos sintéticos**: acceso por roles,
importación versionada, estudiantes/historial, evaluación técnica, alertas,
actividades y reportes CSV. S6 comprueba instalación nueva, recuperación completa
y revisión activa por separado. Resultados en [Estado S6](docs/planning/Estado_Sprint_6.md)
y la [matriz final](docs/manuals/Matriz_Trazabilidad_Final.md).
REAL continúa bloqueado; el software y las métricas sintéticas no validan la tesis,
la eficacia escolar ni una aprobación institucional. Sin commit/push o despliegue externo.

## Guía de operación

Windows/PowerShell y Docker Desktop; Linux solo dentro de los contenedores.
No se requiere una consola WSL, Bash o Make. Versiones conservadas: Python
3.12.12/Linux, PostgreSQL 17.6, Node 24.14.1, npm 11.20.0, scikit-learn 1.9.1
y XGBoost CPU 3.4.1. Launcher del host Python 3.12.0; no sustituye el backend.

1. [Instalación Windows](docs/manuals/Manual_Instalacion_Windows.md): destino nuevo,
   bootstrap propio, perfil ADMIN privado y preparación sintética explícita.
2. [Uso por roles](docs/manuals/Manual_Uso_Final.md): importar, evaluar, atender
   un caso y exportar; fechas Lima, null, abstención y versiones.
3. [Respaldo/restauración](docs/manuals/Manual_Respaldo_Restauracion.md): paquete
   privado DPAPI, copia aislada sin regeneración y parada/limpieza con guards.
4. [Índice técnico y presentación](docs/manuals/README.md): arquitectura,
   diccionario efectivo, endpoints, trazabilidad, guion y límites.

## Conservar la instalación activa

Proyecto `riesgo-escolar`, DB `riesgo_escolar`, puertos loopback
15173/18000/55432, volúmenes `riesgo-escolar_db_data`, `riesgo-escolar_import_data`
y `riesgo-escolar_ml_data`. Abrir http://localhost:15173.
Cinco secretos actuales en `.local/runtime-secrets`, excluidos de Git.
Se conservan cuatro cuentas S2.2 y accesos privados Windows
`SeguimientoEscolar/S2.2/<ROL>`. No repetir bootstrap/preparación de cuentas,
restablecer contraseñas ni ejecutar `review_accounts.py` en esta instalación.
Su [cierre S2.2](docs/planning/Estado_Sprint_2_2.md) conserva identidad y evidencia.

El launcher exige destino explícito y lee únicamente ADMIN:

```powershell
$s6Run = Get-Date -Format 'yyyyMMdd-HHmmss'
$s6Active = Join-Path $env:LOCALAPPDATA "SeguimientoEscolar\S6\active-$s6Run.json"
py -3.12 infra/runtime_target.py active --output $s6Active
py -3.12 infra/study.py status --target $s6Active --admin-credential ADMIN
```

Una instalación nueva utiliza un perfil separado autenticado contra su destino
antes de guardarse en Windows. Ese registro no crea usuarios ni aplica la longitud
de fixtures S2.2. Comandos de generación/comparación/activación en el manual de
instalación: no repetirlos en activo. El CSV registrado se exporta a un archivo
nuevo fuera de Git, con hash y creación exclusiva. Sin entrenamiento HTTP o al arrancar.

```powershell
docker compose ps
docker compose up -d --wait
docker compose stop
```

Conservar secretos y volúmenes. No usar `down -v`, SQL destructivo o checker de
base vacía sobre la aplicación poblada. DEMO histórico permanece detenido y respaldado.

## Comprobaciones reproducibles

Usar prefijos nuevos para conservar evidencia:

```powershell
$s6Run = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:TEST_REPORT_NAME = "s6-$s6Run-backend"
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
py -3.12 -X utf8 infra/test_s6_recovery.py --report "tests/evidence/s6-$s6Run-recovery.json"
py -3.12 -X utf8 -m unittest discover -s infra/tests -p test_s6_profiles.py
npm run generate:api --workspace frontend
npm run typecheck --workspace frontend
npm run build --workspace frontend
$env:CONTRACT_REPORT_PREFIX = "s6-$s6Run"
.\.venv-s0\Scripts\python.exe infra/check_s0.py
docker compose exec -T api python -m pip check
git diff --check
```

Herramienta documental: crear `.venv-s0` e instalar `infra/requirements-s0.txt`
con `--require-hashes` si falta. Backend crea PostgreSQL aislado nuevo y ejecuta
como riesgo_app; fixtures no son resultados escolares. Navegador requiere Chromium
instalado por Playwright. Destinos y comandos efectivos en Estado S6; un BASE
implícito no acredita aislamiento. Respetar diez logins/IP por 300 segundos.

## Contratos y límites

[OpenAPI 0.5.0](docs/planning/Contrato_API.yaml): 27 operaciones/26 paths.
Alembic `0004_followup`: 15 tablas de aplicación más tabla de revisión.
No cambian DB/API por editar scripts/manuales. [Esquema.sql](docs/planning/Esquema.sql)
es referencia: no ejecutarlo para sustituir migraciones. CSV/ML permanecen privados.
Cookie HttpOnly, CSRF, roles/sección se validan en servidor. 503 Error sanitizada;
health/ready conserva Health. Integridad/versiones son conflictos 409.

Correcciones crean revisiones; evidencia/predicciones/auditoría no se sobrescriben.
Sin evaluación o datos suficientes el riesgo es null. ML selecciona en desarrollo
por estudiante, sin reserva en fit/selección o probabilidades calibradas inventadas.
Una actividad planificada no equivale a realizada ni demuestra mejoría.
CSV cuenta el alcance autorizado, sin notas libres/etiquetas privadas.

Decisiones en [ADR 009](docs/adr/009-integracion-recuperacion-s6.md),
[plan](docs/planning/Plan_tesis_riesgo_escolar.md) y
[criterios](docs/planning/Sprints_y_aceptacion.md). Cierres S0–S5 intactos.
HTTPS, protocolo de datos, validación académica y continuidad en otro equipo
requieren trabajo/autorizaciones posteriores; no se propone un S7.
