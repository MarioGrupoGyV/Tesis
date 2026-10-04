# Instalación local en Windows

Este manual prepara una instalación nueva de Seguimiento Escolar para simulación.
REAL permanece bloqueado. El arranque no crea cuentas, periodos, estudiantes o
modelos; tampoco entrena. Una restauración desde respaldo es otro procedimiento:
consultar [respaldo y restauración](Manual_Respaldo_Restauracion.md).

La instalación activa conserva sus cuatro cuentas S2.2, puertos y volúmenes. No
ejecutar bootstrap sobre ella, no repetir `review_accounts.py`, no usar `down -v`
y no utilizar la antigua DEMO. Las pruebas S6 distinguen instalación nueva,
restauración aislada y revisión del activo en [Estado S6](../planning/Estado_Sprint_6.md).

## Requisitos y versiones

El operador utiliza PowerShell, Python Launcher y Docker Desktop en Windows.
Docker ejecuta Linux internamente; no hace falta una consola Bash, WSL o Make.
Los comandos se ejecutan desde la raíz del repositorio.

| Herramienta | Versión comprobada en el anfitrión S6 |
| --- | --- |
| Git | 2.47.0.windows.1 |
| Python Launcher `py -3.12` | Python 3.12.0; solo orquestación Windows |
| Docker | 29.7.2 |
| Docker Compose | 5.5.1 |
| Node / npm | 24.14.1 / 11.20.0 |

Las imágenes conservan Python **3.12.12**, PostgreSQL **17.6**, Node **24.14.1** y
npm **11.20.0**. API/ML y suite backend se ejecutan con ese Python Linux. React,
Vite, FastAPI, SQLAlchemy y dependencias mantienen los pins y hashes del
[ADR 001](../adr/001-arquitectura.md) y los locks del checkout; no ejecutar comandos
de actualización para preparar la instalación. XGBoost CPU 3.4.1 conserva su
dependencia fijada de S3. Consultar el inventario exacto en el cierre S6.

```powershell
git --version
py -3.12 --version
docker --version
docker compose version
node --version
npm --version
docker info
npm ci
docker compose build api web
```

`npm ci` respeta `package-lock.json`. El build de imágenes respeta las versiones y
`--require-hashes`. Docker Desktop debe estar disponible antes de continuar.

## Crear un destino nuevo explícito

El descriptor y Compose se guardan fuera del checkout, con permisos del usuario
Windows. Los cinco secretos de infraestructura del destino nuevo se guardan en
`.local/s6-runtime/<proyecto>`, con ACL privadas y exclusión Git comprobada. En
este entorno Docker Desktop comparte esa ubicación; los binds de archivos desde
AppData no resultaron utilizables. No es un archivo de cuentas ni incluye
contraseñas de usuarios. Respaldos, CSV exportado y artefactos permanecen fuera de
Git; el paquete de respaldo y su descriptor permanecen fuera del checkout.
El comando crea nombres S6 únicos y rechaza colisiones. Elegir puertos loopback libres diferentes de 15173, 18000 y
55432 del activo. Los siguientes son ejemplos para una instalación nueva:

```powershell
$installationDir = Join-Path $env:LOCALAPPDATA 'SeguimientoEscolar\Instalaciones\instalacion-propia'
$target = Join-Path $installationDir 'destino.json'
py -3.12 infra/runtime_target.py create --kind INSTALL --output $target --web-port 15273 --api-port 18100 --db-port 55462
py -3.12 infra/runtime_target.py up --target $target
py -3.12 infra/runtime_target.py identity --target $target
```

Conservar el resultado con proyecto, base, URL y nombres de los tres volúmenes.
`up` aplica Alembic hasta **0004_followup** mediante el propietario temporal y
arranca API/web. La API utiliza **riesgo_app**, nunca riesgo_owner. La base nueva
tiene 15 tablas de aplicación y comienza sin cuentas ni contexto. El chequeo de
identidad valida Compose, proyecto, volúmenes, imágenes, puertos y conexión real.

No editar el descriptor para apuntarlo al activo o a volúmenes anteriores. Cada
comando exige `--target`; no existe fallback a la URL activa. Abrir la `web_url`
devuelta por el comando, por ejemplo `http://localhost:15273`.

## Primer administrador elegido por el operador

Desde una terminal PowerShell interactiva:

```powershell
py -3.12 infra/runtime_target.py bootstrap-admin --target $target
```

