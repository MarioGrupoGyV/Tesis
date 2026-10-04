# Respaldo y restauración desde PowerShell

La herramienta S6 respalda el estado actual completo y lo restaura únicamente en
un destino nuevo. No ejecutar `infra/history/archive_s2.py`: corresponde al entorno
histórico y no incluye ML/seguimiento actuales. Los resultados efectivos se registran
en [Estado S6](../planning/Estado_Sprint_6.md); la [ADR 009](../adr/009-integracion-recuperacion-s6.md)
define las tres verificaciones distintas.

## Preparar y respaldar

Usar Windows, Docker Desktop y el mismo usuario Windows que conserva los accesos.
El paquete se guarda en `$env:LOCALAPPDATA\SeguimientoEscolar\Backups`, fuera del
checkout. El directorio restringe herencia y concede acceso al usuario actual.
DPAPI protege el paquete completo, incluidos los secretos internos, usando
[CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
y [CryptUnprotectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata).
Se usa protección del usuario, sin LOCAL_MACHINE. La recuperación está ligada
normalmente al mismo usuario/equipo; no se promete portabilidad a otro perfil/PC.
Conservar el perfil Windows y sus condiciones de recuperación DPAPI, el paquete,
su registro `.registered.json`, el código/locks y las imágenes identificadas.
No exportar Credential Manager ni compartir el paquete en Git.

```powershell
$s6Private = Join-Path $env:LOCALAPPDATA 'SeguimientoEscolar\S6'
$s6Run = Get-Date -Format 'yyyyMMdd-HHmmss'
$s6Active = Join-Path $s6Private "active-$s6Run.json"
py -3.12 infra/runtime_target.py active --output $s6Active
py -3.12 infra/backup_restore.py backup --target $s6Active --report "tests/evidence/s6-$s6Run-backup.json"
```

La salida muestra el nombre nuevo del paquete, nunca contraseñas o datos. Sustituir
el nombre del ejemplo siguiente por el devuelto. No se sobrescriben backups/reportes.

```powershell
$s6Backup = Join-Path $env:LOCALAPPDATA 'SeguimientoEscolar\Backups\NOMBRE.sebackup'
py -3.12 infra/backup_restore.py verify --backup $s6Backup --report "tests/evidence/s6-$s6Run-verify.json"
```

Se comprueban comandos de estudio/importación, se pausan los escritores que estaban
activos y una transacción SHARE exporta el snapshot para pg_dump custom. PostgreSQL
permanece disponible. DB, Alembic y archivos se fotografían dentro de esa ventana;
se comparan antes/después. finally reanuda exactamente los servicios previos,
sin arrancar dependencias que estaban detenidas. El dump se escribe como bytes desde
Python, sin piping PowerShell. Un fallo conserva un intento `.partial/attempt.json`
identificado; no se anuncia respaldo completo. No ejecutar otro comando del estudio
durante esta breve ventana ni iniciar escritores externos sobre sus volúmenes.

El inventario incluye las 15 tablas, usuarios/sesiones/auditoría/decisiones,
Alembic, definición de esquema/grants y roles; todos los archivos import_data/ml_data
(también `.internal-key`, payload, CSV y artefactos); cinco secretos de infraestructura.
Los hashes de contraseñas permanecen dentro del dump cifrado; no se publican por usuario.
No se archivan el checkout, todo `.local`, Credential Manager ni la antigua DEMO.

## Recuperar en una copia nueva

Los puertos del ejemplo deben estar libres; los binds siempre son 127.0.0.1.
No generar previamente ese destino: restore-check lo crea y rechaza existentes.

```powershell
$s6Restore = Join-Path $s6Private "restore-$s6Run.json"
py -3.12 infra/backup_restore.py restore-check --backup $s6Backup --output $s6Restore --web-port 15274 --api-port 18101 --db-port 55463 --report "tests/evidence/s6-$s6Run-restore.json"
```

La herramienta solo reconoce paquetes propios registrados. Valida versión, inventario,
hashes, tamaños/límites y rutas antes de crear la copia. Rechaza absolutos, traversal,
duplicados, enlaces y corrupción. Crea DB/roles y tres volúmenes con nombres S6 nuevos;
pg_restore restaura esquema, ownership y ACL con errores fatales. No migra tablas antes,
no usa stamp y no restaura sobre el activo. riesgo_owner se usa para restauración y
diagnóstico Alembic; la API usa riesgo_app sin superusuario/CREATE/DELETE/TRUNCATE.
Las claves de artefactos y CSRF se conservan; contraseñas/URLs DB nuevas aíslan la copia.
Los secretos montables nuevos están en `.local/s6-runtime/<proyecto>`, privados y
excluidos de Git. Este Docker Desktop no admite los binds de archivo secretos en AppData;
los descriptores/paquetes continúan fuera del checkout.

Antes de login compara todas las tablas, Alembic, roles/esquema y todos los archivos
contra el manifiesto. Verifica HMAC y compatibilidad sin reentrenar, firmar o activar.
Los temporales descifrados se limpian. La copia arrancada permite revisión posterior:

```powershell
py -3.12 infra/review_s6.py --target $s6Restore --study-id e3a2d28b-2f23-56ae-878c-1a8f4a257e7e --period-id c036cbcb-87db-5ed0-bcfa-bbd644928ccb --prefix "s6-$s6Run-restored" --outage
py -3.12 infra/runtime_target.py stop --target $s6Restore
```

Esos UUID identifican el estado S5 respaldado, no una instalación nueva. La revisión
reutiliza las cuatro entradas Windows S2.2 contra esta copia; login/logout agregan
sesiones/auditoría legítimas separadas de la fotografía previa. Inferencia/sync reutilizan
55 resultados/decisiones y mantienen 51 casos y dos actividades. La caída real de DB
solo está permitida en copia aislada y se recupera con finally; no usarla en activo.
Respetar 10 logins/IP por 300 segundos; no desactivar el límite.

## Inspección y limpieza posterior

La copia se conserva detenida con descriptor, volúmenes y evidencias identificables.
Para inspeccionarla: `py -3.12 infra/runtime_target.py up --target $s6Restore`.
RESTORE no ejecuta migraciones ni preparación. Detenerla al terminar.
La limpieza posterior es opcional y destructiva solo para esos recursos nuevos:

```powershell
py -3.12 infra/runtime_target.py cleanup --target $s6Restore
```

Comprueba identidad/etiquetas/volúmenes y ausencia de consumidores ajenos; rechaza
ACTIVE y recursos compartidos. No utiliza force o down -v; conserva descriptor,
configuración privada y backup. Este comando se documenta, sin afirmar su ejecución
en las copias conservadas. No borrar recursos usando nombres calculados fuera del guard.
El respaldo DPAPI local no acredita continuidad institucional, alta disponibilidad,
seguridad completa ni recuperación en otro equipo. REAL permanece bloqueado.
