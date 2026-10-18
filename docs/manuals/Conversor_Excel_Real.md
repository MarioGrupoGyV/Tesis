# Conversor del Excel real (Bloque 4)

Programa local que convierte el Excel del colegio en los dos archivos CSV que usa el sistema. **No importa nada**: solo genera archivos.
Diseño: [ADR 012](../adr/012-procesamiento-real.md), secciones 10 y 13. No necesita internet ni base de datos y no instala nada
(lee el `.xlsx` con la biblioteca estándar de Python).

## Cómo ejecutarlo (Windows, PowerShell)

```powershell
py -3.12 infra/convert_real_excel.py --excel "C:\ruta\al\Registros academicos_Reales.xlsx" --out "C:\ruta\fuera\del\repositorio\salida" [--identities]
```

- `--excel`: el libro, **fuera del repositorio** (el programa se niega si su carpeta está dentro de Git).
- `--out`: carpeta de salida, **fuera del repositorio**. Si está dentro del árbol de Git el programa se niega (`OUTPUT_INSIDE_GIT`) y no
  escribe nada. **No guardes `--out` dentro del repo**: aunque no lleve nombres, son datos reales de menores.
- `--identities` (opcional): añade `identidades.local.csv` (`student_code,full_name`) para cargar los nombres en la ficha del alumno más
  adelante. Es el único archivo con nombres; solo se escribe dentro de `--out`. Sin la opción no se lee ningún nombre para las salidas.

## Qué produce (en `--out`)

| Archivo | Contenido |
|---|---|
| `cortes.csv` | 120 filas (60 alumnos × B1 y B2) con la cabecera canónica de 13 columnas. Notas parciales al corte (media de los 6 cursos, 0–20, 2 decimales), asistencia y entrega al corte (enteros, mitad hacia arriba), incidencias hasta el corte, participación **vacía**, fechas con zona America/Lima. `cutoff_at` = disponibilidad de la última fuente del bimestre (23:59:59 Lima, 21-04 y 30-06) para que el horizonte hasta el cierre sea de 17 días en todos los bimestres; `available_at` = disponibilidad de la última fuente de esa fila. |
| `cierres.csv` | Una fila por alumno-bimestre con la cabecera exacta de `infra/load_closings.py`: promedio final (media de las 6 notas finales), días y actividades programados/realizados, participación e incidencias. El sistema calcula RIESGO_V1; **el riesgo del Excel nunca se escribe**. |
| `resumen_conversion.json` | Solo conteos, códigos y SHA-256: filas por hoja, recibidas/aceptadas/rechazadas por causa, comprobaciones de estructura, verificación de RIESGO_V1 y búsqueda de nombres. |
| `identidades.local.csv` | Solo con `--identities`. |

El resultado es **determinista**: la misma entrada da los mismos bytes (orden por código y bimestre, `\n`, UTF-8 sin BOM). Puedes comprobarlo
ejecutando dos veces y comparando los SHA-256 del resumen.

## Qué comprueba

1. Recalcula las seis causas de rechazo de la hoja `Procesamiento` con los valores originales de cada recepción: bimestre ausente, código fuera de
   la cohorte, asistidos > programados, nota fuera de 0–20, entregadas > programadas y clave estudiante-bimestre duplicada. Las filas rechazadas **no**
   van a `cortes.csv` ni a `cierres.csv`; el resumen solo cuenta cuántas hay por causa.
2. Valida los CSV con el mismo código del sistema (`csv_validation.py` y el lector de `load_closings.py`).
3. Recalcula RIESGO_V1 con el código del backend a partir de `cierres.csv` y, si el libro trae la columna de riesgo, la compara en memoria
   (solo informa coincidencias y, si las hubiera, códigos de alumno).
4. Busca en memoria que ninguna salida (salvo identidades) contenga un nombre del libro y que no haya columnas sospechosas (`name`, `nombre`,
   `apellido`, `dni`, `correo`).

## Qué no hace

- No importa al sistema ni toca bases de datos o la instalación activa. Los pasos siguientes (importar, cargar cierres) son otra orden de ADMIN.
- No usa las hojas **Alertas** ni **Intervenciones** (fueron generadas por script) ni crea bitácoras de recepción o de reportes.
- No guarda nombres en `cortes.csv`, `cierres.csv` ni en el resumen.

## Si rechaza filas

El resumen indica cuántas filas se rechazaron y por qué causa (`rejected_by_cause`). Corrige el dato en la fuente y vuelve a ejecutar;
las filas rechazadas nunca se «reparan» solas. Si el libro cambió de formato, el programa se detiene con un código estable y sin imprimir valores:
`EXCEL_SHEET_MISSING` (falta una hoja), `EXCEL_COLUMN_MISSING` (falta una columna; se indica `hoja:columna`), `EXCEL_UNREADABLE`,
`EXCEL_DATE_INVALID`, `CORTES_CSV_REJECTED` o `CIERRES_CSV_REJECTED`.

## Siguiente paso (otro bloque)

Con `cortes.csv` y `cierres.csv` verificados: registrar el protocolo REAL, `study.py register-study`, importar, cargar cierres con
`load_closings.py`, comparar, registrar y activar el modelo (ver [Protocolo REAL](Protocolo_REAL.md)).
