# Corrida real (Bloque 5)

Carga los datos reales ya convertidos ([Conversor_Excel_Real.md](Conversor_Excel_Real.md)) en un destino **aislado** `real-tesis` y ejecuta dentro del
sistema la comparación de modelos, la activación del modelo, la evaluación **retrospectiva** de B1 y B2 y los indicadores. No toca la instalación
activa ni otros destinos, salvo que el usuario lo pida expresamente (ver «Cargar en la instalación de siempre»). Todo lo que tiene filas por alumno vive fuera del repositorio; al repo solo entra el resumen agregado
(`tests/evidence/mejoras-05-resumen-agregado.json`: conteos y métricas globales, sin códigos ni nombres).

**Lectura correcta de los resultados:** simulación retrospectiva con datos reales del colegio; **no mide impacto del sistema**. Las alertas se
generaron ahora, con un modelo ajustado con los mismos estudiantes, sobre cortes pasados.

## Pasos (PowerShell, desde la raíz del repositorio)

1. **Imágenes y destino** (una vez). El destino publica la web en el **5173**: antes hay que cerrar el servidor de desarrollo de Vite (`npm run dev`), que usa ese mismo puerto; la instalación de siempre sigue en el 15173:

   ```powershell
   docker build -t riesgo-escolar-api:b5 -f infra/docker/api.Dockerfile .
   docker build -t riesgo-escolar-web:b5 -f infra/docker/web.Dockerfile .
   $d = "$env:LOCALAPPDATA\SeguimientoEscolar\Instalaciones\real-tesis"; New-Item -ItemType Directory -Force $d
   backend\.venv\Scripts\python.exe infra\runtime_target.py create --output "$d\destino.json" --web-port 5173 --api-port 18320 --db-port 55680 --image-tag b5
   backend\.venv\Scripts\python.exe infra\runtime_target.py up --target "$d\destino.json"
   ```

2. **Administrador y perfil** (una vez; la contraseña se escribe en el terminal, nunca en argumentos):

   ```powershell
   backend\.venv\Scripts\python.exe infra\runtime_target.py bootstrap-admin --target "$d\destino.json"
   backend\.venv\Scripts\python.exe infra\operator_profiles.py register-profile --target "$d\destino.json" --name real-tesis
   ```

3. **Entradas:** `cortes.csv`, `cierres.csv` y `resumen_conversion.json` del conversor, en
   `%LOCALAPPDATA%\SeguimientoEscolar\ConversionExcelReal\salida`.

4. **Corrida** (reanudable e idempotente; si un paso ya está hecho lo reconoce y no lo repite):

   ```powershell
   $r = "$env:LOCALAPPDATA\SeguimientoEscolar\ResultadosReales\$(Get-Date -Format yyyy-MM-dd)"
   $e = "$env:LOCALAPPDATA\SeguimientoEscolar\ConversionExcelReal\salida"
   backend\.venv\Scripts\python.exe infra\run_real_study.py --target "$d\destino.json" --operator-profile real-tesis --input $e --results $r --dry-run
   backend\.venv\Scripts\python.exe infra\run_real_study.py --target "$d\destino.json" --operator-profile real-tesis --input $e --results $r --confirm-protocol --locked-tutor --public-summary tests\evidence\mejoras-05-resumen-agregado.json
   ```

   - `--dry-run` valida archivos (SHA-256 contra `resumen_conversion.json`), destino en 0008 y estado de cada paso **sin escribir nada**.
   - El protocolo REAL solo se confirma con `--confirm-protocol` (acción del ADMIN, con auditoría de actor y fecha UTC).
   - `--locked-tutor` crea, si no hay tutores, una cuenta TUTOR de relleno con contraseña aleatoria que nadie conoce (solo para que existan las secciones 3.º A y B).
   - `--results` y `--input` se rechazan si están dentro de Git.

   Pasos: periodo `REAL-2026` y secciones → protocolo → estudio institucional (hash de `cortes.csv`) → importación → cierres (RIESGO_V1 lo calcula el
   backend) → comprobación 120 cortes / 60 estudiantes / 120 referencias y distribución de riesgo (se detiene si difiere de `resumen_conversion.json`) →
   comparación → registro y activación del modelo → evaluación retrospectiva de B1 y B2 (`as_of` = disponibilidad del corte) → indicadores y verificación
   SQL independiente de PDER y CRA. Cada paso imprime solo conteos y códigos de estado.

5. **Identidades (opcional, solo ficha):** el archivo se genera con el conversor y se carga con una orden de ADMIN:

   ```powershell
   backend\.venv\Scripts\python.exe infra\convert_real_excel.py --excel "<libro>" --out "<carpeta fuera del repo>" --identities
   backend\.venv\Scripts\python.exe infra\load_identities.py --target "$d\destino.json" --operator-profile real-tesis --csv "<carpeta>\identidades.local.csv"
   ```

   Todo o nada; rechaza códigos desconocidos; la auditoría guarda solo conteos. En periodos REAL el nombre solo se muestra en la **ficha** del estudiante:
   la lista y el buscador de Estudiantes (que busca solo por código), la búsqueda de identidades, Alertas, Indicadores, Reportes y Modelos no lo muestran.

## Cargar en la instalación de siempre (riesgo-escolar)

