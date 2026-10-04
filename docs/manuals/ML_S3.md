# Manual técnico ML — S3

Infraestructura implementada y comprobable en pruebas aisladas. **No hay dataset
autorizado ni modelo operativo.** Entrenamiento, inferencia y activación institucional
siguen bloqueados; no se ha evaluado la hipótesis ni se han establecido escalas del colegio.

## Operación desde PowerShell

Docker Desktop mantiene Linux/Python 3.12.12 internamente. No se requiere consola Linux,
WSL, Bash o Make. No ejecutar entrenamiento al iniciar ni desde una petición HTTP.

```powershell
py -3.12 infra/ml.py readiness
py -3.12 infra/ml.py configuration
py -3.12 infra/ml.py compatibility
py -3.12 infra/ml.py train
```

`readiness` informa `ready=false`, requisitos ausentes y restricciones. `configuration`
devuelve `institutional_configuration=null` y el esquema requerido, sin inventar valores.
`compatibility` informa versiones, cuatro algoritmos, CPU/un hilo y calibración falsa.
`train` devuelve `INSTITUTIONAL_PROCESSING_NOT_READY` y salida **2**, incluso si el operador
declara disponer de datos o cambia variables de entorno. No admite archivos ni flags
de aprobación. Consultar la configuración no entrena ni abre datasets.

La comprobación de un artefacto interno, cuando exista en almacenamiento controlado:

```powershell
py -3.12 infra/ml.py validate --key <identificador-interno-de-32-hexadecimales>
```

No es una ruta de archivo ni un upload; no autoriza su uso institucional. En la aplicación
activa no se ha registrado ningún artefacto, por lo que no hay clave operativa que consultar.
Los tests realizan guardado/carga completa en directorios temporales privados aislados.

## Esquemas internos y temporalidad

`app/ml/features` define Pydantic con campos extra prohibidos y errores sin entradas
privadas. Versión de dataset `ml-dataset-v1`, variables `ml-features-v1`, cortes
`academic-v1`. No hay nuevas tablas/endpoints de investigación.

| Elemento | Campos y reglas |
|---|---|
| Dataset | scope, provenance, evaluation_as_of, config, observations y labels; máximo 10000 observaciones |
| Observación | student_key seudónimo, snapshot_id, enrollment_id, period_id, origen REAL, revisión/supersedes_id, window_start, available_at, cutoff_at, target_date, created_at, elegibilidad, values, feature_available_at e input_provenance |
| Etiqueta | snapshot_id, LOW/MEDIUM/HIGH, criterion_version, outcome_definition, provenance, observed_at y available_at; exactamente una por observación |
| Configuración | escalas explícitas minimum/maximum/decimals/unit; categorías de participación; criterio/versionado/horizonte; política de faltantes de inferencia; opcionales y justificación |
| Manifiesto | ArtifactManifest `ml-artifact-v1`: hashes, versiones, algoritmo/parámetros, esquema/criterio/horizonte, clases, semilla, soporte, particiones, predicciones de validación, métricas, procedencia y alcance |

Las cinco variables básicas son `average_grade`, `attendance_pct`, `activities_pct`,
`participation_level`, `behavior_incidents`. Edad/grado se excluyen por defecto; agregarlos
requiere `extra_features`, escala y `extra_justification`. Esto comprueba una configuración
explícita, no constituye aprobación metodológica. Ningún rango heredado del SQL se toma
como escala institucional autorizada.

Sección, tutor, IDs, códigos, fechas, etiquetas, predicciones e intervenciones nunca
entran a X. El DataFrame se construye solo con las columnas admitidas. `null` se conserva
hasta el Pipeline. Se rechazan no finitos, precisión incorrecta, escalas/categorías
desconocidas y variables adicionales. Los metadatos permanecen fuera del estimador.

La fecha de corte se convierte a día America/Lima para ventana y horizonte. `available_at`
y cada disponibilidad de variable deben ser <= corte; las variables tampoco pueden
ser posteriores a la disponibilidad global. `target_date` es posterior al día del corte
y debe coincidir con el horizonte configurado. Una etiqueta debe observarse desde la
fecha objetivo, estar disponible después de observarse y antes de evaluation_as_of.
Se exige procedencia distinta de la entrada y definición/versionado del resultado futuro.
Esto valida trazabilidad declarada; verificar evidencia institucional requiere el protocolo
pendiente. No se generan etiquetas con las notas utilizadas en X.

IDs duplicados, etiquetas faltantes o sobrantes, dos revisiones iguales de la misma
serie e identidades de matrícula inconsistentes se rechazan. Revisión 1 no tiene
antecesor; una revisión posterior enlaza la previa de la misma matrícula/corte/periodo/
origen, incrementa uno y no antecede a su incorporación. El dataset incluye la cadena
necesaria para validarla. Revisiones/cortes no incrementan el número independiente de personas.

