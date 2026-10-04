# Estado de Sprint 6 — integración, instalación y recuperación local

Estado de cierre: **S6 COMPROBADO como sistema local integrado para simulación**.
Instalación, recuperación, persistencia y revisión activa pasaron con el código final.
Esta entrega implementa únicamente S6 para simulación SYNTHETIC. REAL permanece
bloqueado. No valida población escolar, eficacia, hipótesis ni aprobación académica.

Fecha de ejecución: 4 de octubre de 2026, instantes de evidencia en UTC y pantalla
en America/Lima. SHA inicial y HEAD final, sin commit:
`2029343f3540f7911cd07f6161c5e241f5696626`. Los cambios locales se identifican por
hashes de archivos, imágenes y evidencia; HEAD por sí solo no identifica el código
de esta entrega. No hubo push, publicación o despliegue externo.

## Cambios implementados

- ADR 009 previa a implementación: tres destinos y criterios independientes.
- `runtime_target.py`: destino obligatorio, identidad de proyecto/DB/volúmenes,
  imágenes, puertos loopback/origins y conexión riesgo_app; instalación,
  preparación explícita, parada y limpieza opcional con guards.
- `operator_profiles.py`: perfil ADMIN privado Windows ligado al destino,
  autenticación real antes de guardar y sin crear cuentas. `study.py` conserva
  ADMIN S2.2, lee solo ese acceso y exige destino; admite administrador propio
  con la política real del bootstrap. No sobrescribe las cuatro entradas.
- `backup_restore.py`/`windows_dpapi.py`: snapshot PostgreSQL consistente, dump
  custom, todos los archivos privados, cinco secretos de infraestructura,
  manifiesto/registro propio y protección DPAPI de usuario. Restauración nueva
  sin migrar/stamp/generador/refit/firma, con roles/grants y verificación HMAC.
- Runners S6: primera importación e inferencia UI, cuatro roles, seguimiento,
  CSV, periodo bloqueado real, caída real aislada, preservación y capturas.
  Reporter S6 registra fallos/status de login sanitizados; no cambia el histórico.
- Correcciones puntuales React: foco/enlace a historial y paginación móvil,
  contraste de fechas, conservación de borradores/conflictos aun si otro actor
  cierra el caso, estados terminales y texto vacío coherente con permisos.
- Nueve manuales consolidados, matriz/criterios/plan/AGENTS y notas operativas
  en manuales previos. No se reescriben cierres S0–S5, migraciones ni núcleo ML.
- OpenAPI mantiene **0.5.0 / 27 operaciones / 26 paths**. Solo se corrige la
  descripción histórica de predictions/run para reflejar seguimiento integrado;
  tipos regenerados, sin nuevas operaciones/campos. Alembic **0004_followup**,
  **15 tablas**. No cambia metodología, configuración de generación ni locks.

## Destinos distintos y código final

Descriptores/configuración privados en
`$env:LOCALAPPDATA\SeguimientoEscolar\S6`. Secretos nuevos montables en
`.local/s6-runtime/<proyecto>`, excluidos de Git y con ACL del usuario. Docker
Desktop no permitió los binds de archivos secretos desde AppData; descriptores
y backups permanecen fuera del checkout. Los cinco secretos activos originales
en `.local/runtime-secrets` permanecen intactos.

| Prueba | Descriptor | Proyecto / DB | Puertos web/API/DB | Prefijo público |
| --- | --- | --- | --- | --- |
| A instalación nueva | install-verified.json | s6-install-041bbf87a38b / s6_install_041bbf87a38b | 15273 / 18100 / 55462 | s6-install-verified |
| B recuperación actual | restore-final-code.json | s6-restore-a3a22654c1a2 / s6_restore_a3a22654c1a2 | 15274 / 18101 / 55463 | s6-restored-final |
| C revisión activa | active-verified.json | riesgo-escolar / riesgo_escolar | 15173 / 18000 / 55432 | s6-active-final |

A/B tienen tres volúmenes propios `<proyecto>_db_data`, `_import_data`, `_ml_data`;
UUID de propietario y red propia, sin consumidores ajenos. C conserva
`riesgo-escolar_db_data/import_data/ml_data`. Las copias anteriores se mantienen
identificables/detenidas; no se borran volúmenes ni se utiliza DEMO histórico.

