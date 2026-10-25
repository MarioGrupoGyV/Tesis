# ADR 014: demostración en vivo con una copia del SVM REAL activo (solo en demo-vivo)

- Estado: aceptado por el usuario (Bloque 9 de la fase de mejoras, [ADR 011](011-fase-mejoras-tesis.md)); 2026-10-25.
- Relacionado: [ADR 012](012-procesamiento-real.md) (Bloque 6: instalación hermana, diseño B descartado) y [ADR 013](013-riesgo-v2-sin-participacion.md) (RIESGO_V2).

## Contexto

En la sustentación se registra en vivo un estudiante inventado y el sistema lo evalúa. El usuario pidió **un solo modelo y un solo botón**: que lo evalúe el mismo SVM
de los resultados del estudio real y no un modelo sintético. El estudiante debe quedarse en el periodo `DEMO-VIVO` de la instalación hermana (`demo-vivo`, 15174) sin tocar
`REAL-2026` ni la instalación principal (`riesgo-escolar`, 15173).

La base separa por origen los datos reales y los de demostración. Un periodo SYNTHETIC solo lo evalúa un modelo SYNTHETIC de su estudio (`active_model_scope`, clave
`(model_id, data_origin)` de las predicciones) y un ingreso manual solo se evalúa en SYNTHETIC (`deny_manual_prediction`). El servidor repite esa separación en cuatro sitios.

## Decisión: camino A

En `demo-vivo` se registra, para el periodo `DEMO-VIVO`, un segundo registro de modelo (`model_versions`, nombre «SVM del estudio real (copia de demostración)», origen
SYNTHETIC porque el periodo es de demostración) que apunta **al mismo artefacto** del SVM REAL activo. Tiene los mismos bytes y la misma huella `artifact_sha256`, y su
procedencia real queda intacta. No se reentrena, no se copia ni se reescribe ningún archivo, y el registro de entrenamiento no se toca. El registro deja escrito en
`manifest.demo_copy`:
- que es la misma huella del modelo REAL activo;
- el identificador del modelo fuente;
- que se usa solo para la demostración;
- y que el origen SYNTHETIC se debe a que el periodo es de demostración.

En pantalla: «Modelo: SVM del estudio real» (`Model.display_label`).

**Reglas de base de datos: ninguna cambia.** El registro cumple tal cual `active_model_scope`, `check_prediction_study`, `deny_manual_prediction` y
`check_followup_provenance`, porque el periodo, el corte, la predicción y la alerta son SYNTHETIC. Ninguna regla del periodo REAL se modifica.

**Comprobaciones del servidor que se doblan.** Solo se doblan con el interruptor `DEMO_REAL_MODEL_COPY=true`:

| Comprobación | Hoy | Con el interruptor y una copia verificada |
|---|---|---|
| `synthetic_study.compatible_model` | El modelo debe usar el artefacto sintético del estudio y sus variables | Acepta la copia si `demo_copy.verified_copy` la verifica |
| `services.ml.load_active_model` | Exige alcance `SYNTHETIC_STUDY` y el estudio del periodo en el artefacto | Devuelve el artefacto REAL, cargado y verificado por su camino normal (firma, protocolo REAL, estudio institucional) |
| `ml.predict.predict_snapshot` (misma regla de origen que la anterior, en el núcleo de inferencia) | El origen del artefacto debe ser el del corte | Con `demo_copy=True` admite un artefacto REAL institucional (v3) sobre un corte SYNTHETIC; nada más |
| `ArtifactStore.inspect` | — | **No cambia**: la copia usa el artefacto real tal como está, que pasa la verificación normal |

`demo_copy.verified_copy` exige todo lo siguiente:
- el interruptor está encendido;
- el periodo es SYNTHETIC y su código es `DEMO-VIVO`;
- la copia pertenece al estudio de ese periodo;
- existe un SVM REAL activo y verificado;
- el modelo fuente y la huella son los suyos.

Si el modelo REAL activo cambia, la copia deja de servir.

**Interruptor.** Está apagado por defecto (`Settings.demo_real_model_copy = False`). Solo lo enciende una copia creada con
`backup_restore.py restore-check --demo-real-model-copy`, que escribe `DEMO_REAL_MODEL_COPY=true` únicamente en la configuración de esa copia. `compose.yaml` (la principal) no
lo define. Con el interruptor apagado las comprobaciones se comportan exactamente como antes: la copia no se reconoce, `compatible_model` y `load_active_model` responden
`MODEL_INCOMPATIBLE` y la evaluación se rechaza. El camino normal llama a `predict_snapshot` igual que siempre.

**Registro y auditoría.** `prepare_demo_period.py --real-model-copy <huella>` (orden interna `register-demo-copy`, solo ADMIN). Rechaza:
- el interruptor apagado (`DEMO_COPY_DISABLED`);
- un periodo que no sea `DEMO-VIVO`, incluido `REAL-2026` (`DEMO_COPY_PERIOD_INVALID`);
- una huella distinta a la del SVM REAL activo (`DEMO_COPY_HASH_MISMATCH`);
- una segunda copia (`DEMO_COPY_EXISTS`, además de `UNIQUE(name, version, data_origin)`).

Al registrar, desactiva y **retira** (`RETIRED`) el modelo sintético del periodo, que no vuelve a evaluar ni se lista. Audita `DEMO_REAL_MODEL_COPY_REGISTERED` y, en cada
evaluación, `DEMO_REAL_MODEL_COPY_EVALUATED`. La evaluación por lote de un periodo (`/predictions/run`) no admite la copia; solo la evaluación por estudiante.

## Por qué no B ni C

- **B (origen nuevo `DEMO`)**: añadiría un tercer origen a periodos, matrículas, cortes, modelos, predicciones y alertas, con sus reglas y una migración también en la
  principal. Es casi tan grande como el diseño B del Bloque 6, para el mismo resultado visible.
- **C (aflojar reglas REAL)**: permitir evaluar ingresos manuales en un periodo REAL metería un alumno inventado entre los datos reales y modificaría las reglas que el usuario
  marcó como condición de parada.

## Consecuencias y límites

- La instalación principal no cambia de comportamiento. Verificado en vivo el 2026-10-25: el interruptor está apagado, el intento de registrar la copia devuelve
  `DEMO_COPY_DISABLED` y no existe ninguna copia.
- En `demo-vivo` el registro de la copia dice SYNTHETIC aunque el artefacto es REAL. Es la regla que se dobla, escrita en el propio registro y en este ADR.
- Pruebas: `backend/tests/test_b12_demo_copy.py`.
  - Interruptor apagado: no se puede registrar y las tres comprobaciones rechazan la copia.
  - Interruptor encendido: rechazos por huella, periodo y duplicado; mismo nivel que el SVM activo en los tres casos de ejemplo; alerta solo para Medio y Alto; sin participación en
    las respuestas; REAL-2026 intacto; auditoría.
  - Núcleo de inferencia: sin `demo_copy` la regla de origen no cambia.
- Ensayo en `demo-vivo` (2026-10-25): Alto 7/50/40/6, Medio 14,5/85/70/0 y Bajo 18/98/95/0. En los tres coinciden el nivel mostrado, el guardado y la alerta, y REAL-2026 conserva
  60 matrículas, 120 cortes, 120 referencias, 120 predicciones y 40 alertas. El SVM predice Medio en una franja estrecha; el caso Medio se eligió dentro de su clase.
