# Compatibilidad del SVM retrospectivo: cierre

11 de octubre de 2026, America/Lima. **RESUELTA para inferencia/evaluación local
en el runtime de referencia reproducible Linux x86_64 comprobado.** El modelo
se ejecuta en las versiones originales, no en las dependencias ML del backend.
Se mantiene S6 y el bloqueo institucional operativo; no se modifica la metodología.

## Versiones comprobadas

`resultados.json` del ZIP declara Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0,
scikit-learn 1.8.0, joblib 1.5.3 y openpyxl 3.1.5. Se compararon con la aplicación
real antes/después de actualizar. El intérprete ML del backend sigue intacto:

| Dependencia | Original / nueva inferencia | Backend |
| --- | --- | --- |
| Python | 3.12.14 | 3.12.12 |
| scikit-learn | 1.8.0 | 1.9.1 |
| NumPy | 2.3.5 | 2.5.3 |
| SciPy | 1.17.0 | 1.18.1 |
| joblib | 1.5.3 | 1.6.0 |

threadpoolctl, requerido transitivamente, está fijado en 3.6.0. Su versión de
entrenamiento no consta en el ZIP. openpyxl se usó para crear/leer Excel; no es
necesario para inferencia, que recibe los tres valores derivados del paquete.
No se pretende haber reconstruido todo el entorno de entrenamiento original.