Introducir correo, nombre y contraseña dos veces. La contraseña no se muestra, no
se pasa por argumentos y no se escribe en archivos. La política real del bootstrap
es **12–200 caracteres**; el operador elige el acceso. Usuario y auditoría se
guardan juntos. Si ya existe cualquier ADMIN, incluso inactivo, se rechaza la
repetición sin restablecerlo. No hay registro público ni valores predeterminados.

Las pruebas automatizadas S6 crean cuentas temporales exclusivamente en su destino
aislado mediante estos mismos servicios. Esa preparación programática no acredita
entrada manual ni constituye un acceso por defecto de una instalación del producto.

Para añadir usuarios autorizados después del administrador:

```powershell
py -3.12 infra/runtime_target.py configure --target $target
```

El operador se autentica como ADMIN y elige `usuario`, correo, nombre, rol y
contraseña privada. TUTOR, DIRECTOR y RESEARCHER conservan sus permisos vigentes.
Guardar el UUID público del tutor si se desea asignar la primera sección del
estudio sintético. Este comando también admite contexto REAL vacío; crearlo no
habilita importación ni procesamiento institucional.

## Registrar el acceso de operación en Windows

El launcher del estudio puede utilizar un ADMIN propio, sin depender de las cuatro
credenciales S2.2 ni de la política de 20 caracteres de sus fixtures. Registrar un
nombre nuevo, de 3–80 caracteres, con minúsculas, números, guion o guion bajo:

```powershell
py -3.12 infra/operator_profiles.py register-profile --target $target --name operador-propio
py -3.12 infra/study.py status --target $target --operator-profile operador-propio
```

El registro pide correo y contraseña con entrada privada. Verifica login,
`auth/me`, rol ADMIN activo y logout con CSRF contra ese destino antes de guardar.
No crea usuarios. Credenciales inválidas, cuenta inactiva o rol distinto de ADMIN
se rechazan. La entrada nueva pertenece a
`SeguimientoEscolar/Operadores/<nombre>` y queda vinculada a proyecto/base/URLs/tipo
de destino. No se sobrescriben entradas existentes; un perfil de otro destino se
rechaza. El almacén corresponde al usuario Windows actual.

Se conserva el acceso S2.2 con selección explícita:

```powershell
py -3.12 infra/study.py status --target $target --admin-credential ADMIN
```

Esta opción lee **solo** `SeguimientoEscolar/S2.2/ADMIN`. Es válida únicamente si
ese acceso ADMIN ya existe también en el destino elegido, como en la copia
restaurada. Una instalación nueva utiliza su administrador propio. Los dos flags
de acceso son mutuamente excluyentes. No incluir contraseñas en argumentos,
variables, JSON público, capturas o logs. El registro de un perfil no exporta
Credential Manager; los perfiles temporales de pruebas se limpian solo si fueron
creados por esa ejecución.

## Preparación explícita y primer recorrido sintético

Configuración versionada: `backend/app/ml/synthetic-study-v1.json`; generador
`synthetic-generator-v1`, semilla 1729. No cambiar escalas o semilla para mejorar
métricas. [Manual del estudio](Manual_Estudio_Sintetico.md) describe supuestos,
separación por estudiante, desarrollo/reserva y limitaciones académicas. Los
comandos siguientes pertenecen exclusivamente a la instalación nueva:

```powershell
# Añadir --tutor-id <UUID del tutor propio> si corresponde.
py -3.12 infra/study.py generate --target $target --operator-profile operador-propio --seed 1729
$studyId = '<study_id devuelto>'
$periodId = '<period_id devuelto>'
$csv = Join-Path $installationDir 'entrada-estudio.csv'
py -3.12 infra/study.py export-csv --target $target --operator-profile operador-propio --study-id $studyId --output $csv
```

El archivo es nuevo, fuera de Git, con hash comprobado y sin sobrescritura. No
contiene datos personales observados. Desde **Datos** en la interfaz: seleccionar
el periodo, elegir ese CSV registrado, revisar vista previa y confirmar. La vista
previa no crea estudiantes. La primera importación del recorrido S6 se realiza
en la interfaz, sin adelantarla mediante API. Comprobar Estudiantes y sus cortes.

Después de importar, ejecutar explícitamente:

```powershell
py -3.12 infra/study.py compare --target $target --operator-profile operador-propio --study-id $studyId
py -3.12 infra/study.py register --target $target --operator-profile operador-propio --study-id $studyId
$modelId = '<model_id devuelto>'
py -3.12 infra/study.py activate --target $target --operator-profile operador-propio --model-id $modelId
```

Se conservan cuatro algoritmos CPU, parámetros, desarrollo por grupos y reserva
temporal prefijada. El algoritmo seleccionado se determina con desarrollo antes de
mirar la reserva. Registro y activación son acciones técnicas de simulación; no
aprobación institucional. Repetir comparación reutiliza evidencia existente.

