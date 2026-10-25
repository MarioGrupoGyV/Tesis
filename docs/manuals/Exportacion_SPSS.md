# Exportación para SPSS (Bloques 7 y 8)

**Bloque 8 ([ADR 013](../adr/013-riesgo-v2-sin-participacion.md)):** la referencia es **RIESGO_V2** (cuatro componentes, sin participación). La exportación
verifica contra el resumen de la corrida V2 y añade la base por estudiante y bimestre y la base pareada B1/B2. La exportación V1 del Bloque 7
(carpeta `ExportSPSS/2026-10-18`, `mejoras-07-verificacion-export.json`) queda como antecedente histórico; no se usa para la tesis.

La tesis es no experimental y contrasta sus hipótesis en SPSS 26. Dos de ellas necesitan datos que el resumen publicado no trae porque solo guarda media y
desviación:

- **HE2** (comparar Random Forest, SVM, XGBoost y Dummy con Friedman/Wilcoxon sobre las 20 repeticiones de la validación cruzada agrupada): hace falta **una fila por
  repetición** con las métricas de cada modelo.
- **HE3** (kappa de Cohen con significación entre el riesgo predicho fuera de muestra en el corte intermedio y el riesgo de referencia al cierre, por bimestre): hace falta
  **una fila por estudiante y bimestre**.

Este bloque **no cambia ningún resultado**. Solo expone lo que `compare_institutional` ya calcula y comprueba que lo exportado reproduce exactamente el resumen publicado
de la corrida con la regla activa (`tests/evidence/mejoras-08-resumen-agregado-v2.json`; el resumen V1 `mejoras-051` ya no sirve de referencia). Es análisis exploratorio local sobre datos reales: no demuestra eficacia escolar ni valida la tesis.

## Cómo se ejecuta (PowerShell, una sola vez el entorno de `.sav`)

Entorno aparte para escribir los `.sav` con `pyreadstat` (fuera del repositorio; **no** es dependencia del backend):

```powershell
py -3.12 -m venv "$env:LOCALAPPDATA\SeguimientoEscolar\venv-spss"
```

```powershell
& "$env:LOCALAPPDATA\SeguimientoEscolar\venv-spss\Scripts\python.exe" -m pip install --only-binary=:all: pyreadstat pandas
```

Exportación, desde la raíz del repositorio (usa el Python del backend, Docker Desktop encendido y la imagen de la API con la que corrió el estudio; aquí `riesgo-escolar-api:b8`):

```powershell
$entrada = "$env:LOCALAPPDATA\SeguimientoEscolar\ConversionExcelReal\salida-v2"     # conversión con conteos RIESGO_V2
$salida = "$env:LOCALAPPDATA\SeguimientoEscolar\ExportSPSS\$(Get-Date -Format yyyy-MM-dd)"
$spss = "$env:LOCALAPPDATA\SeguimientoEscolar\venv-spss\Scripts\python.exe"
backend\.venv\Scripts\python.exe infra\export_spss.py --input $entrada --results $salida --image riesgo-escolar-api:b8 --spss-python $spss --evidence tests\evidence\mejoras-08-verificacion-export.json
```

Sin `--spss-python` solo se generan los CSV (el programa lo dice: `SAV_NOT_GENERATED`). Sin `--evidence` no se escribe nada en el repositorio. Tarda unos minutos
(20 repeticiones × 4 modelos × 5 pliegues).

**Qué hace y qué se niega a hacer.** Verifica el SHA-256 de `cortes.csv` y `cierres.csv` contra `resumen_conversion.json` (como `run_real_study.py`); se niega a escribir
dentro de un árbol de Git (`RESULTS_INSIDE_GIT`), a usar una carpeta de resultados con contenido (`RESULTS_NOT_EMPTY`) y a leer entradas dentro de Git. El cálculo corre en un
contenedor de la imagen de la API **sin red**, con las entradas y el código en solo lectura y únicamente la carpeta de resultados escribible. **No usa ninguna base de datos**:
arma el mismo conjunto de datos del estudio (características del corte, etiqueta RIESGO_V2 calculada con los insumos de cierre sin participación, grupo = código del estudiante) directamente
desde los dos CSV, con semilla 0, 5 pliegues y 20 repeticiones. No toca la instalación activa ni `demo-vivo`. La consola muestra solo conteos y estados.

## Archivos (en la carpeta de resultados, fuera de Git)

