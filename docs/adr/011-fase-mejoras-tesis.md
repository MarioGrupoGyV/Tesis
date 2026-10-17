# ADR 011: fase de mejoras para cumplir la tesis — 2026-10-17

Estado: aceptada. Rama local `mejoras-tesis`, creada desde `main`.

## Decisión

Se abre una fase de mejoras por bloques para que el sistema cubra lo que exige la
tesis. Cada bloque se pide y se autoriza de forma individual; este ADR (Bloque 0)
solo registra la decisión y la línea base. No modifica código de la aplicación.

## Autorización

Autorización explícita del usuario (Mayckol, 2026-10-17). Esta fase sustituye las
restricciones de `AGENTS.md` «no implementar la siguiente fase», «no importar los
tres Excel», «REAL bloqueado» y «sin commit», **solo en lo que cada bloque autorice**.
Se permiten commits locales en `mejoras-tesis`. **No hay push**, publicación ni
despliegue externo. Un bloque no autorizado conserva las restricciones anteriores.

## Bloques previstos

| Bloque | Contenido |
|---|---|
| 0 | Rama, este ADR, documentos de alcance y pruebas base en entorno aislado |
| 1 | Flujo manual evaluable para demostración en vivo (periodos SYNTHETIC) |
| 2 | Indicadores de tesis: PRV, CRA, PDER, intervención oportuna, NIA y métricas del modelo |
| 3 | Protocolo de procesamiento REAL con consentimiento/asentimiento |
| 4 | Conversor del Excel real a CSV canónico (solo códigos, sin nombres) |
| 5 | Entrenamiento y evaluación con datos REAL |
| 6 | Tablero con gráficos SVG propios |
| 7 | Datos de demostración y prueba E2E |

El orden puede ajustarse por coordinación; el contenido de cada bloque se define al
pedirlo y no se infiere de esta tabla.

## Lo que NO cambia

- Las cuatro cuentas locales (UUID, roles, asignaciones, historial) y sus accesos
  privados Windows. Sin bootstrap, `review_accounts.py` ni restablecimientos.
- Secretos en `.local/runtime-secrets` y volúmenes Docker `riesgo-escolar_*`.
  Nunca `docker compose down -v`; sin limpieza, restauración ni SQL destructivo
  sobre la instalación activa. Las pruebas usan el compose aislado `infra/compose.test.yaml`.
- Cierres S0–S6 y M1 y sus evidencias históricas.
- Auditoría inmutable y revisiones inmutables (cortes, predicciones y mediciones
  corregidas crean revisiones nuevas).
- Eventos en UTC, visualización en America/Lima.
- Cookie HttpOnly, CSRF en escrituras, Origin en login, roles y sección validados
  en servidor, 404 seguro para recursos ajenos o inexistentes.
- Sin riesgo inventado: sin evaluación o datos suficientes, el riesgo es null.
- Las métricas sintéticas no se presentan como resultados del colegio.

## Salvaguardas para menores

- Nunca importar ni mostrar nombres en reportes, CSV, logs o evidencias; solo códigos.
- Procesamiento exclusivamente local; ningún dato sale del equipo.
- Ningún archivo con datos identificables entra al repositorio.
- REAL solo opera con un protocolo registrado (consentimiento/asentimiento,
  procedencia, escala, periodo, ventanas y calidad), que llegará en el Bloque 3.
  Hasta entonces `INSTITUTIONAL_PROCESSING_NOT_READY` sigue vigente.
- Ninguna etiqueta convierte registros sintéticos en institucionales ni mezcla
  orígenes REAL y SYNTHETIC.

## Línea base

Pruebas del backend en PostgreSQL aislado antes de cualquier cambio:
`tests/evidence/mejoras-00-baseline.json`.
