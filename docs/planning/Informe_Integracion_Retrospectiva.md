# Informe de integración y verificación retrospectiva

Fecha real: 11 de octubre de 2026, America/Lima. Resultado técnico: **COMPROBADO
como evaluación retrospectiva local integrada**, con compatibilidad entre versiones
**experimental**. No acredita activación institucional ni validación de la tesis.

## Resultado disponible

ADMIN puede usar **Modelos → Evaluación retrospectiva B1 → B2** en
[la aplicación verificada](http://localhost:15173/modelos). El módulo ejecuta el
SVM del ZIP, permite comprobar tres entradas parciales y descargar un reporte
CSV de 60 filas numeradas. La autenticación utiliza los cuatro accesos vigentes;
TUTOR, DIRECTOR y RESEARCHER reciben 403 en estas operaciones.

Se preservan el modelo y los datos sintéticos operativos. Las propuestas nuevas
no se mezclan con los casos del estudio sintético. La importación, entrenamiento,
activación e inferencia institucional operativa siguen bloqueadas por protocolo.
El usuario confirmó expresamente datos reales y autorización para procesamiento
local; esta declaración no sustituye la autorización documental ni autentica los
registros. No se editó el documento académico oficial.

Destino actualizado: proyecto Docker `riesgo-escolar`, base `riesgo_escolar`,
web/API/DB 15173/18000/55432. El Vite Windows en localhost:5173 usa por defecto
API Windows :8000 y no tiene montado el volumen ML Docker. La versión comprobada
con el paquete privado registrado es la instalación Docker en :15173.

## Implementación previa frente al ZIP

| Aspecto | Aplicación previa, comprobada | Protocolo del ZIP / módulo nuevo |
| --- | --- | --- |
| Algoritmo elegido | SVM del estudio SYNTHETIC; núcleo admite Dummy, RF, SVM y XGBoost CPU | SVM RBF congelado, C=1, gamma=scale, class_weight=balanced |
| Variables | average_grade, attendance_pct, activities_pct, participation_level, behavior_incidents | Tres parciales: promedio /20, asistencia /1, entrega /1 |
| Escalas | Promedio /20 con 2 decimales; porcentajes /100; participación simulada 1/2/3; incidencias 0–12 | Promedio sin redondeo adicional; dos proporciones 0–1 |
| Transformación | ColumnTransformer con imputación; codificación de participación; escalado SVM | StandardScaler + SVC del joblib recibido, exactamente una transformación |
| Referencia | synthetic-future-v1 | RIESGO_V1 al cierre: cinco componentes |
| Particiones | Desarrollo/reserva de estudiantes distintos; CV por grupos | B1=60 entrenamiento declarado; B2=60 evaluación de los mismos estudiantes |
| Persistencia | Cortes/revisiones en PostgreSQL, predicción única corte/modelo, seguimiento S5 atómico | Diario privado HMAC separado; UUID/fecha/actor nuevos en cada evaluación completa |
| Alertas | MEDIUM/HIGH actuales crean/actualizan caso; LOW no cierra automáticamente | Solo propuestas retrospectivas; ninguna notificación ni intervención creada |

La entrada operativa anterior es CSV registrado con preview/commit y transacción.
La inferencia selecciona el último corte/revisión incorporado y disponible hasta
as_of, valida elegibilidad/escala/temporalidad y se abstiene cuando faltan datos.
La clase no se rellena como LOW. Inferencia y seguimiento se confirman juntos.
Estos recorridos siguen funcionando; la regresión PostgreSQL los comprobó.
[Evidencia del modelo previo](../../tests/evidence/retro-existing-model.json).

## Resultado real de la nueva ejecución

Última ejecución completa verificada: UUID `1c0c3050-a4bd-4489-a8f2-cdb2533fa590`,
**2026-10-11 19:59:51.318198 UTC / 14:59:51.318198 Lima**. Hay tres ejecuciones
completas conservadas: registro CLI, primer recorrido visual y recorrido final.
Todas usan las mismas 60 filas B2; no son 180 estudiantes ni tres cohortes.

| Indicador | ZIP esperado | Aplicación ejecutada |
| --- | ---: | ---: |
| Predicciones B2 | 60 | 60 |
| Aciertos | 49 | 49 |
| Exactitud | 81,6666667 % | 81,6666667 % |
| F1 macro | 0,7930479204842023 | 0,7930479204842023 |
| Clases coincidentes con el ZIP | 60 | 60 |
| Propuestas de alerta por ejecución | 40 | 40 |
| Notificaciones enviadas por ejecución | 0 | 0 |
| Intervenciones realizadas por ejecución | 0 | 0 |

Conteos predichos: **20 LOW, 18 MEDIUM, 22 HIGH**. Referencia: 25 LOW, 11 MEDIUM,
24 HIGH. Matriz de confusión con filas de referencia y columnas de predicción:

| Referencia / predicción | LOW | MEDIUM | HIGH |
| --- | ---: | ---: | ---: |
| LOW | 20 | 5 | 0 |
| MEDIUM | 0 | 9 | 2 |
| HIGH | 0 | 4 | 20 |

No hubo discrepancias de clases ni métricas B2. No se forzaron los resultados a
los valores esperados. El escalador se comprobó contra media, varianza y n=60 de
B1; los **34 vectores de soporte** coinciden con B1 escalado. El código de
inferencia no contiene fit y las pruebas prohíben Pipeline/Scaler/SVC.fit. No se
reelige ni se reajusta usando B2. La selección CV B1 del ZIP se conserva como
evidencia previa: F1 medio SVM 0,897008177, RF 0,843222703; no se presenta como
una comparación nueva de la aplicación.

## Datos parciales y fechas

Se localizó y leyó en solo lectura el original en Downloads, con SHA-256
`9cd4243f420b6da5e4ddab629d239334cbe6f2c100642eb6c0ec7ae53243c862`, idéntico al
protocolo. No se copió el Excel con nombres al repositorio ni al servidor.
ZIP SHA-256: `08ace0a90feb05e29d1ff5dedb6bd126139fd42ca85df06c5ef5802a70a86de4`.
Joblib SHA-256: `69efc39488faec44b25fd151d638659b4bcc7189d644e0cd96ccec2667137c15`.

El auditor independiente comprobó 120 filas bimestrales, 720 notas parciales,
seis cursos por fila y claves sin duplicación; para cada nota,
evaluación <= registro <= disponibilidad <= corte. Comprobó 120 ventanas de
asistencia y 120 de actividades, numeradores/denominadores y sus tres fechas,
y que pertenecen a la ventana bimestral. Los tres valores de cada una de las
120 filas coinciden con el CSV derivado: **360 coincidencias de entrada**.

B1: corte 21/04/2026, cierre 08/05/2026. B2: corte 30/06/2026, cierre 17/07/2026.
Horizonte lógico: 17 días en ambos. Se interpreta el corte a las **00:00 Lima**,
igual que el script, no al final del día. Los timestamps del archivo sin zona se
interpretan en Lima. Las etiquetas B1 están disponibles antes del corte B2.
La referencia de cinco componentes se recalculó con notas finales/conteos finales
y se comprobaron 120 coincidencias; estos resultados finales **no entran en X**.

Comprobar fechas declaradas demuestra consistencia interna del archivo, no que
fueran realmente observadas/registradas por el colegio en ese momento.
[Auditoría fuente agregada](../../tests/evidence/retro-source-audit.json).

## Pruebas y evidencia

| Comprobación | Estado / resultado | Evidencia |
| --- | --- | --- |
| Suite completa backend en PostgreSQL 17.6 nuevo; Alembic head limpio | COMPROBADO: 293 aprobadas, 0 omitidas/fallos | retro-backend.xml; retro-backend-environment.json |
| Código final del adaptador/API/permisos/CSV en otra DB nueva | COMPROBADO: 20 aprobadas | retro-final-tests.xml; retro-final-tests-environment.json |
| Infraestructura Windows/DPAPI/recovery | COMPROBADO: 45 pruebas y 77 subpruebas | retro-infra-final-tests.xml |
| OpenAPI 3.1, tablas y locks | COMPROBADO: 299 checks; 0.6.0, 32 operaciones, 30 paths, 15 tablas | s6-retrospective-contracts.json |
| Build TypeScript/Vite final | COMPROBADO en Docker Node 24.14.1, npm 11.20.0 | imagen web af3d4735527a1f197f9bb778df85923b0add9a4dc698e19950eee4af1083147c |
| Interfaz real: entrada parcial, evaluación, reporte, recarga e historial; cuatro roles | COMPROBADO: 4/4 Playwright | retro-playwright.json |
| Interfaz 1440×900, 768×1024, 390×844 | COMPROBADO y revisado visualmente; sin overflow global | retro-result-1440x900.png; retro-result-768x1024.png; retro-result-390x844.png |
| API activa y tablas/cuentas/archivos anteriores | COMPROBADO: 22 verificaciones | retro-active-verification.json |
| Respaldo nuevo DPAPI con ambas clases de archivos privados | COMPROBADO: 23 archivos, 467132 bytes | retro-backup-final.json |
| Restauración únicamente en copia nueva | COMPROBADO: DB/esquema/roles/Alembic y todos los archivos exactos antes de login | retro-restore-final.json |
| API restaurada, diario firmado, CSV e inferencia parcial congelada | COMPROBADO: 3 ejecuciones exactas | retro-recovered-api.json |
| Reinicio completo de la copia restaurada | COMPROBADO: tablas y 23 archivos exactos, copia detenida | retro-persistence.json |

Las evidencias anteriores no se sobrescriben. El informe de la primera prueba
visual fallida se conserva como retro-playwright-first.json.
La primera prueba local del adaptador tuvo 19 aprobadas y una omitida por faltar
PostgreSQL aislado; el recorrido completo final pasó las 20 sin omisiones.

Comandos principales, todos desde PowerShell en la raíz:

```powershell
$env:RETROSPECTIVE_TEST_ZIP = 'C:\Users\mario\OneDrive\Escritorio\Downloads\Calculos_y_modelo_evaluacion_retrospectiva.zip'
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_retrospective.py -q
.\backend\.venv\Scripts\python.exe infra/sync_retrospective_contract.py
npm run generate:api --workspace frontend
npm run build --workspace frontend
$env:CONTRACT_REPORT_PREFIX = 's6-retrospective'
.\backend\.venv\Scripts\python.exe infra/check_s0.py
.\backend\.venv\Scripts\python.exe -m pytest infra/tests -q
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml up -d --wait dbtest
docker compose -f infra/compose.test.yaml run --rm -e TEST_REPORT_NAME=retro-backend -e RETROSPECTIVE_TEST_ZIP=/inputs/package.zip -v 'C:\Users\mario\OneDrive\Escritorio\Downloads\Calculos_y_modelo_evaluacion_retrospectiva.zip:/inputs/package.zip:ro' tester
docker compose build api web
docker compose up -d --no-deps --wait api web
$destino = "$env:LOCALAPPDATA\SeguimientoEscolar\S6\active-retrospective-final.json"
.\backend\.venv\Scripts\python.exe infra/test_retrospective_browser.py --target $destino
.\backend\.venv\Scripts\python.exe infra/verify_retrospective_live.py --target $destino --before .local/retro-before.json --report tests/evidence/retro-active-verification.json
.\backend\.venv\Scripts\python.exe infra/backup_restore.py backup --target $destino --report tests/evidence/retro-backup-final.json
.\backend\.venv\Scripts\python.exe infra/backup_restore.py restore-check --backup "$env:LOCALAPPDATA\SeguimientoEscolar\Backups\s6-20261011T200142Z-98a37f884c61.sebackup" --output "$env:LOCALAPPDATA\SeguimientoEscolar\S6\restore-retrospective-final.json" --web-port 15373 --api-port 18200 --db-port 55470 --report tests/evidence/retro-restore-final.json
.\backend\.venv\Scripts\python.exe infra/test_s6_persistence.py --target "$env:LOCALAPPDATA\SeguimientoEscolar\S6\restore-retrospective-final.json" --report tests/evidence/retro-persistence.json
```

Registro y auditoría del original: [manual reproducible](../manuals/Manual_Evaluacion_Retrospectiva.md).
Los runners rechazan informes/descriptores ya existentes: usar destinos nuevos
para repetir y no ejecutar restauración sobre el activo.

## Incidencias y discrepancias

1. **Versiones diferentes:** ZIP: scikit-learn 1.8.0, NumPy 2.3.5, SciPy 1.17.0,
   joblib 1.5.3, Python 3.12.14. Aplicación Docker: scikit-learn 1.9.1, NumPy 2.5.3,
   SciPy 1.18.1, joblib 1.6.0, Python 3.12.12. Se conservan pins/locks; las tres
   advertencias Pipeline/Scaler/SVC se registran. El ensayo coincide fila a fila,
   pero [scikit-learn no respalda compatibilidad entre versiones](https://scikit-learn.org/stable/model_persistence.html).
   La carga permanece experimental y no activa REAL. Falta probar/mantener un
   runtime de referencia idéntico al del artefacto para una entrega soportada.
2. **Redondeo:** Decimal HALF_UP cambia dos promedios finales del original
   (16,40→16,41 y 10,51→10,52); no altera ninguna referencia ni predicción.
   Los promedios parciales no se redondean a dos decimales antes del escalador.
3. **Paquete incompleto:** hashes_archivos.json menciona
   Ajuste_metodologico_y_evaluacion_retrospectiva.docx, ausente del ZIP. Se
   documenta; no se fabrica ni se sustituye por otro documento. Los miembros
   presentes coinciden con sus hashes.
4. **Interfaz móvil:** primer recorrido falló por overflow a 390×844; se
   corrigió min-width del fieldset/grid/contenedores. El recorrido final pasó.
5. **Entorno Windows restringido:** primer build local falló por spawn EPERM y
   cuatro pruebas DPAPI por ACL privadas; ambas comprobaciones pasaron al
   ejecutarse con el acceso necesario. No se cambiaron dependencias. Se corrigió
   .dockerignore para excluir backend/.venv del contexto de imagen.
6. **Login de verificación:** un primer intento adicional falló en login DIRECTOR
   después de dos recorridos de cuatro roles y dos accesos adicionales. Se atribuyó
   al límite por IP de 10/300 s; no se conservó el status HTTP de aquel intento.
   Se conservó la política; la verificación posterior pasó ADMIN 200 y los demás
   403 en retrospectiva.

## Diferencia entre evidencia de ZIP y aplicación

**Comprobado ahora en aplicación:** artefacto congelado, orden de tres entradas,
escalado, 60 clases B2, exactitud/F1/matriz, 40 propuestas, cero acciones enviadas/
realizadas, fechas reales, persistencia firmada, entrada parcial, roles/CSRF,
reporte descargado por UI, conservación y recuperación completa.

**Comprobado por auditor externo del original y registrado junto al paquete:**
fechas declaradas de 720 notas/240 ventanas, transformación de 120 filas y regla
de referencia. Es una comprobación de archivo, no una observación escolar directa.

**Solo consta en el ZIP, no recalculado por la aplicación:** selección/CV B1
entre RF/SVM, predicciones OOF, baselines, intervalos bootstrap/binomial y McNemar.
No se ejecutaron los scripts del ZIP ni se reprodujo su entrenamiento original.
El conjunto B2 ya había sido visto: no se trata de test prospectivo preregistrado.

## Qué falta para sustentar la tesis

- Resolver documentalmente procedencia institucional y autorización/conservación
  de datos reales; confirmar qué población cubren estos 60 códigos.
- Sustentar instrumentos, escala y criterio RIESGO_V1 con el asesor y responsables
  académicos; es una regla al cierre, no una etiqueta independiente validada.
- Aportar evidencia externa de disponibilidad efectiva al corte; los timestamps
  del archivo y su consistencia no prueban autenticidad por sí mismos.
- Definir una validación posterior planificada y, si se desea generalizar, otra
  cohorte independiente. No contar 120 registros bimestrales como 120 personas.
- Resolver la compatibilidad de artefacto/runtime antes de activación operativa.
- Para afirmar impacto, oportunidad histórica o intervenciones eficaces, aportar
  un diseño y registros específicos. Las 40 propuestas retrospectivas no prueban
  notificaciones, atención ni mejoras causadas por el sistema.

No hubo commit/push, publicación, comunicación a terceros, reemplazo de cuentas,
regeneración del estudio sintético ni restauración sobre el activo. El único
entorno virtual local sigue siendo backend/.venv.

## Archivos modificados y agregados

El listado completo con rutas y SHA-256 de archivos públicos está en
[retro-changes.json](../../tests/evidence/retro-changes.json). Principales piezas:

- backend/app/ml/retrospective.py: validación de paquete, temporales, escalador y SVM.
- backend/app/repositories/retrospective.py: diario privado firmado y append-only.
- backend/app/services/retrospective.py; schemas/retrospective.py; api/v1/retrospective.py.
- backend/app/retrospective_cli.py y app/main.py.
- frontend/src/features/models/RetrospectivePanel.tsx, ModelsPage.tsx y features.css.
- frontend/src/lib/api.ts y api.generated.d.ts.
- docs/planning/Contrato_API.yaml y documentos de alcance/plan/manuales actualizados.
- infra/audit_retrospective_source.py, register_retrospective.py, sync_retrospective_contract.py,
  run_retrospective_tests.py, test_retrospective_browser.py, verify_retrospective_live.py,
  verify_retrospective_recovery.py; backup_restore.py y check_s0.py.
- backend/tests/test_retrospective.py; tests/e2e/retrospective.spec.ts;
  playwright.retrospective.config.ts; .dockerignore y evidencias nuevas.

Las migraciones y locks anteriores permanecen sin cambios; Esquema.sql solo
recibe una nota documental sobre el diario, sin DDL nuevo.