Imágenes finales comprobadas:

| Servicio | ID SHA-256 |
| --- | --- |
| api | a0a9d26b7f04b5a31a19296e6def49682425fc83d471bc569d5b17285bf1b81e |
| web | 1578157e456ea957407ac4bb00488422e824f589b5c4f714daad68d962ee78ea |
| db | 567d5d704a3e5a4864393b623a0d50eb1b5a4ad134cdac7cf19555cb2d8ffe9e |

Versiones Docker: Python 3.12.12, PostgreSQL 17.6, Node 24.14.1/npm 11.20.0,
scikit-learn 1.9.1, xgboost-cpu 3.4.1. Host: Git 2.47.0.windows.1,
Docker 29.7.2, Compose 5.5.1 y `py -3.12` 3.12.0 para orquestación Windows.
El `python` de PATH del recolector inicial era 3.11.9; los comandos operativos
documentados usan el Launcher 3.12 y el backend mantiene su Python Docker fijado.
No se añaden dependencias ni se actualizan pins/hashes por conveniencia.

## A — instalación vacía y primer recorrido integrado

Base nueva hasta 0004, 15 tablas vacías antes de bootstrap, tres volúmenes y cinco
secretos propios. No se copian modelos/CSV/DB del activo. Preparación automática
exclusiva del destino mediante servicios reales: ADMIN propio con contraseña
válida de 16 caracteres (no se publica), TUTOR/DIRECTOR/RESEARCHER, contexto y
generación explícita semilla **1729**, versión sintética vigente. No se acredita
entrada manual de bootstrap ni hay cuentas predeterminadas.

Perfiles prueban autenticación propia, inválida/inactiva/no ADMIN y conservación
de S2.2. Generación repetida reutiliza UUID/CSV/hash; comparación/selección en
desarrollo, registro firmado y activación TECHNICAL_SIMULATION por CLI. La reserva
no elige algoritmo; no hay entrenamiento al arrancar ni en HTTP.

Primera importación desde Datos: CSV registrado privado, vista previa/detalle y
confirmación UI; después 60 estudiantes/60 matrículas/360 cortes y cero predicciones
antes de la primera evaluación. Primera inferencia por UI: 55 predicciones,
5 abstenciones y 51 casos; no rellena faltantes con LOW. TUTOR planifica dos
actividades, registra realizada/cancelada, comprueba conflicto real 409 conservando
borrador y concluye un caso. Roles/filtros/paginación/historial/CSV y periodo
bloqueado real comprobados. A final: **11/11 pruebas Playwright**, cuatro comprobaciones HTTP de perfiles,
15 tablas inicialmente vacías y destino conservado detenido. Final: 4 cuentas,
2 periodos (uno REAL vacío exclusivo para probar bloqueo), 60 estudiantes/matrículas,
360 cortes, 55 predicciones/decisiones, 51 casos, dos actividades, 212 eventos y
13 sesiones. SVM técnica elegida en desarrollo. CSV SHA-256
`79fedc114a952631977bbd46cabe5c5a76faeef7e7293e709d5a1a11c9b31374`.
[Runner A](../../tests/evidence/s6-install-verified-environment.json).

## B — respaldo completo y restauración sin reconstrucción

Paquete final privado:
`$env:LOCALAPPDATA\SeguimientoEscolar\Backups\s6-20261004T211105Z-f9190fd4851f.sebackup`.
Paquete: **416316 bytes**, SHA-256
`8cafb0836a0f2a1f39fa39884f01a25394a5dde8f8a8568dfd72a90d969ee11a`.
Ventana consistente UTC: 21:11:17.806405–21:11:47.200149 (29.39 s).
Su registro `.registered.json` y ACL restringidas se conservan. No se empaqueta
en Git ni se exporta Credential Manager. Hash/tamaño/ventana efectivos en
[backup final](../../tests/evidence/s6-backup-final-code.json).

Se pausan web/API previas; DB sigue disponible, bloqueo SHARE de 15 tablas y
Alembic/exported snapshot REPEATABLE READ. pg_dump custom escribe bytes binarios
desde Python. Fotografías DB/archivos antes/después coinciden dentro de la ventana.
finally libera/reanuda exactamente los escritores previos. Paquete contiene las
15 tablas, esquema/grants/roles, Alembic, **17 archivos** completos de ambos
volúmenes (CSV, payloads, cuatro artefactos/manifiestos y `.internal-key`), cinco
secretos de infraestructura y código/locks/imágenes. Los hashes de contraseñas
solo están en el dump cifrado, sin publicación individual.

