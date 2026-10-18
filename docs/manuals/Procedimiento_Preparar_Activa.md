# Procedimiento: dejar lista la instalación de siempre y la hermana de demostración

Lo ejecuta **el usuario**, en PowerShell, con Docker Desktop encendido. Todo se ensayó el 2026-10-18 sobre copias aisladas (nunca sobre la activa); los tiempos salen de esos ensayos.
Resultado: `riesgo-escolar` (15173) con **solo datos reales** (60 estudiantes, B1 y B2, modelo Random Forest) y `demo-vivo` (15174) con los mismos datos reales **más** el periodo
`DEMO-VIVO` para el registro en vivo. Guion: [Guion_Demo_Manual.md](Guion_Demo_Manual.md). Lista del día: [Lista_Dia_Sustentacion.md](Lista_Dia_Sustentacion.md).

**Reglas.** Nunca `docker compose down -v` ni borrar volúmenes. Nunca restaurar sobre la activa. Las contraseñas se escriben solo en el terminal cuando se piden. Nada de lo que imprime cada
paso lleva códigos ni nombres de estudiantes. Si un paso falla, **no sigas**: anota el código que imprime (por ejemplo `PRE_BACKUP_TOO_OLD`) y consulta la tabla del final.

## 0. Variables (en cada ventana de PowerShell)

```powershell
Set-Location C:\Users\mario\OneDrive\Escritorio\tesis-riesgo-escolar
$py = 'backend\.venv\Scripts\python.exe'
$base = "$env:LOCALAPPDATA\SeguimientoEscolar"; $s6 = "$base\S6"; $backups = "$base\Backups"
$entrada = "$base\ConversionExcelReal\salida"          # cortes.csv, cierres.csv y resumen_conversion.json
$fecha = Get-Date -Format yyyyMMdd-HHmmss
```

Estado de partida esperado (solo lectura): `docker compose ps` con `api`, `web` y `db` *healthy*; la base en `0008_real_chain`, 0 periodos, 4 cuentas.

## 1. Imágenes con el código final (≈ 1–3 min; la base no se detiene)

La activa corre un código anterior al bloque 5.1 (detección validada) y al rótulo de demostración. La comparación que se cargue debe llevar la detección validada, así que primero se reconstruyen las imágenes.

```powershell
docker tag riesgo-escolar-api:latest "riesgo-escolar-api:previo-$fecha"
docker tag riesgo-escolar-web:latest "riesgo-escolar-web:previo-$fecha"
docker compose build api web
docker compose stop api web
docker compose up -d --no-deps --wait api web
docker compose ps
```

Esperado: `api` y `web` *healthy*; `db` sin reiniciarse. Retroceso de imágenes: `docker tag riesgo-escolar-api:previo-<fecha> riesgo-escolar-api:latest` (igual con `web`) y repetir los dos últimos comandos.

## 2. Descriptor de la activa y perfil del ADMIN

```powershell
& $py infra\runtime_target.py active --output "$s6\active-$fecha.json"
& $py infra\operator_profiles.py register-profile --target "$s6\active-$fecha.json" --name riesgo-escolar
```

El segundo pide en el terminal el correo y la contraseña de **tu ADMIN de siempre** (no se imprimen ni se guardan en archivos; quedan en el Administrador de credenciales de Windows).

## 3. Respaldo verificado previo (≈ 1–2 min; la web y la API se pausan ~30 s)

El respaldo debe tener **menos de 24 h** y estar en 0008; la corrida real lo exige.

```powershell
& $py infra\backup_restore.py backup --target "$s6\active-$fecha.json" --report "$s6\antes-de-cargar-$fecha-respaldo.json"
```

Anota el `backup_file` que imprime (por ejemplo `s6-AAAAMMDDTHHMMSSZ-xxxxxxxxxxxx.sebackup`) y úsalo en el resto de los pasos:

```powershell
$respaldo = "$backups\s6-AAAAMMDDTHHMMSSZ-xxxxxxxxxxxx.sebackup"      # sustituye el nombre real
& $py infra\backup_restore.py verify --backup $respaldo --report "$s6\antes-de-cargar-$fecha-verificacion.json"
```

Esperado: `COMPROBADO`. (Etiqueta de origen: `SYNTHETIC`, porque aún no hay datos escolares.)

## 4. Decisión del tutor de las secciones 3.º A y B