`ISOLATED_TEST` identifica el alcance del núcleo ejercitado por pytest; no es un permiso
ni un modo de la aplicación. Un dataset `INSTITUTIONAL` se rechaza antes de entrenar.
No hay ejemplo escolar, generador de población, importación de datasets por API ni
comando operativo que acepte un flag para sustituir este bloqueo.

## Pipelines, grupos y métricas

Cada algoritmo recibe un Pipeline nuevo por fold. ColumnTransformer conserva únicamente
las columnas permitidas: mediana para numéricas, moda y OneHotEncoder para participación.
SVM añade StandardScaler. Las transformaciones se ajustan en train, nunca sobre validación.
Un fold sin ninguna observación disponible de una variable rechaza la comparación.

DummyClassifier usa prior; Random Forest tiene 32 árboles/profundidad 5; SVM usa RBF,
C=1, caché 64 MiB y máximo 10000 iteraciones, `probability=False`; XGBoost CPU tiene
24 árboles/profundidad 3, hist, learning_rate 0.1 y un hilo. Semilla por defecto 1729.
Threadpoolctl limita un hilo durante comparación; no GPU ni IA externa. No hay búsqueda
de hiperparámetros ni elección automática del ganador. Son parámetros de infraestructura
para pruebas, no una configuración institucional aprobada.

Se intenta StratifiedGroupKFold reproducible y, si no logra soporte, GroupKFold también
por estudiante. De hasta cinco folds se reduce según grupos y clase; todas las clases
deben existir en train y validación. Si no hay al menos dos folds válidos se emite
`INSUFFICIENT_CLASS_GROUP_SUPPORT`. Nunca se divide por filas para evitar ese diagnóstico.
Las mismas particiones se reutilizan en los cuatro algoritmos; se registran índices y
seudónimos **solo en el manifiesto privado**. Los tests comprueban disjunción y reproducibilidad.

Se guardan predicciones fuera de muestra de cada fold y métricas agregadas de validación
cruzada; después se ajusta el Pipeline final con los datos de desarrollo completos para
comprobar inferencia/round-trip. Ese ajuste no produce una evaluación final independiente.
No existe conjunto institucional reservado ni evaluación prospectiva en S3. Cualquier
tuning futuro debe quedar dentro del entrenamiento y preservar evaluación final aparte.

Matriz de confusión con orden LOW/MEDIUM/HIGH, soporte, precision/recall/F1 por clase y
macro, accuracy y balanced accuracy. Si falta denominador/soporte, la métrica correspondiente
es null; macro/balanced incompletas son null. Un cero con denominador válido sí es estimable.
AUC siempre null: no se implementa calibración. `predict_proba` no acredita calibración;
ningún algoritmo publica porcentajes, `probabilities_calibrated=false` y probabilidades null.
No se exige exactitud mínima. Métricas de fixtures nunca son resultados del colegio o tesis.

## Artefactos privados y confianza

Volumen nuevo `riesgo-escolar_ml_data` montado únicamente en API, `/var/lib/riesgo/ml`,
propietario del proceso sin privilegios y permisos de directorio 0700. Sin publicación
web ni endpoint de upload/download. El volumen activo permanece vacío: no hay modelo
aprobado ni test dentro de él. Los tests usan tmp_path dentro del entorno aislado.

ArtifactStore acepta una raíz absoluta fuera del checkout e IDs internos generados de
32 caracteres hexadecimales. Cada artefacto contiene Pipeline joblib, dataset JSON privado,
manifiesto firmado con hashes y, para XGBoost, `estimator.ubj` nativo además del Pipeline.
El manifiesto contiene parámetros completos, versiones exactas, particiones y predicciones
de validación privadas. No publicar estos archivos en evidencias, Git o respuestas API.

El escritor interno crea `.internal-key` de 32 bytes, permisos 0600, dentro del almacén
privado. Firma HMAC del manifiesto enlaza nombres y hashes. Antes de joblib: verifica firma,
esquema tipado, versiones exactas, clases/orden, archivos esperados y hashes, criterio,
horizonte y alcance. Rechaza rutas arbitrarias, traversal y symlinks en archivos/directorios
o sus padres. Lee bytes una vez y deserializa esos bytes ya verificados. XGBoost comprueba
también coherencia con su formato nativo. No acepta artefactos de versiones diferentes
asumiendo compatibilidad ni hace migración automática.

Un hash comprueba integridad, **no confianza**. La confianza presupone control exclusivo
del escritor y de la raíz/clave interna; quien controla ambos puede reemplazar una firma.
No copiar pickle/joblib externos a este almacén ni firmarlos por tener un hash válido.
El sandbox no hace seguro un pickle desconocido. Este sprint no ofrece importación de
modelos de terceros. Una firma tampoco equivale a aprobación metodológica o institucional.

## Inferencia, selección y persistencia

