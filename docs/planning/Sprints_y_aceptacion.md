# Sprints y aceptación vigente

S0, S1 y S2: cerrados bajo el alcance histórico anterior. Sus reportes/evidencias
se conservan intactos. S2.1 reemplaza las instrucciones operativas de ese alcance.

| Sprint | Estado | Dependencia y criterio de salida |
|---|---|---|
| S2.1 | Implementado; resultados en Estado_Sprint_2_1.md | Windows/PowerShell con Docker, respaldo restaurado, nuevo entorno vacío, bootstrap explícito, contrato 0.2.0, bloqueo institucional y regresión |
| S2.2 | Comprobado; Estado_Sprint_2_2.md y Matriz_verificacion_S2_2.md | Cuatro cuentas locales explícitas con credenciales privadas Windows; revisión de 14 rutas y UI por rol/tamaño; persistencia con usuarios y regresión aislada; sin registros escolares ni habilitación institucional |
| S3 | Infraestructura implementada; Estado_Sprint_3.md | S2.2 preservado; núcleo ML y persistencia comprobados aisladamente. Entrenamiento/evaluación/activación institucional pendientes de datos, etiquetas, protocolo y migración |
| S3.1 | Comprobado; Estado_Sprint_3_1.md y Matriz_verificacion_S3_1.md | Estudio SYNTHETIC nuevo verificado, comparación con reserva temporal, activación explícita técnica y recorrido API/DB; REAL bloqueado |
| S4 | Implementado y comprobado; Estado_Sprint_4.md y Matriz_verificacion_S4.md | S3.1 comprobado. Acceso/Inicio/Estudiantes/Datos/Modelos con API real, rutas/roles/contexto, flujo importación/evaluación sintética y tres tamaños. Alertas/Reportes pendientes S5 |
| S5 | Implementado; cierre y resultados en Estado_Sprint_5.md y Matriz_verificacion_S5.md | S4 conservado; seguimiento SYNTHETIC único/versionado, inferencia atómica, resumen y CSV con permisos servidor. REAL bloqueado |
| S6 | Comprobado como sistema local para simulación; Estado_Sprint_6.md y Matriz_Trazabilidad_Final.md | Instalación nueva/recorrido UI, respaldo DPAPI/restauración completa sin regeneración y revisión activa no destructiva; validación académica pendiente |

## Aceptación S6

**Comprobada**: A 11/11, B 5/5, C 4/4; backend 269, perfiles 16, recuperación 29,
paquete real seis negativos. Estado S6 y matriz final documentan evidencia, hashes
y límites. REAL y aceptación académica permanecen pendientes.

1. ADR 009 previa y tres destinos explícitos: instalación nueva, restauración del
   estado S5 sin generador y revisión activa no destructiva. Identidad comprobada
   antes de escribir; sin fallback a BASE activo, colisiones o volúmenes compartidos.
2. Instalación vacía con 15 tablas/head 0004, riesgo_app y secretos/volúmenes nuevos;
   bootstrap/configuración explícitos y perfil ADMIN propio privado validado en
   Windows, sin recrear accesos S2.2 o imponer política de fixtures.
3. Generación/comparación/registro/activación técnica explícitos solo en aislamiento;
   primer import y primera inferencia por UI real. Selección en desarrollo y firmas
   reproducibles; reserva fuera de fit/selección, sin cambios metodológicos.
4. Respaldo consistente custom PostgreSQL y todos los archivos privados, incluida
   clave HMAC, más configuración mínima. Manifiesto de código/locks/imágenes,
   roles/grants/Alembic, tamaños/hashes y todas las tablas. finally exacto de escritores.
5. DPAPI de usuario nativa Windows comprobada y rechazo de alteración; validación de
   paquetes propios/rutas/inventario/límites antes de restaurar. Temporales privados
   limpios; errores/corrupción/ausencia/incompatibilidad/colisión comprobados sin activo.
6. Restore aislado con pg_restore fatal, sin migración previa/stamp/regeneración;
   coincidencia de las 15 tablas, sesiones/auditoría/Alembic y todos los archivos
   antes de login. HMAC/modelo compatibles, API riesgo_app y copia conservada detenida.
7. Cuatro roles en copia y activo, alcance/filtros/paginación/historial/reportes/CSV,
   CSRF, idempotencia y caso cerrado preservados. Recorrido nuevo con actividades y
   versiones; caída DB real exclusivamente aislada, 503 sanitizada y recuperación.
8. Tres tamaños inspeccionados, teclado/foco/historial móvil y conflictos/borradores;
   simulaciones HTTP diferenciadas de DB real. Sin certificación de accesibilidad.
9. Backend completo, pruebas nuevas de perfiles/recuperación, contrato/tipos,
   pip check/build host/imágenes/diff check y checker S6 de destinos/cobertura actual.
   Índice/manuales/matriz/Estado con código/locks, comandos, fallos/omisiones y límites.