- **Opción A (recomendada, mínimo privilegio; decidida por el usuario el 2026-10-18):** `--locked-tutor`. Crea una cuenta TUTOR de relleno que **nadie puede usar para iniciar sesión** (contraseña aleatoria desconocida); añade una quinta cuenta a las cuatro. Tu TUTOR real **no** ve datos reales.
- **Opción B:** un TUTOR existente. Obtiene acceso a los datos reales de esas secciones. Su identificador (solo cuentas, sin datos de estudiantes):

```powershell
"select id, email from risk_school.app_users where role='TUTOR' and is_active;" | docker exec -i riesgo-escolar-db-1 psql -U riesgo_owner -d riesgo_escolar -At
```

  y se usa `--tutor-a <id> --tutor-b <id>` en lugar de `--locked-tutor`. En la activa **nunca** se elige solo al único tutor existente; sin esta decisión la corrida se detiene antes de escribir.

## 5. Simulacro de la corrida real (≈ 1 min; solo inicia sesión)

```powershell
$resultados = "$base\ResultadosReales\activa-$(Get-Date -Format yyyy-MM-dd)"
& $py infra\run_real_study.py --target "$s6\active-$fecha.json" --operator-profile riesgo-escolar --input $entrada --results $resultados --dry-run --confirm-protocol --locked-tutor
```

Esperado: `preflight OK` (hashes de los CSV verificados, 120 filas, 60 estudiantes) y todos los demás pasos `PENDING`. No escribe datos.

## 6. Corrida real sobre la activa (≈ 8–11 min)

```powershell
& $py infra\run_real_study.py --target "$s6\active-$fecha.json" --operator-profile riesgo-escolar --input $entrada --results $resultados `
      --confirm-protocol --locked-tutor --confirm-active riesgo-escolar --pre-backup $respaldo --public-summary "$resultados\resumen_agregado_activa.json"