Es una decisión aparte del usuario: pone datos de menores en la base de la instalación activa. `run_real_study.py` rechaza ese destino salvo que se
cumplan las dos protecciones siguientes (con `--dry-run` no se exigen). Requisitos previos: la instalación ya migrada a 0008 (`infra/manage.py migrate`)
y el perfil de operador del ADMIN real de esa instalación.

1. **Descriptor y respaldo previo** (el respaldo debe ser de `riesgo-escolar`, estar en 0008 y tener menos de 24 h):

   ```powershell
   $s6 = "$env:LOCALAPPDATA\SeguimientoEscolar\S6"; $run = Get-Date -Format yyyyMMdd-HHmmss
   backend\.venv\Scripts\python.exe infra\runtime_target.py active --output "$s6\active-$run.json"
   backend\.venv\Scripts\python.exe infra\backup_restore.py backup --target "$s6\active-$run.json" --report "$s6\antes-de-cargar-$run-backup.json"
   backend\.venv\Scripts\python.exe infra\backup_restore.py verify --backup "$env:LOCALAPPDATA\SeguimientoEscolar\Backups\<NOMBRE>.sebackup" --report "$s6\antes-de-cargar-$run-verify.json"
   ```

2. **Perfil del ADMIN** (la contraseña se escribe en el terminal): `operator_profiles.py register-profile --target "$s6\active-$run.json" --name riesgo-escolar`.
3. **Simulacro** (inicia sesión, no escribe datos): la misma orden de «Corrida» con `--dry-run`, `--target "$s6\active-$run.json"` y `--operator-profile riesgo-escolar`.
4. **Corrida real**: la orden de «Corrida» con `--target "$s6\active-$run.json"`, `--operator-profile riesgo-escolar`, `--confirm-protocol`, la decisión sobre el tutor (abajo) y las dos protecciones:
   `--confirm-active riesgo-escolar --pre-backup "$env:LOCALAPPDATA\SeguimientoEscolar\Backups\<NOMBRE>.sebackup"`.

- **Tutor.** En la activa nunca se asigna por defecto al único tutor existente, y la decisión se exige antes de escribir nada. `--locked-tutor` crea la cuenta
  `tutor-bloqueado@example.com` sin acceso posible (añade una cuenta más a las cuatro); `--tutor-a/--tutor-b` da a esos TUTOR acceso a los datos REAL de sus secciones.
- **Respaldo con datos REAL.** Desde esta carga el respaldo S6 de la activa se etiqueta según lo que contiene (`origin` y `data_origins`: `REAL` o `MIXED`, con el alcance
  `REAL_INSTITUTIONAL`); nunca queda como `SYNTHETIC`. `restore-check` de un paquete REAL/MIXED exige `--confirm-real-copy`, porque crea otra copia local con esos datos.
- `load_identities.py` (nombres en la ficha) sigue sin actuar sobre la activa; los cierres los carga el propio orquestador.
- Cada corrida posterior (aunque no escriba nada) vuelve a pedir un respaldo de menos de 24 h.

## Dónde queda cada cosa

| Qué | Dónde |
|---|---|
| Informe completo de comparación, indicadores JSON y CSV por alumno | `%LOCALAPPDATA%\SeguimientoEscolar\ResultadosReales\<fecha>\` (fuera del repo) |
| Resumen agregado sin códigos | `tests/evidence/mejoras-05-resumen-agregado.json` |
| Capturas (Alertas con códigos enmascarados, Indicadores B1 y B2, Modelos) | `tests/evidence/mejoras-05-real-*.png` |
| Suite del backend | `tests/evidence/mejoras-05-backend.xml` |

## Repetir la corrida desde cero

Solo se borra el destino `real-tesis` (nunca la instalación activa ni otros destinos): `runtime_target.py stop` y luego `runtime_target.py cleanup` sobre
su `destino.json`; después se repite desde el paso 1 (el perfil `real-tesis` apunta al destino anterior: bórralo del Administrador de credenciales de
Windows o usa otro nombre). Detener sin borrar: `backend\.venv\Scripts\python.exe infra\runtime_target.py stop --target "$d\destino.json"`; volver a
encender: `... up --target "$d\destino.json"`. Dirección local: <http://localhost:5173>.

## Limitaciones (obligatorias en cualquier uso de los resultados)

1. **En `real-tesis` no existe respaldo ni restauración.** El respaldo S6 solo parte de la instalación activa; allí los datos viven solo en el volumen del destino y en
   los archivos originales, y si se borra el destino se rehacen desde `cortes.csv` y `cierres.csv`. En la activa sí hay respaldo (etiquetado REAL/MIXED, ver arriba), pero su
   restauración solo se ha comprobado con paquetes sin datos REAL. La corrida es **reproducible**: repetida desde cero da las mismas métricas, el mismo modelo ganador y las mismas alertas (la partición usa el código del estudiante, no identificadores internos).
2. **NIA e intervención oportuna reales no se calculan** sin registros reales de intervenciones: quedan `null` con `NO_REAL_INTERVENTIONS`.
3. PRV: el sistema solo ve el CSV ya filtrado (120 de 120); la recepción real (126) no tiene procedencia confirmada, así que **no se informa** en periodos REAL
   (`RECEPTION_PROVENANCE_UNCONFIRMED`, también en pantalla).
4. La matriz «predicho frente a referencia» de la evaluación retrospectiva es **en muestra** (el modelo se ajustó con esos mismos estudiantes): las
   cifras válidas son las de validación cruzada (fuera de muestra). Con 60 estudiantes la incertidumbre es alta y no sustituye una validación externa.
