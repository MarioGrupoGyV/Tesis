# ADR 004 — Windows, entorno vacío y límite institucional

Estado: aceptado para S2.1, 3 de octubre de 2026 (America/Lima).
Decisión explícita del usuario; sustituye las instrucciones de demostración de
ADR 001–003 y la planificación anterior. No modifica la metodología académica.

## Entorno y conservación

Windows/PowerShell es el anfitrión. Docker Desktop mantiene contenedores Linux y
las imágenes fijadas; no se requiere distribución adicional, Bash, Make ni consola
WSL. Se renombra el runner a run_backend_tests.py. Las pruebas informan Linux como
runtime real, nunca Python nativo Windows. Locks y dependencias se conservan.

Antes de cambiar referencias se inventariaron base, volúmenes, secretos y cuentas;
se detuvieron escritores y respaldaron PostgreSQL/CSV. La restauración aislada
comparó las trece tablas y el archivo reconstruido de CSV. El entorno anterior
queda detenido, con respaldo y volúmenes conservados, fuera del arranque normal.
No se borraron datos ni se cambiaron sus etiquetas.

El proyecto nuevo riesgo-escolar usa base riesgo_escolar, secretos independientes
en .local/runtime-secrets y volúmenes propios db_data/import_data. Comienza vacío.
prepare.py solo crea secretos. Se retiran semillas, credenciales de demostración,
comandos relacionados y consumidores de pruebas contra la aplicación activa.
La imagen API no incluye fixtures ni módulos de pruebas.

## Cuentas y contexto

bootstrap-admin exige terminal interactiva y pide correo/nombre/contraseña sin eco.
No admite contraseña por argumento, archivo o valor predeterminado. Advisory lock
serializa la creación; si existe cualquier ADMIN se rechaza la repetición. Usuario,
hash y auditoría se confirman juntos. No hay registro público ni restablecimiento
silencioso. configure solicita autenticación ADMIN y valores explícitos para usuario,
periodo o sección, sin inventar contexto. Sus cambios también son transaccionales.

El operador debe crear su cuenta: no se fabrica una para completar el entorno activo.
Pruebas automatizadas crean cuentas exclusivamente en bases aisladas nuevas; sus
contraseñas son temporales en memoria, no secretos del producto.

## Origen, migraciones y API

Origen público REAL significa institucional, no autorizado para procesamiento.
0001 y su snapshot no se alteran. 0002 añade restricciones de origen a nuevas
escrituras de nueve tablas; NOT VALID permite preservar registros históricos si
se migra otra base. En la nueva base vacía se validan las nueve restricciones.
Se conservan claves compuestas, integridad, triggers, permisos e inmutabilidad.
No se ejecuta autogeneración sobre ORM parcial. Defaults pasan a academic-v1;
ningún modelo puede activarse en esta iteración.

La regla require_processing_protocol rechaza escrituras de importación con 422
INSTITUTIONAL_PROCESSING_NOT_READY después de rol/CSRF y antes de persistir archivos
o registros escolares. No existe variable de entorno para habilitarlo. Faltan
procedencia autorizada, escala, periodo, ventanas, fechas y reglas de calidad.
El contexto institucional vacío sí se puede consultar.

El motor S2 conserva validación CSV, atomicidad/auditoría, locks, versión de vista
previa, idempotencia, revisiones, fechas Lima/UTC, null y permisos. Solo pytest
sustituye la política para ejercitarlo con fixtures aislados; no hay modo operativo
alternativo. Conflictos de integridad siguen como 409; indisponibilidad como 503
Error sanitizado, salvo health/ready que mantiene Health.

Contrato_API.yaml 0.2.0 introduce incompatibilidades deliberadas: retira DEMO del
origen público, renombra el bloqueo institucional y elimina rutas futuras no
implementadas. Publica catorce rutas S1/S2. Esquema.sql describe el diseño efectivo;
tipos frontend se regeneran. Historial de predicciones/seguimiento conserva sus
proyecciones públicas de lectura, sin implementar ML ni seguimiento.

## Consecuencias y siguiente dependencia

La aplicación presenta acceso y contexto vacío sin cifras ni riesgos inventados.
S3 desarrollará infraestructura predictiva, baseline y algoritmos del plan académico
con separación por estudiante y sin fuga temporal. Entrenar/evaluar institucionalmente
requiere dataset autorizado, etiquetas verificables y protocolo. S4–S6 permanecen
pendientes. No se declara preparación para producción ni evaluación de la hipótesis.

Resultados, fallos y límites: [Estado S2.1](../planning/Estado_Sprint_2_1.md).