10. Datos/credenciales/modelo/históricos preservados; REAL, eficacia escolar y
    validación de tesis pendientes. Sin S7, commit/push o despliegue externo.

## Aceptación S2.1 (registro previo)

1. SHA inicial y cambios registrados; no descartar trabajo. Versiones/locks conservados.
2. Respaldo privado de base/CSV restaurado en destino aislado antes de retirar el
   entorno anterior; ninguna eliminación ni conversión de origen.
3. Proyecto, base, secretos y volúmenes nuevos; cero cuentas y registros precargados.
4. Preparación/arranque/migración/parada/reinicio/pruebas desde PowerShell. Componentes
   Linux solo internos de Docker; no afirmar ejecución backend nativa Windows.
5. Primer administrador por entrada interactiva sin contraseña persistida, repetición
   rechazada, hash y auditoría atómicos. Configuración posterior con valores del operador.
6. Origen institucional en contrato; 422 INSTITUTIONAL_PROCESSING_NOT_READY en importación,
   sin archivos ni escrituras escolares. No existe bypass por variable de entorno.
7. Conservación del motor S2 con pruebas aisladas de transacciones, concurrencia,
   revisiones, integridad/409, fechas, idempotencia, permisos, CSRF y archivos alterados.
8. Migración nueva sin alterar snapshot 0001; relaciones, funciones, triggers y permisos.
9. Acceso/contexto vacío sin textos ni cuentas de demostración, tres tamaños y teclado.
10. Tipos regenerados, build, validación contractual, PostgreSQL y Playwright; resultados,
    fallos y omisiones explícitos. S3–S6 no implementados.

## Reglas siguientes

### Aceptación técnica S3

1. ADR previa; cuatro cuentas, auditoría, locks previos y migraciones conservados.
2. Dataset/etiquetas/manifiesto versionados; variables permitidas y escalas explícitas;
   validación temporal/revisiones y rechazo de configuración incompleta.
3. Pipeline por entrenamiento/fold, SVM escalado, Dummy/RF/SVM/XGBoost CPU; particiones
   comunes sin solapamiento por estudiante, soporte suficiente y folds efectivos.
4. Matriz LOW/MEDIUM/HIGH, soporte y métricas por clase/macro; null no estimable;
   sin calibración, probabilidades públicas null, sin ganador automático ni tesis evaluada.
5. Artefactos privados de procedencia interna, firmas/hashes/esquemas/versiones antes
   de deserializar, rechazo de rutas/symlinks/corrupción, round-trip de cuatro algoritmos.
6. Selección por matrícula/as_of, abstención, revisiones pendientes, unicidad snapshot/model,
   concurrencia/rollback/auditoría con riesgo_app y modelos de fixture inactivos.
7. Cuatro rutas reales, permisos/CSRF y errores contractuales; entrenamiento CLI y ejecución
   institucional bloqueados, ninguna activación ni procesamiento activo.
8. PostgreSQL aislado, contrato/tipos, pip check, build, navegador S2.2 y persistencia;
   comandos y resultados en cierre S3; sin datos escolares/modelos activos ni avance S4–S6.

### Dependencias institucionales

No reutilizar la antigua DEMO. La nueva solicitud S3.1 autoriza un generador de 60 estudiantes ficticios configurables bajo synthetic-study-v1; nunca se presentan como personas reales.
S3 conserva baseline, Random Forest, SVM y XGBoost según el plan académico, Pipeline,
separación por estudiante, prevención de fuga, trazabilidad y abstención.
No prometer precisión, fabricar riesgo bajo ni declarar evaluada la hipótesis.
S4/S5/S6 mantendrán permisos servidor/sección, UTC y días Lima, campos públicos,
evidencias inmutables, versiones esperadas y auditoría transaccional.
Los criterios previos detallados se preservan en history/Sprints_y_aceptacion_S2.md
como historia; las obligaciones de crear/entrenar/mostrar una demo quedan sustituidas.

### Aceptación S3.1

1. ADR previa y separación software/comparación sintética/evaluación real; revisión académica pendiente explícita.
2. Migración 0003 limpia y desde S3, orígenes y estudio coherentes por DB/servicios; 0001/0002 e histórico intactos.
3. Configuración/generación deterministas, 60 estudiantes por defecto, calendario cerrado, cinco variables, futuros resultados y faltantes.
4. CSV exacto registrado, preview sin filas académicas, confirmación atómica/versionada, claves verificadas a etiquetas privadas; REAL y archivos modificados bloqueados.
5. Desarrollo y reserva diferentes por persona/tiempo; etiquetas disponibles antes del ajuste; misma CV para cuatro algoritmos, sin tuning ni reserva en fit/selección.
6. Artefactos privados firmados/compatibles, registro y activación técnica ADMIN explícitos/auditados; probabilidades null y abstención.
7. GET processing/status, orígenes públicos, tipos/contrato 0.4.0 y aviso servidor; RESEARCHER sin casos/modelos; no pantallas S4.
8. Recorrido API/DB generado→importado→comparado→registrado→activado→inferido→consultado; repetición y permisos comprobados.
9. Regresión backend/contrato/build/navegador/persistencia; cuentas/secretos/volúmenes conservados, evidencia sanitizada y fallos/omisiones registrados.
10. Sin REAL, hipótesis validada, S4–S6, commit/push/despliegue externo.

