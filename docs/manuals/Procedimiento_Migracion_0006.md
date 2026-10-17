# Procedimiento: aplicar la migración 0006 a la instalación activa

**Redactado el 2026-10-17; NO ejecutado.** Solo lo ejecuta el operador, con el respaldo
verificado. La migración `0006_manual_evaluable` solo reemplaza tres funciones PL/pgSQL
(`deny_manual_prediction`, `check_prediction_study`, `check_followup_provenance`) y sus
grants: **no modifica ni borra filas, tablas ni columnas**. Alembic no admite downgrade
(el `downgrade()` lo rechaza a propósito). Efecto: las mediciones MANUAL de periodos
SYNTHETIC pueden evaluarse; REAL conserva el bloqueo. Ver
[ADR 011](../adr/011-fase-mejoras-tesis.md) y [Registro_Manual_M1.md](Registro_Manual_M1.md).

Reglas: desde la raíz en PowerShell; sin `docker compose down -v`; sin bootstrap ni
`review_accounts.py`; sin restablecer contraseñas; nunca restaurar sobre el activo.

## 0. Precondiciones

1. Estado actual en `0005_manual_academic` (si ya está en `0006_manual_evaluable`, no hay nada que hacer).
2. La rama con el código del Bloque 1 está en el checkout, con las pruebas backend en verde.
3. Nadie ejecuta importaciones ni comandos del estudio durante el procedimiento.

```powershell
docker compose ps
docker compose exec -T db psql -U riesgo_owner -d riesgo_escolar -Atc "SELECT version_num FROM public.alembic_version"
```

Debe mostrar los tres servicios *running* y `0005_manual_academic`.

## 1. Respaldo previo verificado

`backup_restore.py` reconoce ahora las cabeceras 0004, 0005 y 0006 y registra la vigente.

```powershell
$run = Get-Date -Format 'yyyyMMdd-HHmmss'
$active = Join-Path $env:LOCALAPPDATA "SeguimientoEscolar\S6\active-$run.json"
py -3.12 infra/runtime_target.py active --output $active
py -3.12 infra/backup_restore.py backup --target $active --report "tests/evidence/pre0006-$run-backup.json"
# Sustituir NOMBRE por el paquete devuelto:
$backup = Join-Path $env:LOCALAPPDATA 'SeguimientoEscolar\Backups\NOMBRE.sebackup'
py -3.12 infra/backup_restore.py verify --backup $backup --report "tests/evidence/pre0006-$run-verify.json"
```

**No continuar** si `backup` o `verify` no terminan con estado COMPROBADO. Opcional y
recomendado: comprobar la restauración en una copia aislada
(`restore-check`, ver [Manual_Respaldo_Restauracion.md](Manual_Respaldo_Restauracion.md)).

## 2. Conservar las imágenes actuales (para volver atrás)

```powershell
docker tag riesgo-escolar-api:latest riesgo-escolar-api:pre-0006
docker tag riesgo-escolar-web:latest riesgo-escolar-web:pre-0006
docker compose build api web
```

## 3. Aplicar la migración

El contenedor efímero recibe el secreto de propietario solo durante este comando:

```powershell
docker compose -f compose.yaml -f infra/compose.migrate.yaml run --rm --no-deps api python -m alembic -c /app/alembic.ini upgrade head
docker compose up -d --wait api web
```

## 4. Comprobar que quedó aplicada

```powershell
docker compose exec -T db psql -U riesgo_owner -d riesgo_escolar -Atc "SELECT version_num FROM public.alembic_version"
docker compose exec -T db psql -U riesgo_owner -d riesgo_escolar -Atc "SELECT proname, prosrc LIKE '%MANUAL%' FROM pg_proc WHERE proname IN ('deny_manual_prediction','check_prediction_study','check_followup_provenance') ORDER BY 1"
docker compose exec -T db psql -U riesgo_owner -d riesgo_escolar -Atc "SELECT count(*) FROM pg_trigger WHERE tgname IN ('m1_prediction_guard','prediction_study_guard')"
docker compose ps
```

Esperado: `0006_manual_evaluable`; las tres funciones con `t` (en 0005 `check_prediction_study` y
`check_followup_provenance` no mencionaban MANUAL); 2 triggers; servicios *healthy*. Comparar además los conteos de
estudiantes, mediciones, predicciones y alertas con el reporte del respaldo: deben ser iguales
(la migración no cambia datos). Abrir http://localhost:15173 e iniciar sesión con una cuenta
existente; no se crean cuentas.

## 5. Si algo falla

| Situación | Acción |
|---|---|
| La migración falla antes de terminar | PostgreSQL ejecuta este DDL dentro de una transacción de Alembic: la base debe quedar en 0005 (confirmarlo con la consulta del paso 4). Volver a las imágenes `pre-0006` (abajo) y revisar el error. |
| La migración terminó pero la aplicación falla | El cambio de BD es compatible hacia atrás (relaja guardas que el código anterior nunca ejercita). Basta volver a las imágenes anteriores. |
| Hay que descartar el estado de la BD | **No restaurar sobre el activo.** Usar `restore-check` con el respaldo del paso 1 para crear una copia nueva y operar desde ella según el manual de respaldo; el activo y sus volúmenes se conservan intactos para análisis. |

Volver a las imágenes anteriores (sin tocar volúmenes ni la BD):

```powershell
docker tag riesgo-escolar-api:pre-0006 riesgo-escolar-api:latest
docker tag riesgo-escolar-web:pre-0006 riesgo-escolar-web:latest
docker compose up -d --wait --force-recreate api web
```

Conservar el paquete de respaldo y los reportes `pre0006-*`. Registrar fecha y resultado
de la ejecución real en un estado nuevo en `docs/planning/`; este documento solo es el procedimiento.
