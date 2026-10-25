# ADR 013: RIESGO_V2, riesgo de referencia sin participación

- Estado: aceptado (Bloque 8 de la fase de mejoras, [ADR 011](011-fase-mejoras-tesis.md)); 2026-10-24.
- Sustituye, para el estudio REAL y la exportación a SPSS, la regla activa RIESGO_V1 de [ADR 012](012-procesamiento-real.md) §4. RIESGO_V1 se conserva.

## Motivo

La institución confirmó que **no existe un registro original de la participación en aula**. Un componente sin fuente original no puede formar parte de la
referencia con la que se etiqueta y evalúa el modelo. La decisión se tomó **antes de reentrenar**: la regla, los umbrales y el reescalado del corte se fijaron
sin mirar resultados y no se ajustaron después.

## Regla RIESGO_V2

Cuatro componentes de 0 a 2 puntos con los insumos de cierre, con los mismos umbrales y la misma aritmética entera de V1:

| Componente | 2 puntos | 1 punto | 0 puntos |
|---|---|---|---|
| Promedio (redondeado a 2 decimales, mitad hacia arriba) | < 11 | < 14 | ≥ 14 |
| Asistencia (`100·asistidos` frente a programados) | < 80 % | < 90 % | ≥ 90 % |
| Actividades (`100·entregadas` frente a programadas) | < 60 % | < 80 % | ≥ 80 % |
| Incidencias | ≥ 3 | 1 o 2 | 0 |

Total 0–8. Nivel: **Bajo 0–1, Medio 2–3, Alto ≥ 4**. El umbral de Alto conserva el 50 % del puntaje máximo, igual que V1 (5 de 10): reescalado proporcional
decidido antes de reentrenar. La participación **no se lee ni se valida**; si llega en los insumos, se ignora. Criterio:
`RIESGO_V2: cuatro componentes de 0 a 2 puntos con insumos de cierre, sin participación (Bajo 0–1, Medio 2–3, Alto ≥ 4)`.

## Decisiones de implementación

1. `backend/app/services/risk_reference.py`: `compute_riesgo_v2`, `level_of_v2`, `validated_v2` (no exige participación) y una única constante
   `ACTIVE_RULE_VERSION = 'RIESGO_V2'`. `compute_riesgo_v1` y sus resultados no cambian.
2. **La regla de un periodo es la de su protocolo** (`risk_rule.version`), que queda congelada al confirmarlo; sin protocolo se usa la regla activa. Los
   protocolos nuevos (`run_real_study.py`) se crean con la regla activa. Un periodo ya cargado con un protocolo V1 no se convierte: la corrida se detiene con
   `PROTOCOL_RULE_DIFFERS` (los parámetros de un protocolo confirmado son inmutables). Estudio, indicadores, cierres y exportación leen la regla del periodo.
3. Migración `0009_riesgo_v2` (no edita 0007 ni 0008): `rule_version IN ('RIESGO_V1','RIESGO_V2')`; participación y su puntaje anulables, obligatorios en
   V1 con su CHECK de siempre y NULL en V2; CHECK de total y de nivel condicionados a la regla; el protocolo admite las dos reglas. Las filas V1 existentes
   siguen siendo válidas sin modificarse; V2 se agrega como filas nuevas (`revision = 1`), porque las referencias son de solo inserción.
4. Conversor: la verificación contra el riesgo del Excel sigue siendo con V1 (prueba que la conversión es fiel al archivo original). El resumen añade
   `recalculated_levels_v2` y `level_changes_v1_to_v2`, solo conteos. Los CSV de cortes y cierres no cambian (byte a byte).
5. Modelo: mismas cuatro características al corte (promedio de notas parciales, asistencia, actividades e incidencias), mismos algoritmos, hiperparámetros,
   semilla 0, 5 pliegues estratificados y agrupados por estudiante, 20 repeticiones y desempate de la clase modal hacia el mayor riesgo. Ningún ajuste.
