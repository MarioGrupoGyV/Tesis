# Runtime compatible del SVM retrospectivo

Actualización S6 solicitada el 11 de octubre de 2026. Solo inferencia/evaluación
retrospectiva del paquete autorizado; no habilita REAL operativo ni entrenamiento.

## Versiones e instalación

| Componente | ZIP original / inferencia nueva | Backend conservado |
| --- | --- | --- |
| Python | 3.12.14 | 3.12.12 |
| scikit-learn | 1.8.0 | 1.9.1 |
| NumPy | 2.3.5 | 2.5.3 |
| SciPy | 1.17.0 | 1.18.1 |
| joblib | 1.5.3 | 1.6.0 |

`resultados.json` declara estas cinco versiones y openpyxl 3.1.5 para la lectura
de Excel. La inferencia no lee Excel ni utiliza openpyxl. La dependencia transitiva
threadpoolctl se fija en 3.6.0; su versión de entrenamiento no consta en el ZIP.
Todos los paquetes necesarios para inferencia se fijan en
`backend/requirements-retrospective.txt`, con SHA-256 de las ruedas oficiales.
Plataforma comprobada: Linux x86_64 / CPython 3.12 / Debian bookworm.

La etapa Docker usa `python:3.12.14-slim-bookworm` fijada por digest
`sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e`.
Instala solo ruedas con `--require-hashes`, ejecuta pip check y copia su árbol
Python a `/opt/retrospective` dentro de la imagen API. El build verifica versión,
prefix y las cinco dependencias originales. El proceso de inferencia usa `-I`,
sin PYTHONPATH ni paquetes/credenciales del proceso padre, y limita hilos CPU a 1.
Este aislamiento de dependencias no es un sandbox de seguridad separado.

Desde PowerShell, raíz del repositorio, con Docker Desktop Linux iniciado:

```powershell
docker compose build api web
```

No instalar este lock en backend/.venv ni sustituir requirements.txt. No se crea
otro entorno virtual Windows. Para actualizar una instalación activa, elegir y
comprobar su descriptor S6 actual y tomar respaldo DPAPI antes del siguiente paso:

```powershell
# $destinoAnterior debe identificar las imágenes realmente activas.
.\backend\.venv\Scripts\python.exe infra/runtime_target.py identity --target $destinoAnterior
.\backend\.venv\Scripts\python.exe infra/backup_restore.py backup --target $destinoAnterior --report $informeRespaldoNuevo
docker compose up -d --no-deps --wait api web
# Elegir una ruta nueva para registrar las imágenes actuales.
.\backend\.venv\Scripts\python.exe infra/runtime_target.py active --output $descriptorNuevo
```

El destino comprobado actualmente se identifica con el descriptor privado
`%LOCALAPPDATA%\SeguimientoEscolar\S6\active-svm-reference.json`.
No reutilizar descriptores anteriores al build. Las instalaciones nuevas y las
restauraciones siguen el manual S6; la imagen API respaldada contiene el runtime
completo y no descarga ni entrena al arrancar.

## Ejecutar y reproducir

En [la aplicación](http://localhost:15173/modelos), ADMIN ejecuta evaluación B2,
entrada parcial y reporte; la versión/compatibilidad se ven en el resultado.
Las fechas históricas del corte y las fechas reales de ejecución son distintas.
Las 40 propuestas se separan de notificaciones/intervenciones, que siguen en cero.

Comprobar solo la identidad del intérprete, sin datos ni carga del modelo:

```powershell
docker compose exec -T api python -c "import json; from app.ml.retrospective_runtime import invoke; print(json.dumps(invoke('probe')))"
```

La ejecución verifica versiones antes de deserializar; hashes del ZIP/joblib,
escalador y 34 vectores de soporte contra B1; entradas parciales/fechas; B2 solo
evaluación. Pipeline, StandardScaler y SVC tienen fit deshabilitado dentro del
worker. El paquete viaja por stdin, no por argumentos ni por un nuevo archivo.
El worker no persiste datos. Solo el backend publica la ejecución nueva firmada.

Pruebas completas en una DB de prueba nueva, sin tocar la DB activa:

```powershell
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml up -d --wait dbtest
$zip = 'C:\Users\mario\OneDrive\Escritorio\Downloads\Calculos_y_modelo_evaluacion_retrospectiva.zip'
# Usar un TEST_REPORT_NAME nuevo; montaje externo read-only.
docker compose -f infra/compose.test.yaml run --rm -e TEST_REPORT_NAME=svm-reproduccion-nueva -e RETROSPECTIVE_TEST_ZIP=/inputs/package.zip -v "${zip}:/inputs/package.zip:ro" tester
```

Prueba de interfaz con credenciales vigentes en memoria y nuevo prefijo:

```powershell
$destino = "$env:LOCALAPPDATA\SeguimientoEscolar\S6\active-svm-reference.json"
.\backend\.venv\Scripts\python.exe infra/test_retrospective_browser.py --target $destino --evidence-prefix svm-reproduccion-nueva
```

`infra/verify_svm_compatibility.py --restart` reinicia únicamente API/web activas,
compara todas las tablas/archivos antes de login y verifica nuevamente B2 desde
la API. Requiere una instantánea privada previa y un informe nuevo. No reinicia
PostgreSQL activo. Para reinicio completo DB/API/web, restaurar a una copia nueva
y usar `infra/test_s6_persistence.py`; nunca restaurar sobre el activo.

## Advertencias y límites

La carga compatible comprobada no produce advertencias; no se ignoran ni filtran.
Las advertencias de carga/inferencia se capturan como datos del resultado y se
muestran en la interfaz. Un diagnóstico que escape a stderr impide declarar éxito.
Runtime ausente devuelve 503; versiones incompatibles rechazan la operación.
No se activa un fallback. Las ejecuciones históricas conservan tres advertencias
de versión y su estado experimental; no se reescriben como compatibles.

La correspondencia de versiones resuelve el problema de deserialización/inferencia
observado. No reconstruye el entrenamiento, el SO/hardware de origen ni paquetes
de análisis innecesarios para inferencia; el ZIP no aporta un lock completo de
ese entorno. Se mantienen pendientes procedencia documental, criterio académico,
autenticidad temporal y validación prospectiva/otra cohorte.