| Archivo | Contenido |
|---|---|
| `Metricas_por_repeticion.csv` / `.sav` | 20 filas (`repeticion` 1–20). Por modelo, sufijos `_rf`, `_svm`, `_xgb`, `_dummy`: `acc_` exactitud, `balacc_` exactitud balanceada, `f1_` F1 macro, `kappa_` kappa de la matriz de la repetición, `recallhigh_` sensibilidad de la clase Alto, `det_` detección total (proporción de Medio/Alto marcados Medio/Alto), `fa_` falsa alarma total (proporción de Bajo marcados Medio/Alto). |
| `Predicciones_fuera_de_muestra.csv` / `.sav` | 120 filas (estudiante × bimestre). `codigo` (código anónimo del Excel), `seccion` (1 = A, 2 = B), `bimestre` (1, 2), `riesgo_ref` (1 Bajo, 2 Medio, 3 Alto), `riesgo_pred_rf/svm/xgb/dummy` (clase modal), `acuerdo_rf`, `riesgo_pred_rf_rep1`, `detectado_rf`, `falsa_alarma_rf`. |
| `Base_estudiante_bimestre.csv` / `.sav` | 120 filas: `codigo`, `seccion` (1 = A, 2 = B), `bimestre` (1, 2), al corte `nota_corte`, `asist_corte`, `activ_corte`, `incid_corte`; al cierre `promedio`, `asistencia`, `entrega` (porcentajes 0–100 con 2 decimales, mitad hacia arriba), `incidencias`, `puntos_riesgo` («Puntaje RIESGO_V2 al cierre (0-8)») y `riesgo_ref`. **Sin columna de participación.** |
| `Base_pareada_B1_B2.csv` / `.sav` | 60 filas: `codigo`, `seccion` y, con sufijos `_b1` y `_b2`, `promedio`, `asistencia`, `entrega`, `incidencias`, `puntos_riesgo` y `riesgo_ref` (para pruebas pareadas entre bimestres). |
| `variables.json` | Etiquetas de variable, de valor y nivel de medida (de aquí salen los `.sav`). |
| `verificacion.json` | Verificación completa de esta ejecución (la copia sin códigos va al repositorio como `tests/evidence/mejoras-08-verificacion-export.json`). |

CSV en UTF-8 con BOM, separador coma, fin de línea CRLF, **punto decimal** y celdas vacías para los faltantes. Los `.sav` llevan etiquetas de variable en español, etiquetas de
valor (Bajo/Medio/Alto, A/B, Primer/Segundo bimestre, No detectado/Detectado, Sin falsa alarma/Falsa alarma) y nivel de medida: **ordinal** para los riesgos, **nominal**
para `codigo`, `seccion`, `bimestre`, `detectado_rf` y `falsa_alarma_rf`, escala para las métricas. Cada `.sav` se vuelve a leer con `pyreadstat` y se comprueba contra su CSV.

### Clase modal de las 20 repeticiones

En cada repetición el estudiante se predice **una vez, estando fuera del entrenamiento**. `riesgo_pred_*` es la clase más frecuente de esas 20 predicciones; **en caso de empate gana
la clase de mayor riesgo** (criterio conservador: ante la duda no se rebaja el riesgo) y los empates se cuentan por modelo en `verificacion.json`
(`empates_clase_modal_por_modelo`; en esta ejecución, 0 en los cuatro modelos). `acuerdo_rf` es la proporción de repeticiones en que Random Forest predijo esa clase modal
(1 = las 20 coinciden). `riesgo_pred_rf_rep1` es la predicción de la repetición 1, que es la que alimenta la matriz de confusión agregada del informe.

`detectado_rf` vale 1 si la referencia es Medio/Alto y la clase modal es Medio/Alto, 0 si la referencia es Medio/Alto y la clase modal es Bajo, y queda **vacío** si la referencia
es Bajo. `falsa_alarma_rf` vale 1 si la referencia es Bajo y la clase modal es Medio/Alto, 0 si es Bajo y Bajo, y queda vacío si la referencia es Medio/Alto.

### Por qué la detección de la clase modal puede diferir de la media por repetición

La detección publicada de Random Forest con V2 (91,4 % ± 1,3 en total) es la **media de 20 proporciones**, una por repetición. La detección de la clase modal es
**una sola proporción** sobre los 74 casos en riesgo con la predicción por mayoría. Son agregaciones distintas de las mismas predicciones y no tienen por qué coincidir.
En la ejecución V2 (Random Forest): detección 90,5 % (67/74) frente a 91,4 % en total; 82,9 % (34/41) frente a 84,6 % en B1; 100 % (33/33) frente a 99,8 % en B2. Falsa
alarma 15,2 % (7/46) frente a 14,3 % en total; 15,8 % (3/19) frente a 13,9 % en B1; 14,8 % (4/27) frente a 14,6 % en B2. Empates de la clase modal: 0 en Random Forest,
SVM y Dummy; 2 en XGBoost (resueltos hacia el mayor riesgo). Se informan como datos distintos; no se ajusta ninguna cifra publicada.

## Verificación (`verificacion.json`)