DPAPI Windows nativo cifra/descifra y rechaza alteraciones. Solo paquetes propios
registrados: versión/inventario/hashes/tamaños/límites, rutas absolutas/traversal,
duplicados/enlaces rechazados antes de restaurar. Se conservan originales tras
los seis negativos derivados del paquete real. Temporales descifrados privados
se eliminan; backup cifrado e intentos identificados permanecen.

pg_restore con errores fatales restaura únicamente en DB nueva. Riesgo_owner se
recrea para inicialización/restauración/diagnóstico Alembic; riesgo_app permanece
sin superusuario/CREATE/DELETE/TRUNCATE. La API verifica usuario/base efectivos.
Antes de login **todas las tablas, Alembic, roles/esquema y 17 archivos coinciden**
exactamente con el manifiesto. CSRF/HMAC conservados; conexiones DB propias.
SVM recuperada verifica HMAC/compatibilidad, sin generar/refit/registro/activación.

Revisión B posterior: cuatro roles, contexto, procesamiento, estudiantes/historial,
modelo cargado, inferencia/sync reutilizados y CSV efectivos. Mantiene 55
predicciones/55 decisiones/51 casos, un caso concluido y dos actividades.
Solo nuevos accesos/exportaciones añaden auditoría/sesiones. DB se detiene
brevemente con web/API activos: health/ready 503 Health, consultas 503 Error
sanitizada, sin éxito falso, recuperación real al volver PostgreSQL.

La prueba de persistencia es distinta: stop/up de la copia, sin migrar, compara
otra vez todas las tablas/Alembic/esquema/roles y archivos. Resultado B: **329 eventos/74 sesiones** después de revisión (delta +13/+5),
5/5 pruebas navegador. Reinicio conserva todos esos registros y los 17 archivos
exactos. La copia queda detenida, con su descriptor y volúmenes, para inspección;
limpieza opcional no ejecutada.

## C — conservación activa

Antes S6: 4 cuentas, 60 estudiantes/matrículas, 360 cortes, 55 predicciones,
55 decisiones, 51 casos, dos actividades, 305 eventos de auditoría y 65 sesiones.
Fotografía del backup final: 316 eventos/69 sesiones después de primera revisión
S6 legítima; todas las otras huellas y los 17 archivos coinciden con inicio.
La revisión final C repite cuatro roles y reutilización, sin crear casos/actividades
ni editar estados/cuentas/cortes/modelos. Final C: **327 eventos/73 sesiones**, delta +11/+4 en revisión final, y +22/+8
respecto al inicio S6. Solo login/logout de cuatro roles y tres exportaciones
por cada revisión; ninguna mutación de seguimiento. Delta de accesos/exportaciones
se registra en [revisión C](../../tests/evidence/s6-active-final-environment.json).
También se comprueba conservación de las filas anteriores, no solo recuentos.
DEMO histórico permanece detenido y su respaldo anterior íntegro.

## Pruebas y límites de la evidencia