### Aceptación S4

1. ADR previa; conservación de S3.1, cuentas/secretos, ML, migraciones, locks y volúmenes.
2. AppShell y rutas estables: recarga, atrás/adelante, 404 y acceso directo por rol; RESEARCHER sin llamadas escolares.
3. Contexto autorizado por API; cambio de periodo reinicia sección/filtros/página; vacío y errores útiles.
4. ProcessingStatus tipado y política efectiva: escrituras deshabilitadas ante fallo/bloqueo; REAL prohibido.
5. Lista/detalle/historial con filtros/paginación servidor; null, revisiones pendientes, riesgo con texto/icono/color y fechas Lima.
6. Datos en tres pasos, CSV exacto, GET lote, consentimiento de acción, expected_preview_version, CSRF, READY/COMMITTED, 409 y respuestas inciertas.
7. Exportación local ADMIN del CSV registrado: hash idéntico, destino fuera de Git y creación exclusiva; sin contenido/base64/secretos publicados.
8. Modelos públicos/evaluación sintética ADMIN: as_of actual o Lima explícito, created/reused/abstenciones; sin botones de entrenamiento/activación, métricas inventadas o probabilidades no calibradas.
9. Cancelación y limpieza por sesión/contexto, errores sanitizados y accesibilidad; navegador activo/aislado con API/PostgreSQL reales, primera importación aislada y repetición activa sin duplicados.
10. Typecheck/build, contrato/tipos, regresión backend, persistencia e inspección de capturas 1440×900, 768×1024 y 390×844; evidencias s4, fallos/omisiones explícitos. S5/S6 y validación institucional fuera de alcance.

### Aceptación S5

1. ADR previa, SHA inicial y conservación de cuentas/credenciales, sesiones/auditoría
   anteriores, locks, artefactos, modelo, predicciones y migraciones 0001–0003.
2. Migración 0004 limpia y desde S4; 15 tablas, evidencia única/inmutable por predicción,
   idempotencia original por actor/clave y guards de matrícula/origen/lote/modelo/estudio.
3. Política MEDIUM/HIGH/LOW vigente; última revisión/modelo compatibles, sin riesgo
   inventado, sin reapertura automática ni retroceso histórico de fuente.
4. Inferencia, seguimiento y auditoría en una transacción; locks DB comunes y unicidad;
   simultaneidad comprobada mediante coordinación/observación sin sleeps arbitrarios.
5. Permisos ADMIN/TUTOR/DIRECTOR/RESEARCHER efectivos; 404 propios/ajenos indistinguibles,
   CSRF, bloqueo de todas las escrituras de periodo y lectura autorizada preservada.
6. Alertas/intervenciones con versiones estrictas, transiciones terminales y razones;
   fecha efectiva explícita no futura, creación idempotente con digest original,
   actividades pendientes editables tras cierre y ausencia de cambios parciales.
7. Ocho operaciones nuevas reales: contrato 0.5.0, 27 operaciones/26 paths, tipos
   generados, ProcessingStatus por rol, errores JSON sanitizados y resultado de seguimiento.
8. Resumen sobre una matrícula actual por unidad; total=evaluados+pendientes+insuficientes,
   evaluados=LOW+MEDIUM+HIGH, conteos no multiplicados y porcentajes null sin denominador.
9. CSV completo filtrado/servidor, UTF-8 BOM, quoting/Unicode/control/fórmulas comprobados,
   sin narrativas/privados, nombre fijo/no-store y auditoría de solicitud sin filas.
10. UI Alertas/Reportes/Inicio/estudiante conectada; 409 conserva borrador y revisión,
    intento incierto conserva clave/payload, caché/cancelación por sesión y reloj API.
11. Recorrido aislado CSV→importación→evaluación UI→caso→actividades→cierre→resumen→CSV;
    cuatro roles, sección ajena/CSRF/409/teclado e inspección real de tres tamaños.
    Fallos HTTP simulados separados de respuestas positivas API/PostgreSQL.
12. Activo incorpora las 55 predicciones existentes por sincronización ADMIN explícita,
    verifica repetición/inferencia y mínimo seguimiento simulado conservado. Regresión,
    contrato/tipos/build/pip check, upgrade/persistencia y checker S5 con evidencia nueva.
    Resultados/fallos/omisiones registrados. S6, restauración final integrada y revisión
    académica pendientes; sin REAL, eficacia escolar, commit, push o despliegue externo.
