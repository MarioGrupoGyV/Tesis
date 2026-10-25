# Lista para el ensayo general y el día de la sustentación

Sistemas: `riesgo-escolar` (<http://localhost:15173>, la instalación de siempre, **solo datos reales**) y `demo-vivo` (<http://localhost:15174>, mismos datos reales **más** el periodo `DEMO-VIVO` para el registro en vivo).
`real-tesis` (<http://localhost:5173>) es la copia de referencia de la corrida real: úsala solo para comparar, no para presentar. Guion: [Guion_Demo_Manual.md](Guion_Demo_Manual.md).
Preparación previa: [Procedimiento_Preparar_Activa.md](Procedimiento_Preparar_Activa.md). **No hace falta internet** para nada de esto.

## El día anterior (ensayo general, con tiempo)

- [ ] Docker Desktop encendido. En la raíz del repositorio: `docker compose ps` → `api`, `web` y `db` *healthy* (la instalación de siempre).
- [ ] Encender `demo-vivo` si está detenida y comprobar su salud:

```powershell
Set-Location C:\Users\mario\OneDrive\Escritorio\tesis-riesgo-escolar
$py = 'backend\.venv\Scripts\python.exe'; $s6 = "$env:LOCALAPPDATA\SeguimientoEscolar\S6"
$demo = Get-ChildItem "$s6\demo-vivo-v9u-*.json" | Where-Object { $_.Name -notlike '*-restore.json' } | Select-Object -First 1 -ExpandProperty FullName
& $py infra\runtime_target.py up --target $demo
docker ps --format "{{.Names}} | {{.Status}}"
```

- [ ] Abrir <http://localhost:15174>, iniciar sesión (ADMIN de la demostración) y recorrer **toda la parte B con códigos de ensayo** (`ENSAYO-ALTO`, `ENSAYO-MEDIO`, `ENSAYO-BAJO`), cronometrando. Resultado esperado: Alto y Medio con caso, Bajo sin caso,
  y «Modelo: SVM del estudio real» junto al resultado. En **Modelos** debe estar activa «SVM del estudio real (copia de demostración)».
- [ ] Abrir <http://localhost:15173> y comprobar **Indicadores → REAL-2026 → B1/B2**: detección validada 86,2 % ± 1,6 (B1) y 100 % ± 0 (B2) del SVM; PDER «en muestra» 100 %; 40 alertas.
- [ ] Hacer un **respaldo del día** de cada instalación (`backup_restore.py backup`; para `demo-vivo`, con `--isolated-source`) y verificarlo (`verify`). Anotar los nombres de los paquetes.
- [ ] Revisar que las **capturas del plan B** abren (`tests\evidence\mejoras-09-e2e-*`, `mejoras-09-demo-vivo-*` y `mejoras-09-principal-*`).
- [ ] Equipo: batería al 100 % y cargador, modo «no suspender», notificaciones silenciadas, zoom del navegador al 100 %, una sola sesión del navegador por sistema, proyector probado.

## El día, 30 minutos antes

- [ ] `docker ps` → los contenedores de `riesgo-escolar` y de `demo-vivo` en *healthy*. Si `demo-vivo` no está: `runtime_target.py up --target $demo` (nunca `down -v`).
- [ ] Sesión iniciada en las dos pestañas: 15173 (parte A) y 15174 (parte B), cada una con su ADMIN. En 15174, periodo **`DEMO-VIVO · 2025`** ya elegido y visible el rótulo «Registro de demostración, no es dato del colegio».
- [ ] La demostración del día usa `DEMO-ALTO`, `DEMO-MEDIO` y `DEMO-BAJO`: confirmar que **no existen todavía** en `DEMO-VIVO`. Si existen, añadir `-2`.
- [ ] Capturas del plan B abiertas en una ventana aparte, sin datos por alumno.
- [ ] Este guion impreso o en una segunda pantalla.

## Qué NO abrir ni mostrar

- **Fichas de estudiantes de `REAL-2026`** (si algún día se cargan los nombres, solo se ven en la ficha) y las listas de `REAL-2026`: llevan códigos reales.
- La carpeta `%LOCALAPPDATA%\SeguimientoEscolar\ResultadosReales` (CSV por alumno, informes completos) y `ConversionExcelReal`.
- La carpeta de respaldos `Backups` y cualquier copia restaurada con datos reales (`restore-check`): contienen datos de menores.
- Credenciales: no proyectar el Administrador de credenciales ni el terminal con los comandos del procedimiento.

## Si algo falla durante la sustentación

1. Mantener la calma y pasar al **plan B** (capturas revisadas del mismo recorrido). Decirlo con naturalidad: «lo vemos en las capturas del ensayo».
2. Error 5xx o sin respuesta: `docker compose ps` (instalación de siempre) o `docker ps` (demo-vivo); reiniciar solo `api` y `web` con `docker compose restart api web`. Nunca `down -v` ni detener la base.
3. El periodo `DEMO-VIVO` no aparece: estás en 15173; cambiar a 15174.

## Después

- [ ] Detener `demo-vivo` si no se usa más: `runtime_target.py stop --target $demo` (sin borrar volúmenes).
- [ ] No dejar encendidas copias restauradas con datos reales.
- [ ] Conservar el último respaldo verificado de cada instalación. Están protegidos con DPAPI: solo se abren con tu usuario de Windows en este equipo; copiarlos a otro equipo no permite restaurarlos allí.
