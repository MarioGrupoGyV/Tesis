# ADR 005 — Infraestructura predictiva S3 y límite institucional

Estado: aceptado para implementar S3, 4 de octubre de 2026 (America/Lima).
Referencia inicial: `0c6063f65cfe84dd5d122439cc8ee899527da617`; checkout limpio.
Esta decisión se registra antes de programar. No cambia metodología ni criterios escolares.

## Decisiones y criterios técnicos

1. Completar núcleo tipado en app/ml/features, train, evaluate y predict; ORM explícito
   de las dos tablas existentes y capas separadas. Sin nueva migración ni autogeneración.
2. Mantener protocolo institucional bloqueado en CLI/API, sin flags de habilitación.
   Conservar model_activation_pending y demo_only_active_model. Ningún modelo se activa
   ni se registra en la aplicación actual. Entrenamiento solo se comprueba en pytest aislado.
3. Dataset interno versionado con escalas/criterio/horizonte/procedencia explícitos,
   etiquetas futuras observadas y metadatos temporales fuera de X. Rechazar temporalidad,
   revisiones o escalas incompatibles. Cinco variables básicas; edad/grado solo con
   justificación explícita y escala configurada. Sin configuración no hay entrenamiento.
4. Pipeline/ColumnTransformer por fold: imputación y codificación; SVM además escalado.
   Dummy, Random Forest, SVM sin probability=True y XGBoost CPU, recursos acotados.
   Mismas particiones por estudiante para todos; reducir folds cuando falte soporte,
   rechazar particiones inviables, nunca sustituirlas por partición de filas. No tuning
   ni elección automática del ganador; resultados fuera de muestra de validación cruzada,
   no evaluación prospectiva ni conjunto final independiente de validación institucional.
5. Métricas con orden LOW/MEDIUM/HIGH y null cuando no estimables. Sin calibración en S3:
   probabilidades públicas null y probabilities_calibrated=false en todos los algoritmos.
   La política de faltantes de inferencia será explícita e independiente de elegibilidad.
6. Artefactos internos privados: identificadores UUID, manifiesto con hashes/versiones,
   dataset y particiones privadas; firma HMAC con clave interna del almacenamiento para
   verificar procedencia antes de deserializar joblib. Un hash solo no acredita confianza.
   Rechazar symlinks, traversal, incompatibilidad y corrupción antes de cargar. XGBoost
   conserva además formato nativo UBJSON. Sin upload/download de modelos.
7. Selección temporal por matrícula: cutoff/available/created_at <= as_of; última revisión
   disponible, sin heredar una predicción anterior. Persistencia única snapshot/model,
   auditoría atómica y reutilización ante concurrencia. No alertas/intervenciones.
8. OpenAPI 0.3.0 añadirá solo cuatro rutas: GET models, GET models/{id}, POST predictions/run
   y GET predictions/{id}. ADMIN para modelos/ejecución, lectura de predicción ADMIN/TUTOR/
   DIRECTOR con alcance servidor. Autenticación/rol/CSRF preceden al bloqueo institucional.
   Modelo ausente 409 en el núcleo posterior al protocolo; no 503 para integridad.
9. Conservar cuentas/secretos Windows, volúmenes y puertos. Volumen ML privado nuevo,
   vacío en activo. Pruebas usan tmp_path fuera del checkout del contenedor. Sin fixtures
   o datasets de ejemplo en la aplicación. Regresión por roles S2.2 preservada.

## Dependencia adicional

Se elige **xgboost-cpu 3.4.1**, distribución oficial estable para CPU, Python >=3.12,
Linux x86_64 y Windows. Evita dependencias GPU; NumPy/SciPy ya están fijados.
Solo añadir esta distribución y sus hashes a los dos locks, sin actualizar otras
versiones. Instalación --require-hashes, pip check y cuatro algoritmos se comprobarán
en Linux/Python 3.12.12 dentro de Docker. Registrar resultados/diff en cierre S3.
Fuentes primarias: [instalación CPU](https://xgboost.readthedocs.io/en/stable/install.html),
[release 3.4.1](https://pypi.org/project/xgboost-cpu/3.4.1/).

## Habilitación pendiente

No existe dataset autorizado, criterio institucional implementado, calendario de
validación prospectiva ni modelo operativo. Entrenamiento/evaluación/activación
institucional exigen protocolo y futura migración revisada. Una configuración o
manifiesto declarado aprobado por el usuario no levanta este bloqueo. Las métricas
de fixtures solo prueban software y no evalúan la hipótesis. S4–S6 fuera de alcance.