```

(Opción B: sustituye `--locked-tutor` por `--tutor-a <id> --tutor-b <id>`.) La orden se niega si falta `--confirm-active riesgo-escolar` o `--pre-backup`, si el respaldo no es de esta instalación, no está en 0008 o tiene
más de 24 h. Es reanudable e idempotente: si se corta, repite **la misma orden** (necesitará un respaldo de menos de 24 h; si pasó el plazo, repite el paso 3). Esperado, doce líneas:

`preflight OK · period DONE · sections DONE (created 2) · protocol DONE (confirmed) · study DONE (120 filas, 60 estudiantes) · import DONE (120) · closings DONE (120) · checks OK (B1 15/21/24, B2 25/11/24) · comparison DONE (RANDOM_FOREST, 20 repeticiones) · model DONE (LOCAL_EXPLORATORY) · evaluation DONE (alertas 45, simuladas 45) · indicators DONE (sql_matches_system true)`

## 7. Comprobaciones (solo lectura)

Resultado idéntico al de referencia (`real-tesis`): el resumen agregado debe coincidir exactamente.

```powershell
& $py infra\compare_real_summaries.py tests\evidence\mejoras-051-resumen-agregado.json "$resultados\resumen_agregado_activa.json"
```

Esperado: `IDENTICOS` (salida 0). Si imprime `DIFIEREN`, no la uses: copia la lista de rutas. Conteos directos en la base:

```powershell
@'
select 'periodos_REAL', count(*)::text from risk_school.academic_periods where data_origin='REAL'
union all select 'estudiantes', count(*)::text from risk_school.students
union all select 'estudiantes_con_nombre', count(*)::text from risk_school.students where full_name is not null and btrim(full_name) <> ''
union all select 'cortes', count(*)::text from risk_school.academic_snapshots
union all select 'referencias', count(*)::text from risk_school.risk_references
union all select 'predicciones', count(*)::text from risk_school.predictions
union all select 'alertas', count(*)::text from risk_school.alerts
union all select 'intervenciones', count(*)::text from risk_school.interventions
union all select 'modelos_activos', string_agg(algorithm||'/'||data_origin, ',') from risk_school.model_versions where is_active
union all select 'protocolos_confirmados', count(*)::text from risk_school.processing_protocols where authorization_confirmed_by_admin
union all select 'alembic', string_agg(version_num, ',') from public.alembic_version
order by 1;
'@ | docker exec -i riesgo-escolar-db-1 psql -U riesgo_owner -d riesgo_escolar -At -F ' = '
```

Esperado: `periodos_REAL = 1`, `estudiantes = 60`, `estudiantes_con_nombre = 0`, `cortes = 120`, `referencias = 120`, `predicciones = 120`, `alertas = 45`, `intervenciones = 0`,
`modelos_activos = RANDOM_FOREST/REAL`, `protocolos_confirmados = 1`, `alembic = 0008_real_chain`. En el navegador (<http://localhost:15173>): **Indicadores → REAL-2026 → B1**: «Detección validada» 87,3 % ± 2,4.

## 8. Respaldo posterior con datos reales (≈ 1–2 min) y comprobación opcional de restauración

```powershell
$fecha2 = Get-Date -Format yyyyMMdd-HHmmss
& $py infra\backup_restore.py backup --target "$s6\active-$fecha.json" --report "$s6\despues-de-cargar-$fecha2-respaldo.json"
```

Verifica el paquete nuevo (`verify`, como en el paso 3). Esperado: origen **REAL** (`data_origins = REAL`, alcance `REAL_INSTITUTIONAL`), `COMPROBADO`. Para comprobar que se puede restaurar (crea una copia local con los datos reales,
en puertos libres; **detenla al terminar, no la dejes encendida**):

```powershell
& $py infra\backup_restore.py restore-check --backup "$backups\<NUEVO>.sebackup" --output "$s6\copia-real-$fecha2.json" --web-port 15474 --api-port 18301 --db-port 55663 --confirm-real-copy --report "$s6\copia-real-$fecha2-informe.json"
& $py infra\runtime_target.py stop --target "$s6\copia-real-$fecha2.json"
```

Sin `--confirm-real-copy` la herramienta se niega: copiar datos reales a otro destino es una decisión explícita. Nunca se restaura sobre la activa.

## 9. Instalación hermana de demostración `demo-vivo` (≈ 20 min)

Mismo código y mismos datos reales, más el periodo `DEMO-VIVO` (estudio sintético rotulado; los 60 estudiantes sintéticos del generador vienen con él). La activa **no** se toca.

```powershell
$d = "$base\Instalaciones\demo-vivo"; New-Item -ItemType Directory -Force $d | Out-Null
& $py infra\runtime_target.py create --output "$d\destino.json" --web-port 15174 --api-port 18001 --db-port 55433
& $py infra\runtime_target.py up --target "$d\destino.json"
& $py infra\runtime_target.py bootstrap-admin --target "$d\destino.json"
& $py infra\operator_profiles.py register-profile --target "$d\destino.json" --name demo-vivo
```

(`bootstrap-admin` y `register-profile` piden el correo y la contraseña del ADMIN de la demostración **en el terminal**; anótalos aparte: serán los de la sustentación.) Luego la corrida real (sin protecciones de la activa, es un destino aislado) y el periodo de demostración:

```powershell
$proyecto = (Get-Content "$d\destino.json" -Raw | ConvertFrom-Json).project
& $py infra\run_real_study.py --target "$d\destino.json" --operator-profile demo-vivo --input $entrada --results "$base\ResultadosReales\demo-vivo" --confirm-protocol --locked-tutor --public-summary "$base\ResultadosReales\demo-vivo\resumen_agregado.json"
& $py infra\compare_real_summaries.py tests\evidence\mejoras-051-resumen-agregado.json "$base\ResultadosReales\demo-vivo\resumen_agregado.json"
& $py infra\prepare_demo_period.py --target "$d\destino.json" --operator-profile demo-vivo --confirm-demo-target $proyecto --locked-tutor --dry-run
& $py infra\prepare_demo_period.py --target "$d\destino.json" --operator-profile demo-vivo --confirm-demo-target $proyecto --locked-tutor
```

Esperado: `IDENTICOS`; el periodo de demostración imprime `study DONE · import DONE (360) · compare DONE (SVM) · model DONE (TECHNICAL_SIMULATION) · label DONE (DEMO-VIVO) · check OK (60 estudiantes sintéticos, SVM, SYNTHETIC)`.
El script se niega sobre la activa (`DEMO_ONLY_ISOLATED_TARGET`) y sin `--confirm-demo-target`. En <http://localhost:15174>: periodo **`DEMO-VIVO · 2025`** con el rótulo «Registro de demostración, no es dato del colegio».
Después haz el **ensayo general** con otros códigos (`ENSAYO-ALTO`, `ENSAYO-BAJO`); el guion usa `DEMO-ALTO`/`DEMO-BAJO`. Opcional: respaldo de `demo-vivo` (`backup --isolated-source`, etiqueta MIXED) como punto de partida del día.

## 10. Nombres en la ficha: paso opcional y separado (≈ 2 min)

Solo si quieres ver nombres en la **ficha** del estudiante (listas, alertas, indicadores y reportes nunca los muestran). Necesita un respaldo nuevo (< 24 h) y tu archivo real de identidades fuera del repositorio:

```powershell
& $py infra\convert_real_excel.py --excel "<tu libro>" --out "<carpeta fuera del repositorio>" --identities
& $py infra\load_identities.py --target "$s6\active-$fecha.json" --operator-profile riesgo-escolar --csv "<carpeta>\identidades.local.csv" --confirm-active riesgo-escolar --pre-backup $respaldo
```

Todo o nada; la auditoría guarda solo conteos. Ensayado con nombres inventados: aparecen únicamente en la ficha. **No lo ejecutes sin querer los nombres reales en el sistema.**

## Si algo no sale

| Código que imprime | Qué significa | Qué hacer |
|---|---|---|
| `ACTIVE_CONFIRMATION_REQUIRED` | Falta o no coincide `--confirm-active riesgo-escolar` | Repetir con el nombre exacto |
| `PRE_BACKUP_REQUIRED` / `PRE_BACKUP_TOO_OLD` | Falta el respaldo o tiene más de 24 h | Repetir el paso 3 y usar el nuevo |
| `PRE_BACKUP_NOT_AT_0008` / `PRE_BACKUP_OTHER_INSTALLATION` | Respaldo de otra versión o instalación | Respaldar la activa actual |
| `ACTIVE_TUTOR_EXPLICIT_REQUIRED` | No se decidió el tutor | `--locked-tutor` o `--tutor-a/--tutor-b` |
| `INPUT_HASH_MISMATCH` | Los CSV no son los registrados | No usar esos archivos; regenerar con el conversor |
| `TARGET_NOT_AT_0008` | La base no está en 0008 | Detenerse; no hay nada que escribir |
| `TARGET_RUNTIME_IMAGE_CHANGED` | El descriptor es anterior a la reconstrucción de imágenes | Repetir `runtime_target.py active --output <nuevo>` |
| `BACKUP_WRITER_IN_PROGRESS` | Hay una orden de estudio o migración en marcha | Esperar a que termine |
| `DEMO_ONLY_ISOLATED_TARGET` | Se apuntó el periodo de demostración a la activa | Es la protección; usar el destino `demo-vivo` |

## Retroceso, con honestidad

- **Nunca se restaura sobre la activa**: no existe «deshacer» sobre ella. Los pasos de carga son reanudables e idempotentes; una carga incompleta se completa repitiendo la orden.
- El plan de vuelta es **restaurar el último respaldo en una copia aislada** (`restore-check`, paso 8) para inspeccionar o comparar contra el estado anterior, no para reemplazar la activa.
- Si el resultado de la carga no es `IDENTICOS`, no lo uses en la sustentación: `real-tesis` (5173) sigue siendo la copia de referencia con la corrida verificada.

## Tiempos y espacio (medidos en los ensayos)

| Fase | Tiempo |
|---|---|
| Imágenes (paso 1) | 1–3 min |
| Respaldo y verificación (pasos 3 y 8) | 1–2 min cada uno |
| Corrida real (paso 6) | 8–11 min |
| Restauración de comprobación (paso 8) | 1–2 min |
| Instalación hermana completa (paso 9) | ≈ 20 min |

Espacio: la base real ocupa ≈ 51 MB; cada respaldo con datos reales ≈ 0,3 MB (reales) a 0,6 MB (reales + sintéticos); cada copia restaurada ≈ 52 MB. El disco tenía 118,8 GB libres.

## Limitaciones (obligatorias en cualquier uso de los resultados)

NIA e intervención oportuna reales no se calculan sin registros reales (quedan en «sin dato»); la procedencia de la recepción de registros (PRV: 126 recibidas, 6 rechazadas, 113 de 120 reportes) no está confirmada y no se informa;
el modelo es `LOCAL_EXPLORATORY` con 60 estudiantes y sin validación externa; las alertas reales son «simulación retrospectiva»; el periodo `DEMO-VIVO` es un registro de prueba en una instalación aparte. La restauración de un
respaldo con datos reales se ensayó en copias aisladas; no se ha ejecutado sobre la activa.