Vuelve a leer los CSV exportados (no los datos en memoria) y recalcula media y desviación (ddof = 1) de exactitud, exactitud balanceada, F1 macro, kappa y sensibilidad de Alto de los
cuatro modelos, más detección y falsa alarma totales, y las compara con el resumen publicado con tolerancia 1e-12. También comprueba las filas (20 y 120), los 60 estudiantes, la
distribución del riesgo de referencia por bimestre **calculada** (la del resumen V2 y la que el conversor calcula con el código del backend, nunca un valor fijo), que el
resumen de referencia sea de la regla activa (`regla_del_resumen_publicado`), y en las dos bases nuevas: filas, puntaje coherente con el nivel V2, rangos, misma referencia
que las predicciones, pareada igual a la base por estudiante y ausencia de participación; y que lo exportado coincida con el informe de la comparación en proceso. Registra además el SHA-256 de
cada archivo exportado, la imagen y las versiones de las librerías. `reproduce_resumen_publicado` es `true` solo si **todo** coincide; si es `false`, el programa se detiene
(salida 4), muestra qué difiere y **no** escribe la evidencia del repositorio. En la ejecución registrada la diferencia máxima fue 0,0 (idéntico bit a bit) y una segunda ejecución dio los
mismos SHA-256 en los CSV (los `.sav` llevan marca de tiempo y por eso su hash cambia; para comparar ejecuciones usa el de los CSV).

## Uso en SPSS 26

Abre los `.sav` directamente. Si importas el CSV, indica codificación UTF-8 y **punto** como símbolo decimal (con configuración regional en español SPSS puede esperar coma).

- HE2: *Analizar > Pruebas no paramétricas > Cuadros de diálogo antiguos > K muestras relacionadas…* (Friedman) con `acc_rf`, `acc_svm`, `acc_xgb`, `acc_dummy` (repite con `f1_*`,
  `balacc_*`, `kappa_*`, `recallhigh_*`); comparaciones por pares con *2 muestras relacionadas…* (Wilcoxon).
- HE3: *Datos > Segmentar archivo > Organizar los resultados por grupos* con `bimestre`; luego *Analizar > Estadísticos descriptivos > Tablas de contingencia…* con `riesgo_ref` y
  `riesgo_pred_rf`, y en *Estadísticos…* marca *Kappa*. `detectado_rf` y `falsa_alarma_rf` dan directamente las proporciones del bimestre.

**Cautelas que conviene dejar escritas en la tesis.** Las 20 repeticiones reutilizan las mismas 120 observaciones (solo cambia cómo se reparten los estudiantes entre pliegues), así que no
son 20 muestras independientes: SPSS no lo sabe y los valores *p* de Friedman/Wilcoxon sobre ellas son descriptivos, no evidencia de generalización. Del mismo modo, las 120 filas son
60 estudiantes con dos bimestres cada uno, no 120 personas independientes. La clase modal es una predicción por mayoría de modelos entrenados con los mismos datos; no es validación externa.

## Privacidad

Los archivos con una fila por estudiante llevan el **código anónimo** del Excel (nunca nombres) y viven **fuera del repositorio**
(`%LOCALAPPDATA%\SeguimientoEscolar\ExportSPSS\<fecha>`). No los copies dentro del repositorio ni los compartas con los nombres de la ficha de identidades. En el repositorio solo
queda la verificación agregada, sin códigos.

## Códigos de parada

| Código | Significado |
|---|---|
| `RESULTS_INSIDE_GIT`, `INPUT_INSIDE_GIT` | La carpeta de resultados o de entrada está dentro de un árbol de Git. |
| `RESULTS_NOT_EMPTY` | La carpeta de resultados ya tiene contenido (no se sobrescribe). |
| `INPUT_HASH_MISMATCH` (+ archivo) | `cortes.csv` o `cierres.csv` no coincide con `resumen_conversion.json`. |
| `REFERENCE_MISSING`, `IMAGE_REQUIRED` | Falta el resumen publicado de referencia o `--image`. |
| `WORKER_FAILED`, `SAV_FAILED`, `PYREADSTAT_MISSING` | Falló el cálculo en el contenedor, la creación de `.sav` o falta `pyreadstat` en el entorno de SPSS. |
| `LABELS_DIFFER_FROM_CONVERSION_SUMMARY` | La regla activa recalculada no coincide con el resumen del conversor. |
| `CONVERSION_SUMMARY_WITHOUT_ACTIVE_RULE` | El resumen del conversor no trae los conteos V2: vuelve a convertir el Excel con el conversor actual. |
| Salida 4 (`NO_REPRODUCE`) | `reproduce_resumen_publicado = false`: se listan las diferencias y no se publica evidencia. |

## Cambio en el código y pruebas

`compare_institutional(..., collector=None)` recibe de forma opcional un colector que obtiene, por repetición y algoritmo, un `RepetitionRecord` (métricas de la repetición, kappa,
conteos de detección por ámbito, predicciones fuera de muestra alineadas con el orden canónico y clase de referencia). Entrega copias y no altera semillas, particiones ni
hiperparámetros. Sin colector, el resultado es idéntico al anterior (`backend/tests/test_b10_export_spss.py` lo comprueba con una huella calculada con el código previo al cambio, también
con un colector que destroza lo que recibe). La misma prueba cubre las tablas, la clase modal y los empates, la verificación (con una referencia alterada que no debe reproducir) y el rechazo de
`--results` dentro de Git y de entradas con otro SHA-256.
