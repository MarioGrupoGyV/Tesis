# Backend reservado para S1

Sprint 0 no contiene una aplicación FastAPI, modelos ORM ni migraciones ejecutables.
El SQL de planificación es un diseño y no debe ejecutarse directamente.

Separación: `api/v1` rutas; `schemas` contratos; `services` reglas y transacciones;
`repositories` consultas; `models` persistencia; `core` configuración y acceso.
`ml/features`, `ml/train`, `ml/evaluate` y `ml/predict` alojarán el procesamiento local.
El coordinador convertirá el SQL revisado en Alembic en S1.