En **Modelos**, consultar el artefacto activo y evaluar el periodo desde la
interfaz. La primera inferencia S6 también se hace allí. Continuar Alertas →
planificar actividad → registrar realizada/cancelada → concluir/descartar caso →
historial → Reportes/CSV, según [manual de uso final](Manual_Uso_Final.md). Sin
evaluación o con datos insuficientes se muestra pendiente/abstención, nunca LOW
inventado. Toda actividad de este estudio es simulada.

El launcher conserva `import` y `run` para operaciones explícitas posteriores con
ADMIN, destino y CSRF; no son tareas de arranque ni sustituyen la evidencia del
primer recorrido UI. No generar, comparar o activar sobre el estudio activo para
acreditar una instalación nueva.

## Detener y volver a iniciar

```powershell
py -3.12 infra/runtime_target.py stop --target $target
py -3.12 infra/runtime_target.py up --target $target
```

Los tres volúmenes y secretos se conservan. No borrar carpetas de configuración,
volúmenes, la clave interna de ML o contraseñas de infraestructura. Conservar un
respaldo DPAPI comprobado; un reinicio no prueba restauración.

La limpieza posterior de un destino aislado S6 tiene un comando separado. **No se
ejecuta como parte del cierre ni del arranque**: elimina sus contenedores,
volúmenes y red, por lo que solo corresponde cuando ya se decidió retirar esa
instalación o copia de pruebas. Antes de usarlo, revisar el descriptor y conservar
un respaldo comprobado:

```powershell
# Acción posterior opcional, solo sobre un destino INSTALL/RESTORE S6 propio.
py -3.12 infra/runtime_target.py cleanup --target $target
```

El guard rechaza ACTIVE, volúmenes compartidos y recursos sin la identidad S6
esperada. Conserva descriptor, configuración privada, respaldo y evidencia para
identificación; no realiza borrado recursivo de archivos Windows. Para detener y
mantener el destino inspeccionable, utilizar únicamente `stop`.

## Errores comunes

| Diagnóstico | Acción |
| --- | --- |
| Docker no disponible | Iniciar Docker Desktop y comprobar `docker info` desde PowerShell. |
| TARGET_PORT_IN_USE | Elegir otros puertos antes de crear un descriptor nuevo; conservar los destinos existentes. |
| TARGET_DESCRIPTOR_EXISTS / TARGET_VOLUME_EXISTS | Usar una carpeta/nombre nuevo; no hay opción force para sobrescribir. |
| TARGET_RUNTIME_IMAGE_CHANGED / TARGET_COMPOSE_CHANGED | No editar configuración ni sustituir imágenes bajo el descriptor. Revisar identidad y el procedimiento de recuperación. |
| OPERATOR_PROFILE_EXISTS | Elegir otro nombre. No se restablece ni sobrescribe el acceso almacenado. |
| OPERATOR_PROFILE_TARGET_MISMATCH | Elegir el descriptor asociado o registrar un perfil nuevo para el destino correcto. |
| OPERATOR_ADMIN_AUTHENTICATION_REQUIRED | Comprobar en privado el acceso ADMIN activo existente en ese destino. El registro no crea ni reactiva cuentas. |
| OPERATOR_INTERACTIVE_TERMINAL_REQUIRED | Ejecutar el registro en una terminal interactiva; no usar archivos o redirecciones de contraseñas. |
| HTTP 429 de login | Esperar la ventana de 300 segundos. Límite: 10 intentos/IP, incluidos los correctos; no desactivarlo. |
| INSTITUTIONAL_PROCESSING_NOT_READY | Bloqueo esperado de REAL. Ningún flag o variable habilita el protocolo. |
| CSV_OUTPUT_EXISTS / CSV_OUTPUT_INSIDE_GIT | Elegir un archivo nuevo fuera del checkout en un directorio existente. |
| INSUFFICIENT_* al comparar | Revisar el diagnóstico/protocolo. No aumentar/regenerar población para fingir soporte o exactitud. |

Los comandos y resultados efectivamente ejecutados están en
[Estado S6](../planning/Estado_Sprint_6.md) y su matriz final. Los runners históricos
S0–S5 conservan evidencias y expectativas propias; no acreditan instalación o
recuperación S6 por encontrarse ya ejecutados. No ejecutar el checker de base vacía
en una aplicación poblada. HTTPS, tratamiento REAL, validación escolar, hipótesis y
revisión del asesor permanecen pendientes.
