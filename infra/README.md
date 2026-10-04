# Infraestructura de preparación

`requirements-s0.in` y su archivo de bloqueo describen herramientas para validar
OpenAPI y analizar sintaxis SQL sin crear una base. `check_s0.py` realiza esas
comprobaciones locales y revisa la estructura.

`compose.yaml` en la raíz reserva los servicios futuros, con `services: {}`.
Los Dockerfiles, proxy de mismo origen, volúmenes persistentes, roles de base
(propietario de migración y usuario de aplicación sin DDL) y healthchecks son S1.
No ejecutar `docker compose up` ni el SQL de diseño durante Sprint 0.