| Comprobación | Resultado / evidencia |
| --- | --- |
| Backend completo final PostgreSQL aislado, riesgo_app, Python 3.12.12/Linux | **269 aprobadas**, 0 fallos/errores/omisiones, 475.84 s; [JUnit](../../tests/evidence/s6-backend-final.xml) y entorno |
| Backend inicial S6 | 269 aprobadas, 298.06 s; se repitió después de cambios de guards/test launcher, no para mejorar métricas |
| Windows perfiles | **16 aprobadas**, incluyendo dos pruebas nativas Credential Manager; [informe](../../tests/evidence/s6-profiles-native.json) |
| Windows recuperación/DPAPI/ACL/guards | **29 aprobadas**, 0 fallos/errores/omisiones; [código final](../../tests/evidence/s6-recovery-tests-final-code.json), cuatro pruebas nativas de DPAPI/ACL y validadores/guards/mocks separados |
| Negativos paquete real | **6 aprobados**: bytes alterados, HMAC ausente, versión incompatible, dump alterado, copia externa, destino existente; original intacto |
| Contrato documental | **292 checks**, 15 tablas/119 campos/27 operaciones; [informe](../../tests/evidence/s6-contracts-verified-contracts.json). Sus 66 respuestas históricas no acreditan S6; checker valida nuevas respuestas S6 aparte |
| Tipos/typecheck/build Windows e imagen | Aprobados, assets host e imagen idénticos; [build](../../tests/evidence/s6-build-checks.json) |
| pip check / git diff --check | Aprobados; versiones, comandos/hashes en build/checker |
| Navegador A/B/C, PostgreSQL real y persistencia | **20/20 Playwright**: A 11, B 5, C 4; B todas las tablas/archivos iguales tras reinicio y detenido, A detenido, C healthy. Muestras nuevas validadas aparte |
| Visual 1440×900 / 768×1024 / 390×844 | **34 PNG finales realmente abiertos**, ocho antecedentes separados; [inventario de inspección](../../tests/evidence/s6-browser-visual-review.json), full-page puede tener mayor altura que viewport |
| Checker S6 actual | **COMPROBADO**, 1490 controles y 202 nuevas respuestas contractuales; [primera verificación aprobada](../../tests/evidence/s6-final-verification-candidate.json). Revalidación del cierre documental en `tests/evidence/s6-final-closure.json`; identidad/cobertura/código/DPAPI/destinos reales |

248 warnings backend existentes: deprecación Starlette TestClient/httpx y aviso
scikit-learn sobre parámetro probability de SVC. Se conserva SVC sin probabilidades
calibradas inventadas y no se actualizan pins. Las métricas de fixtures prueban
software, nunca resultados escolares. No hubo entrenamiento institucional.

## Fallos iniciales conservados y correcciones

1. Binds secretos AppData aparecían como directorios vacíos en Docker Desktop:
   instalación falló antes de precargas. Se usan secretos infraestructura privados
   Git-ignored montables en `.local/s6-runtime`; paquete/descriptor siguen fuera.
2. Compose poda un secreto owner no utilizado: derivación de migrador quedó con
   referencia indefinida. Configuración derivada lo declara explícitamente.
3. Casos mal tipados de manifiesto fallaban con AttributeError; validación de
   contenedores/tipos/canonical paths y rechazo de ZIP backslash se corrigieron.
   Informes iniciales de recuperación con fallos se conservan.
4. Primer restore usó create --no-deps, no soportado por Compose 5.5.1. Se usa
   create --no-recreate antes de cargar volúmenes. Copias fallidas detenidas.
5. Primera instalación integrada: locator de aviso seleccionaba también versión
   móvil oculta; se acota a main-content. Segunda completó tres roles y seguimiento
   pero falló RESEARCHER sin diagnóstico exacto registrado; no se atribuye 429
   como hecho. Reporter final añade status/posición sanitizados y ventanas
   completas entre fases para respetar login limits, sin desactivarlos.
6. Auxiliares docker run heredaron labels Compose api/activo y el guard de otra
   revisión concurrente rechazó sus montajes. Se fija project/service/oneoff
   propios de storage; guard estricto conservado y regresión/restore repetidos.
7. Build host inicial falló por spawn EPERM del sandbox; ejecución autorizada
   Windows aprobó. Recolector corrigió nombre de distribución xgboost-cpu/ruta
   assets/API Python y kwargs; no requirió cambio del producto.
8. Una ejecución del checker documental sin prefijo escribió el informe S5:
   se restauraron sus bytes originales desde HEAD y se comprobó igualdad exacta.
   Nuevos prefijos S6 evitan sobrescribir evidencia histórica.
9. Primer checker final rechazó un inventario incompleto de hashes: faltaban
   20 marcadores vacíos `.gitkeep`, sin diferencias de código. Se completa el
   inventario y se repite solo el checker; la aserción completa se conserva.
   Informe fallido `s6-final-verification-first.json` permanece separado.

No se convierten mocks HTTP 409/503/pérdida de respuesta en prueba de caída de DB.
Mocks de UI prueban borradores y ausencia de reintento; los 409 de versiones y
periodo bloqueado tienen pruebas separadas con API/PostgreSQL efectivos.
La suite final completa solo se repite ante cambios de backend relevantes; el
último fix de auxiliares stdlib se comprueba por pruebas Windows y restore real.

## Comandos PowerShell y reproducción