scikit-learn exige conservar versiones para persistencia joblib:
[documentación oficial](https://scikit-learn.org/stable/model_persistence.html).
La solución evita cargar el modelo entre versiones, en lugar de ocultar warnings
o inferir compatibilidad por coincidencia de 60 clases.

## Cambios implementados

- Imagen API con un segundo intérprete en `/opt/retrospective`, sin otro servicio
  ni modificación de PostgreSQL. Base Python 3.12.14 fijada por digest Docker;
  cinco dependencias de inferencia más threadpoolctl fijadas por versión y SHA-256.
- `retrospective_runtime.py` invoca ese intérprete con `-I`, JSON por stdin/stdout,
  entorno sin secretos/paquetes del padre y timeout de 30 segundos. No hay fallback.
- `retrospective_worker.py` exige versiones exactas antes de deserializar. Mantiene
  las comprobaciones de hashes, esquema, B1 y fechas; deshabilita fit de Pipeline,
  StandardScaler y SVC. No entrena ni persiste datos.
- Servicio de evaluación, ensayo parcial y CLI administrativo usan el worker.
  El backend solo publica la nueva ejecución firmada. Runtime/lock quedan
  identificados junto al hash del modelo y la fecha real en el diario privado.
- Se capturan todas las advertencias de carga/inferencia y se muestran en UI.
  Diagnósticos no capturados en stderr impiden declarar éxito. No se usan filtros
  ignore, no se alteran versiones dentro del pickle ni se guarda un modelo nuevo.
- Contrato y tipos frontend admiten `COMPATIBLE_REFERENCE_RUNTIME`, preservando
  los dos estados históricos. Ensayo parcial devuelve versiones/advertencias.
- Backup S6 incluye el nuevo lock en su identidad. La recuperación sigue usando
  las tres imágenes exactas y el diario completo sin regeneración.

Los locks existentes backend/requirements.txt, requirements-dev.txt y
package-lock.json permanecen sin cambios. No se crea otro entorno virtual Windows;
backend/.venv sigue siendo el único. No hay migraciones nuevas, semillas,
credenciales nuevas, commit/push ni comunicación externa.

## Resultados desde aplicación, antes y después del reinicio

Instalación comprobada: [Modelos](http://localhost:15173/modelos), ADMIN.
La inferencia usa exactamente promedio parcial /20, proporción asistencia /1 y
proporción entrega /1. B1 conserva el corte 21/04/2026, B2 el 30/06/2026, ambos
a las 00:00 Lima, y B2 sigue exclusivamente como evaluación.

| Resultado de B2 | Ejecución real compatible |
| --- | ---: |
| Predicciones / coincidencias con el ZIP | 60 / 60 |
| Aciertos | 49 |
| Exactitud | 81,6666666667 % |
| F1 macro | 0,7930479204842023 |
| Propuestas | 40 |
| Notificaciones enviadas / intervenciones realizadas | 0 / 0 |
| Advertencias de carga/inferencia | 0 |
| Reajuste con B2 | No |

Conteos predichos: 20 LOW, 18 MEDIUM, 22 HIGH; soporte de referencia 25/11/24.
Matriz de confusión: [[20,5,0],[0,9,2],[0,4,20]]. No hubo discrepancias de clases,
métricas ni propuestas. El resultado no se reemplazó por cifras esperadas.

Ejecución después del reinicio activo: `be27bf54-ce3c-4d16-9a35-871c206f2007`,
2026-10-11 20:32:24.717534 UTC / **15:32:24.717534 Lima**.
Se conservaron tres ejecuciones experimentales anteriores, con sus tres warnings
originales, y se añadieron dos compatibles: interfaz y evaluación posterior al
reinicio. Son cinco ejecuciones sobre la misma cohorte de 60, no 300 estudiantes.

Hash original joblib, comprobado nuevamente antes de carga:
`69efc39488faec44b25fd151d638659b4bcc7189d644e0cd96ccec2667137c15`.
Hash original ZIP:
`08ace0a90feb05e29d1ff5dedb6bd126139fd42ca85df06c5ef5802a70a86de4`.
Hash lock del runtime:
`0539b84d9b771feff24218f9e3537936f488f73475dd711e734b49d503cd1373`.
El escalador incluido y sus 34 vectores de soporte siguen verificados contra B1.

## Pruebas y conservación

| Comprobación | Resultado | Evidencia nueva |
| --- | --- | --- |
| Regresión completa, PostgreSQL nuevo, Alembic head | 298 aprobadas; 0 fallos/omitidas | svm-compat-backend.xml y environment.json |
| Código final adaptador/worker/API, otra DB nueva | 25 aprobadas; 0 fallos/omitidas | svm-compat-final-tests.xml y environment.json |
| Infraestructura Windows/DPAPI/targets | 45 aprobadas y 77 subpruebas | svm-compat-infra.xml |
| Contrato, locks, tablas | 299 checks; 32 operaciones/30 paths/15 tablas | s6-svm-compat-contracts.json |
| Build API / frontend TypeScript y Vite | Aprobados | imágenes exactas abajo |
| Playwright real: cuatro roles, nueva B2, parcial, CSV, recarga, warnings antiguos | 4 aprobadas; 0 fallos/omitidas | svm-compat-playwright.json |
| UI real 1440×900 / 768×1024 / 390×844 | Capturada e inspeccionada; sin overflow global | svm-compat-result-*.png |
| Reinicio API/web activo y nueva inferencia | 12 verificaciones aprobadas | svm-compat-active-restart.json |
| Respaldo previo/final DPAPI | Aprobados; 23/25 archivos privados | svm-compat-backup-before.json / backup-final.json |
| Restauración a copia nueva, sin entrenamiento | Tablas, roles, esquema, Alembic y archivos exactos antes de login | svm-compat-restore.json |
| API recuperada y runtime compatible | Diario firmado, CSV y ensayo parcial | svm-compat-recovered-api.json |
| Reinicio completo de la copia DB/API/web | Todas las tablas y archivos exactos; copia detenida | svm-compat-persistence.json |

La suite completa precedió el refuerzo final de captura de advertencias; las
25 pruebas específicas se ejecutaron después de ese cambio, sobre el código final.
Los tests genéricos SYNTHETIC mantienen advertencias existentes de Starlette/httpx
y SVC.probability en 1.9.1; no son advertencias de carga del artefacto retrospectivo.

La prueba local Windows inicial tuvo 3 aprobadas, 1 fallida y 1 omitida porque el
ensayo de intérprete Linux se intentó sobre Windows con entorno sanitizado Linux.
Se corrigió su alcance: 3 aprobadas/2 omitidas en Windows; las dos se comprobaron
sin omisiones en Docker. Las evidencias inicial/final locales se conservan.
Un prefijo inválido del checker se corrigió a s6-svm-compat sin sobrescribir
evidencias. Un guard adicional de ruta no canónica impidió el primer preflight de
restauración; no efectuó escrituras. La restauración registrada posterior pasó.

En el activo: cuatro cuentas exactas; las 13 tablas anteriores fuera de sesiones/
auditoría no cambiaron, incluyendo 360 cortes, 55 predicciones, 51 casos y dos
intervenciones históricas. Todos los archivos privados preexistentes mantuvieron
sus hashes. Al reiniciar API/web, las 15 tablas y los archivos fueron exactamente
iguales antes de login; luego solo aumentaron sesiones/auditoría de autenticación
y las nuevas ejecuciones explícitas. PostgreSQL activo no se reinició.

Imágenes finales:
- API: sha256:815a1ac15f683deedededd90a9e116d5bbfb2202cdd7e28dbe3a49e44d5c18ba.
- Web: sha256:ac8eeb7746fb2fc51417b7026aafa4fb0aa3868bb3bbb2fb0bb0fa3d9ad4a1b5.
- DB: sha256:567d5d704a3e5a4864393b623a0d50eb1b5a4ad134cdac7cf19555cb2d8ffe9e.

Descriptor activo privado: %LOCALAPPDATA%\SeguimientoEscolar\S6\active-svm-reference.json.
Respaldo final privado: %LOCALAPPDATA%\SeguimientoEscolar\Backups\s6-20261011T203322Z-b63c6c843f4f.sebackup,
474060 bytes. Copia nueva: s6-restore-447dcff79726, puertos 15473/18300/55480;
descriptor restore-svm-reference.json, detenida y conservada tras comprobarla.

## Reproducción y archivos

[Manual de instalación y reproducción](../manuals/Manual_Runtime_SVM.md) con
comandos PowerShell, builds fijados, probe del intérprete, ejecución y pruebas.
Comandos ejecutados adicionales:

```powershell
docker compose build api web
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml up -d --wait dbtest
docker compose -f infra/compose.test.yaml run --rm -e TEST_REPORT_NAME=svm-compat-backend -e RETROSPECTIVE_TEST_ZIP=/inputs/package.zip -v 'C:\Users\mario\OneDrive\Escritorio\Downloads\Calculos_y_modelo_evaluacion_retrospectiva.zip:/inputs/package.zip:ro' tester
docker compose -f infra/compose.test.yaml run --rm -e TEST_REPORT_NAME=svm-compat-final-tests -e RETROSPECTIVE_TEST_ZIP=/inputs/package.zip -v 'C:\Users\mario\OneDrive\Escritorio\Downloads\Calculos_y_modelo_evaluacion_retrospectiva.zip:/inputs/package.zip:ro' -v 'C:\Users\mario\OneDrive\Escritorio\tesis-riesgo-escolar\infra:/workspace/infra:ro' tester python infra/run_retrospective_tests.py
.\backend\.venv\Scripts\python.exe -m pytest infra/tests -q --junitxml=tests/evidence/svm-compat-infra.xml
$destino = "$env:LOCALAPPDATA\SeguimientoEscolar\S6\active-svm-reference.json"
.\backend\.venv\Scripts\python.exe infra/test_retrospective_browser.py --target $destino --evidence-prefix svm-compat
.\backend\.venv\Scripts\python.exe infra/verify_svm_compatibility.py --target $destino --before .local/svm-compat-before.json --report tests/evidence/svm-compat-active-restart.json --restart
.\backend\.venv\Scripts\python.exe infra/backup_restore.py backup --target $destino --report tests/evidence/svm-compat-backup-final.json
.\backend\.venv\Scripts\python.exe infra/backup_restore.py restore-check --backup "$env:LOCALAPPDATA\SeguimientoEscolar\Backups\s6-20261011T203322Z-b63c6c843f4f.sebackup" --output "$env:LOCALAPPDATA\SeguimientoEscolar\S6\restore-svm-reference.json" --web-port 15473 --api-port 18300 --db-port 55480 --report tests/evidence/svm-compat-restore.json
.\backend\.venv\Scripts\python.exe infra/verify_retrospective_recovery.py --source-target $destino --restored-target "$env:LOCALAPPDATA\SeguimientoEscolar\S6\restore-svm-reference.json" --report tests/evidence/svm-compat-recovered-api.json
.\backend\.venv\Scripts\python.exe infra/test_s6_persistence.py --target "$env:LOCALAPPDATA\SeguimientoEscolar\S6\restore-svm-reference.json" --report tests/evidence/svm-compat-persistence.json
```

Para repetir, usar informes/descriptores/prefijos nuevos; no sobrescribir estos.
El manifiesto [svm-compat-changes.json](../../tests/evidence/svm-compat-changes.json)
enumera archivos modificados/nuevos con rutas y SHA-256. Datos reales, modelo,
credenciales, autorizaciones y diario siguen en sus destinos privados externos.

## Límites pendientes

Compatibilidad resuelta para la inferencia comprobada y su plataforma fijada.
No se probó ejecución nativa Windows/ARM del worker; no se instaló en backend/.venv.
El ZIP no permite verificar una réplica completa de entrenamiento/SO/hardware ni
la versión original de threadpoolctl. No se ejecutaron los scripts ni fit del ZIP.
Selección CV, OOF, baselines, intervalos y McNemar siguen siendo evidencia anterior.

La compatibilidad no valida la procedencia institucional, la regla RIESGO_V1,
autenticidad de timestamps, generalización a otra cohorte o impacto pedagógico.
Siguen pendientes sus soportes académicos/documentales. B2 son los mismos 60
estudiantes de B1; repetir la inferencia no crea una validación prospectiva.
