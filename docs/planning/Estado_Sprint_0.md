> Cierre histórico: no es una guía de arranque vigente. Consultar [Estado S2.1](Estado_Sprint_2_1.md). Los resultados originales se conservan.

# Cierre del Sprint 0

Fecha: **3 de octubre de 2026 (America/Lima)**. Estado: **COMPLETADO**.
S1–S6: **NO INICIADOS**. Origen de la futura demo: **sintético/DEMO**.

## Entrega

Se leyeron AGENTS y los cuatro documentos de planificación antes de preparar la
estructura. No se eliminó ningún archivo inicial. AGENTS e Inicio conservan sus
hashes originales; plan, contrato y SQL reciben ajustes técnicos documentados.
El README inicial estaba en UTF-16 y se normalizó a UTF-8. Las versiones previas de
los documentos siguen en Git; no se hicieron commits, push ni cambios de rama.

| Entrega | Archivos o destino |
|---|---|
| Estructura del plan | frontend/src, backend/app, backend/migrations/versions, backend/tests, docs, infra, tests/e2e y tests/evidence; .gitkeep en carpetas vacías |
| Arquitectura/versiones | docs/adr/001-arquitectura.md, .node-version, .python-version |
| Dependencias exactas | package.json, frontend/package.json, package-lock.json; backend/requirements{,-dev}.{in,txt}; infra/requirements-s0.{in,txt} |
| Conciliación | docs/planning/Conciliacion_SQL_API.md; contrato 0.1.1 y SQL revisado; nota técnica y transiciones sincronizadas en el plan |
| Requisitos y preparación | README.md; README de frontend, backend, infra, tests, docs/research y docs/manuals |
| Configuración reservada | compose.yaml sin servicios; Makefile sin operaciones funcionales; .env.example sin secretos; .gitignore y .gitattributes |
| Aceptación/dependencias | docs/planning/Sprints_y_aceptacion.md |
| Verificación S0 | infra/check_s0.py; tests/evidence/s0-checks.json, s0-entorno.txt y s0-archivos.txt |

La conciliación resuelve año de periodo y catálogo inicial, identidad de sección por
grado, conteos y versión de vista previa, revisión del mismo corte, fechas Lima/UTC,
límites/tipos/nulabilidad, probabilidades conjuntas y fecha efectiva. Documenta roles,
CSRF recuperable por HMAC, asignación de responsable y métricas DRAFT sin inventarlas.
Los servicios que aplicarán esas decisiones pertenecen a los siguientes sprints.

## Herramientas comprobadas

| Herramienta | Resultado | Observación |
|---|---|---|
| Git | COMPROBADO: 2.47.0.windows.1 | Repositorio existente main, un commit por delante de origin/main al comenzar; sin cambios iniciales. |
| Docker CLI | COMPROBADO: 29.7.2 | No se creó ningún contenedor. |
| Docker Compose | COMPROBADO: 5.5.1 | Analiza la reserva Compose de S0. |
| Motor Docker | COMPROBADO: 29.7.2 | Consulta docker info de solo lectura fuera de la restricción de consola; respondió correctamente. |
| Python requerido | COMPROBADO: py -3.12 → 3.12.0 | venv y pip funcionan. El comando python usa 3.11.9 y no debe usarse para este stack. |
| Node/npm | COMPROBADO: 24.14.1 / 11.20.0 | Resolución real del lock npm con peers. |
| Make | FALTANTE, opcional | README ofrece preparación PowerShell. No bloquea S1. |

No faltan herramientas obligatorias del inventario solicitado. No se comprobó una
instalación independiente de PostgreSQL: S1 lo proporcionará por Compose.

## Comandos y resultados

