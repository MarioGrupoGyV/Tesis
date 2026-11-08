# ADR 016: grupo de demostración `PRUEBAS` en la instalación principal

- Estado: aceptado por el usuario (fase de mejoras, [ADR 011](011-fase-mejoras-tesis.md)); 2026-11-08.
- Modifica: [ADR 014](014-copia-demo-svm-real.md) (la copia del SVM solo existía en la instalación hermana `demo-vivo`). Relacionado: [ADR 015](015-conjunto-real-cerrado.md).

## Contexto

El usuario pidió trabajar en un solo sistema: los 60 estudiantes reales cerrados y, aparte, un grupo donde registrar en vivo un estudiante nuevo con sus datos y
evaluarlo con el SVM del estudio. La instalación hermana `demo-vivo` se eliminó a su pedido. Se evaluó y descartó permitir evaluar estudiantes escritos a mano en
un conjunto REAL nuevo: exige quitar el disparador `deny_manual_prediction` (migración sobre la base activa), una autorización de datos para ese conjunto y otra
regla de modelo, y dejaría un estudiante inventado etiquetado REAL.

## Decisión

1. El periodo de demostración se llama **`PRUEBAS`** (antes `DEMO-VIVO`): `demo_copy.DEMO_PERIOD_CODE`, `prepare_demo_period.py`, pantallas y pruebas.
2. La instalación principal tiene el grupo `PRUEBAS` (SYNTHETIC, con su estudio base de 60 estudiantes sintéticos) y la copia del SVM REAL activo (misma huella
   `45fb6c6b…38261`). Las reglas de base de datos y las comprobaciones de la copia son las del ADR 014, sin cambios.
3. **Interruptor.** `compose.yaml` define `DEMO_REAL_MODEL_COPY: "${DEMO_REAL_MODEL_COPY:-false}"` (apagado por defecto). La principal lo enciende en su `.env` local
   (no versionado). Una instalación nueva o una copia sin esa línea siguen con la copia apagada.
4. `prepare_demo_period.py` sigue rechazando la instalación activa (`DEMO_ONLY_ISOLATED_TARGET`), salvo con `--allow-active`, que además exige `--real-model-copy`
   (`DEMO_ACTIVE_REQUIRES_REAL_MODEL_COPY`) y repetir el nombre del proyecto (`--confirm-demo-target riesgo-escolar`).

## Ejecución (2026-11-08)

- Respaldo previo `s6-20261108T091220Z-7f94cbc57960` (COMPROBADO). Imágenes `b10c` (API y web). `.env` con `DEMO_REAL_MODEL_COPY=true`. Perfil de operador `riesgo-escolar-b12`.
- `prepare_demo_period.py --allow-active --confirm-demo-target riesgo-escolar --locked-tutor --real-model-copy <huella>`: simulacro sin escrituras y después
  `study · import (360) · compare · model · label (PRUEBAS) · real_model_copy (SVM, misma huella) · check OK`, 60 estudiantes sintéticos. Tutor de relleno ya existente:
  ninguna cuenta nueva (5 cuentas).
- `REAL-2026` idéntico antes y después: 60 matrículas, 120 revisiones, 120 referencias, 120 predicciones, 40 alertas, misma huella de modelos y de predicciones, cerrado.
- Navegador: «Estudio real» con 60 y «Conjunto cerrado», avisos retirados; `PRUEBAS` con su rótulo, «Nuevo estudiante» habilitado y la copia en Modelos.
  No se creó ningún estudiante de ensayo.
- Suite del servidor con el cambio de nombre: 564 aprobadas, 11 omitidas, 0 fallidas.

## Consecuencias

- La principal ya no tiene «solo datos reales»: tiene además un grupo SYNTHETIC rotulado. Los respaldos se etiquetan MIXED.
- Los estudiantes registrados en `PRUEBAS` no se pueden borrar (como todo estudiante); no entran en «Estudio real» ni en los indicadores de `REAL-2026`.
- Retroceso: quitar la línea del `.env` y reiniciar la API apaga la copia (las evaluaciones en `PRUEBAS` se rechazan); el grupo y sus registros se conservan.