`predict_snapshot(Observation, ModelBundle | None) -> PredictionResult` retorna EVALUATED
o abstención MODEL_NOT_AVAILABLE/INSUFFICIENT_DATA/INELIGIBLE/INCOMPATIBLE con motivo.
Sin modelo: Modelo no disponible; faltantes excesivos o variables requeridas ausentes:
Datos insuficientes. Nunca LOW como reemplazo. Se valida esquema/origen/fecha/elegibilidad,
configuración y versiones; se usa exactamente el Pipeline entrenado. classes_ se mapea
por valor a LOW/MEDIUM/HIGH, no por posición de una columna.

`inference_max_missing_fraction` y `required_features` son obligatorios en configuración
y se calculan sobre las variables seleccionadas. No se reutiliza missing_fraction SQL
(que incluye otras variables) ni un umbral de elegibilidad de investigación como regla
operativa. El bool de elegibilidad no se deduce de esas notas o faltantes.

El repositorio selecciona por matrícula el mayor corte y revisión cuyas fechas cutoff,
available y created_at no superen as_of; tampoco usa estudiante/matrícula incorporados
después. Una corrección incorporada después no reemplaza retrospectivamente la vista
histórica. Una revisión nueva no hereda predicción. Se conserva el modelo inactivo en
las pruebas; la lectura actual de estudiantes continúa NOT_EVALUATED sin modelo activo.
La base no guarda historial de cambios de elegibilidad: se exige el estado actual y no
se pretende reconstruir autorizaciones históricas con as_of. El protocolo futuro debe
resolver esa limitación antes de inferencia institucional retrospectiva.

Persistencia interna: solo resultado evaluado, estudiante elegible con consentimiento/
asentimiento, origen coherente, periodo desbloqueado y esquema compatible. Un INSERT con
ON CONFLICT(snapshot_id,model_id) DO NOTHING espera al ganador concurrente y reutiliza su
fila. Solo el creador audita, en la misma transacción; rollback elimina ambos cambios.
Nunca modifica predicciones previas. Inmutabilidad/constraints existentes siguen activos.
Las abstenciones no insertan filas y el resultado de ejecución informa created/reused/
selected/abstentions. No genera alertas ni intervenciones.

`run_period` primero exige protocolo; después comprueba as_of no futuro, periodo, modelo
aprobado/activo, hashes/configuración y procedencia institucional. Estas condiciones no
son alcanzables operativamente: la base prohíbe cualquier modelo activo y ArtifactStore
actual solo acepta alcance de pruebas. No se simula aprobación para producir un éxito.

## API y orden de validación

| Operación /api/v1 | Rol y comportamiento |
|---|---|
| GET /models | ADMIN; paginado page/page_size, orden created_at DESC/id ASC, vacío en activo |
| GET /models/{id} | ADMIN; metadatos públicos, sin parámetros/métricas/manifiesto/hashes/rutas; inexistente 404 |
| POST /predictions/run | ADMIN y CSRF; period_id/as_of zonificado. Sesión → rol → CSRF → protocolo → cuerpo → periodo/modelo. S3 devuelve 422 de bloqueo sin consultas de datos escolares |
| GET /predictions/{id} | ADMIN/TUTOR/DIRECTOR; tutor solo su sección. Ajeno/inexistente mismo 404; RESEARCHER 403 |

401 sesión inválida; 403 rol/CSRF; 404 inaccesible/inexistente; 409 periodo bloqueado,
modelo no disponible/incompatible o conflicto; 422 validación/elegibilidad/protocolo;
503 indisponibilidad DB sanitizada. Integridad nunca se oculta como 503. Health/ready
conserva Health. La repetición válida devuelve reused, no un conflicto artificial.
No hay POST activate ni entrenamiento HTTP, ni pantallas nuevas de S4.

## Pruebas y siguiente dependencia

```powershell
$env:TEST_REPORT_NAME = 's3-backend'
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
npm run generate:api --workspace frontend
.\.venv-s0\Scripts\python.exe infra/check_s0.py
docker compose build web
$env:BROWSER_REPORT_PREFIX = 's3'
py -3.12 infra/test_browser.py
```

Mantener los locks. Única adición: xgboost-cpu 3.4.1; hashes de wheels oficiales para
Linux x86_64 y Windows amd64 en requirements/requirements-dev; NumPy/SciPy ya estaban.
No hay soporte comprobado de estas imágenes en ARM. Ver ADR 005 y cierre S3 para
comandos reales, resultados, advertencias y SHA de locks. Las pruebas usan riesgo_app;
el propietario prepara/migra bases aisladas. Nunca ejecutar checker de base vacía sobre
el entorno actual ni borrar volúmenes para conseguir una prueba aprobada.

Pendientes: datos y etiquetas autorizados, escalas/criterio/calendario institucional,
evaluación prospectiva, política de faltantes/elegibilidad/retención y revisión humana;
futura migración para activación, almacenamiento operativo de confianza y calibración
si se requiere. S4–S6 no están implementados. Las cuatro cuentas S2.2 y sus credenciales
Windows permanecen sin cambios; no hay envío de mensajes ni servicios de pago.