| Comprobación ejecutada | Resultado |
|---|---|
| git --version, status --short --branch, rev-parse --show-toplevel | COMPROBADO: Git operativo y checkout identificado. |
| docker --version; docker compose version; docker info --format '{{json .ServerVersion}}' | COMPROBADO: CLI/Compose/motor; el primer intento sandbox falló y el intento de solo lectura permitido respondió 29.7.2. |
| python --version; py -0p; py -3.12 --version; py -3.12 -m pip --version | COMPROBADO: dos intérpretes; Python 3.12 disponible explícitamente. |
| node --version; npm --version; consulta de engines/peerDependencies del registro npm | COMPROBADO: runtime compatible con dependencias fijadas. |
| py -3.12 -m venv .venv-s0; instalación del tooling | COMPROBADO: entorno local de preparación, excluido de Git. |
| piptools compile con --generate-hashes (runtime, dev y S0) | COMPROBADO: locks generados; S0 usa --allow-unsafe para incluir pip/empaquetado. |
| .venv-s0/Scripts/python.exe -m pip install --require-hashes -r infra/requirements-s0.txt | COMPROBADO: instalación del tooling desde lock, pip 25.2. |
| .venv-s0/Scripts/python.exe -m pip check | COMPROBADO: No broken requirements found. Solo entorno de herramientas S0. |
| npm install --package-lock-only --ignore-scripts --no-audit --no-fund | COMPROBADO: bloqueo final generado; no instala node_modules ni ejecuta scripts. |
| npm ls --package-lock-only --depth=0 | COMPROBADO: versiones directas coinciden con manifests. |
| .venv-s0/Scripts/python.exe infra/check_s0.py | COMPROBADO: 171 verificaciones, 102 tipos SQL/API, 13 tablas, 35 sentencias, 27 rutas y 8 muestras contractuales. |
| docker compose config --no-consistency | COMPROBADO: reserva declarativa válida, services vacío; no prueba servicios. |
| git diff --check; revisión de inventario/hashes y git check-ignore | COMPROBADO: sin errores de whitespace; archivos privados/locales excluidos. |
| Revisión independiente de dependencias | COMPROBADO: 16 pins npm, 92 rangos engines compatibles; 42 paquetes runtime iguales en lock dev; hashes presentes en los tres locks Python. |
| Revisión independiente de contratos y comprobación de enlaces README | COMPROBADO: sin nuevos bloqueos de diseño; documentos enlazados presentes y sin implementación S1. |

Los números del validador corresponden al estado registrado en s0-checks.json.
Son comprobaciones de documentos, no pruebas de permisos, restricciones en DB o
recorridos. SQL se analizó con pglast; sus funciones PL/pgSQL aún no fueron ejecutadas.

Incidencias encontradas y resueltas durante S0:

- Docker info falló inicialmente por permisos del pipe en la consola restringida;
  una consulta de solo lectura permitida comprobó el motor sin iniciar servicios.
- npm rechazó @hookform/resolvers 5.3.0 con ETARGET; el registro confirmó 5.9.1 y
  la resolución final pasó.
- Una edición intermedia de YAML produjo un error de indentación; se corrigió y
  el contrato final pasó OpenAPI y las muestras positivas/negativas de JSON Schema.
- El primer lock de tooling advertía dependencias de empaquetado sin bloqueo;
  se regeneró con --allow-unsafe y se instaló por hashes satisfactoriamente.

## Pendientes y siguiente dependencia

**El proyecto está preparado para iniciar S1.** Docker funciona y las decisiones
documentales están resueltas. S1 debe comprobar tags/digests de imágenes e instalación
Linux, y usar Python objetivo 3.12.12; el local 3.12.0 no equivale a esa comprobación.

NO EJECUTADO por pertenecer a S1–S6: Docker build/up, PostgreSQL limpio, migración
Alembic, semilla, sesiones, permisos reales, módulos de negocio, entrenamiento,
build frontend, pytest de dominio, Playwright, capturas y persistencia tras reinicio.
No hay aplicación ejecutable ni modelo validado. La siguiente dependencia es la
implementación de S1 según sus criterios, con nueva autorización del usuario.

Para fase institucional siguen pendientes escala, horizonte, criterio de riesgo,
autorizaciones, fechas O1/O2 y protocolo del colegio/asesor. No bloquean la preparación
de la demo sintética, pero no se habilita REAL ni se cambia la metodología desde S0.