6. Registro manual: la participación sigue siendo un campo opcional del formulario y no interviene en ninguna referencia; ninguna pantalla muestra
   componentes de la referencia. Nota: el modelo **sintético** de la demostración en vivo (`DEMO-VIVO`) sí usa la participación como característica del
   generador sintético; cambiarlo sería un ajuste de modelo fuera de este bloque.
7. Contrato 0.14.0 (`RiskRule.version` admite `RIESGO_V1` y `RIESGO_V2`) y tipos del frontend regenerados.

## Impacto en los resultados (estudio REAL local, exploratorio)

Distribución de referencia: V1 B1 15/21/24, B2 25/11/24 → **V2 B1 19/18/23, B2 27/8/25** (Bajo/Medio/Alto); 10 de los 120 registros cambian de nivel
(6 Medio→Bajo, 2 Medio→Alto, 2 Alto→Medio). Coincide con la comprobación cruzada del usuario, calculada aparte.

Validación cruzada agrupada, 20 repeticiones (media ± DE):

| Modelo | Exactitud | Exactitud balanceada | F1 macro | Kappa | Detección | Falsa alarma |
|---|---|---|---|---|---|---|
| Random Forest | 0,813 ± 0,015 | 0,776 ± 0,016 | 0,776 ± 0,016 | 0,711 ± 0,022 | 91,4 % ± 1,3 | 14,3 % ± 2,9 |
| SVM | 0,826 ± 0,014 | 0,792 ± 0,017 | 0,792 ± 0,017 | 0,731 ± 0,022 | 92,4 % ± 0,9 | 14,9 % ± 1,3 |
| XGBoost | 0,810 ± 0,020 | 0,771 ± 0,025 | 0,771 ± 0,025 | 0,705 ± 0,031 | 91,5 % ± 2,2 | 13,8 % ± 3,3 |
| Dummy (referencia) | 0,389 ± 0,014 | 0,325 ± 0,011 | 0,216 ± 0,030 | −0,016 ± 0,020 | 89,3 % ± 13,1 | 91,9 % ± 10,2 |

Con la misma regla de selección (F1 macro medio, luego exactitud balanceada, luego orden fijo) el modelo seleccionado pasa de **Random Forest (V1)** a **SVM (V2)**.
Con V1 Random Forest tenía exactitud 0,863 ± 0,014, F1 macro 0,848 y kappa 0,790: las métricas bajan con V2 porque la referencia ya no incluye un
componente (la participación) que no tenía registro original. No es una mejora ni un empeoramiento del sistema; es la consecuencia de una referencia más
defendible. La detección validada del modelo activo (SVM) es 92,4 % ± 0,9 en total, 86,2 % en B1 y 100 % en B2. Resumen agregado:
`tests/evidence/mejoras-08-resumen-agregado-v2.json`; exportación y verificación: `tests/evidence/mejoras-08-verificacion-export.json`.

## Instalación activa

Respaldo DPAPI previo en 0008 (`s6-20261025T032242Z-b57bdce2a247`), imágenes `b8`, migración a 0009, respaldo previo a la carga en 0009
(`s6-20261025T034734Z-a98986c42fb3`), ensayo completo en una copia aislada restaurada de ese respaldo (resumen idéntico al de la activa) y corrida V2 en
`riesgo-escolar` con `--locked-tutor`. La activa estaba vacía (sin periodos, estudiantes ni referencias): no había referencias V1 ni un modelo anterior que
conservar en ella; las referencias y modelos V1 siguen en `real-tesis` y en los respaldos del Bloque 6. Respaldo posterior con datos reales:
`s6-20261025T035700Z-2ce439b28970` (origen REAL, verificado).

## Consecuencias

- RIESGO_V1 sigue disponible para trazabilidad (pruebas, conversor y periodos con protocolo V1); no se borra ni se reescribe ninguna fila.
- Los textos de la tesis que citen la distribución, las métricas o el modelo seleccionado deben usar las cifras V2 de arriba.
- El guion de la demostración (`Guion_Demo_Manual.md`) cita cifras V1 de la parte A; hay que revisarlas antes de la sustentación.