Desde la raíz, con Docker Desktop disponible. Los tres descriptores de este cierre
ya existen; no repetir create/restore sobre ellos ni sobrescribir informes.
Ver [instalación](../manuals/Manual_Instalacion_Windows.md) y
[respaldo](../manuals/Manual_Respaldo_Restauracion.md) para destinos y nombres nuevos.

```powershell
$s6Run = Get-Date -Format 'yyyyMMdd-HHmmss'
$s6Private = Join-Path $env:LOCALAPPDATA 'SeguimientoEscolar\S6'
$s6Active = Join-Path $s6Private 'active-verified.json'
$s6Install = Join-Path $s6Private 'install-verified.json'
$s6Restore = Join-Path $s6Private 'restore-final-code.json'
$s6Backup = Join-Path $env:LOCALAPPDATA 'SeguimientoEscolar\Backups\s6-20261004T211105Z-f9190fd4851f.sebackup'
py -3.12 infra/runtime_target.py identity --target $s6Active
py -3.12 infra/study.py status --target $s6Active --admin-credential ADMIN
# Inspección opcional de copia detenida; RESTORE no migra:
py -3.12 infra/runtime_target.py up --target $s6Restore
py -3.12 infra/runtime_target.py stop --target $s6Restore
# Comando efectivo de persistencia aislada, con informe nuevo:
py -3.12 infra/runtime_target.py up --target $s6Restore
py -3.12 infra/test_s6_persistence.py --target $s6Restore --report "tests/evidence/s6-$s6Run-persistence.json"

$env:TEST_REPORT_NAME = "s6-$s6Run-backend"
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
py -3.12 -X utf8 infra/test_s6_recovery.py --report "tests/evidence/s6-$s6Run-recovery.json"
py -3.12 -X utf8 -m unittest discover -s infra/tests -p test_s6_profiles.py -v
npm run generate:api --workspace frontend
npm run typecheck --workspace frontend
npm run build --workspace frontend
docker compose build web
docker compose exec -T api python -m pip check
$env:CONTRACT_REPORT_PREFIX = "s6-$s6Run"
.\.venv-s0\Scripts\python.exe infra/check_s0.py
# Checker de cierre: solo lee los tres destinos y la evidencia final.
.\.venv-s0\Scripts\python.exe infra/check_s6.py --active $s6Active --install $s6Install --restore $s6Restore --report "tests/evidence/s6-$s6Run-final.json"
git diff --check
```

No ejecutar checker de base vacía sobre activo/restauración poblados.
Respetar diez logins/IP/300 s; runners separan fases con ventanas reales,
no hacen reintentos de escrituras inciertas. Scripts leen accesos privados en
memoria y muestras/capturas no contienen contraseñas/tokens/particiones/etiquetas.

## Pendientes y límites reales

Requisitos institucionales/dataset/etiquetas/escalas/criterio/protocolo, calendario
de validación prospectiva, consentimiento/procedencia y revisión con asesor
permanecen pendientes. REAL bloqueado; simulación no acredita hipótesis/impacto.
No se prueba traslado DPAPI a otro usuario/equipo, recuperación ante pérdida del
perfil Windows, despliegue HTTPS externo, estrés productivo, auditoría integral
de seguridad/WCAG/lector de pantalla ni limpieza destructiva de copias conservadas.
No se avanza a otro sprint ni se crea S7.

Archivo de referencia: [matriz final](../manuals/Matriz_Trazabilidad_Final.md),
[índice de nueve manuales](../manuals/README.md), [ADR 009](../adr/009-integracion-recuperacion-s6.md).

## Inventario final de archivos y evidencia

[Archivos cambiados](../../tests/evidence/s6-changed-files-final.json) enumera modificaciones
reales frente al SHA inicial y archivos nuevos con hash (incluidas capturas y
resultados). Se agrupan en infraestructura/CLI, pruebas/runner/reporter, cuatro
ajustes React, tipos/descripcion contractual y documentación/manuales.
No hay cambios en locks, migraciones, núcleo ML ni cierres/evidencias históricos.
La evidencia final distingue A/B/C y los intentos anteriores; SHA final igual al
inicial porque no se creó commit. El checker revalida los archivos finales y
registra `code_tree_sha256`, hashes de locks/imágenes/informes y destinos.
