# ADR 009: integración y recuperación local S6

Fecha: 2026-10-04. Estado: aceptada para implementación; los resultados se registrarán en Estado_Sprint_6.md.

## Alcance y decisión

S6 cierra el software local para simulación. No habilita procesamiento REAL, aceptación institucional ni evaluación de la hipótesis. Se conservan OpenAPI 0.5.0, sus 27 operaciones, migración 0004_followup, 15 tablas, versiones y locks. No se regeneran el estudio ni el modelo activos. No se hace commit, push ni despliegue externo.

La evidencia distingue tres destinos: A, instalación nueva con secretos, base y tres volúmenes nuevos y preparación sintética explícita; B, restauración completa del estado S5 mediante respaldo, sin generación ni entrenamiento; C, revisión no destructiva del entorno activo. Cada herramienta S6 exige un descriptor privado explícito y comprueba proyecto, base, volúmenes, origen, puertos loopback e imágenes antes de escribir. Los recursos aislados llevan identificador y nombres S6 propios. No existe fallback a la aplicación activa ni opción force para sustituir recursos.

## Respaldo y recuperación

Se implementará una herramienta Python estándar operable desde PowerShell. El respaldo incluye dump custom completo de PostgreSQL, Alembic, todos los archivos privados de importación y ML incluida la clave HMAC, y los cinco secretos de infraestructura necesarios. No incluye el checkout, Credential Manager ni el entorno histórico DEMO. Los roles riesgo_owner y riesgo_app se recrean expresamente; el dump restaura ownership y ACL, y la API conserva riesgo_app sin privilegios de propietario.

La captura pausa brevemente los escritores web/API, comprueba comandos y conexiones concurrentes y mantiene PostgreSQL disponible. Una transacción de lectura con bloqueos SHARE y snapshot exportado protege la fotografía de todas las tablas durante el dump y la captura de archivos. try/finally reanuda exactamente los servicios inicialmente activos. La escritura binaria se realiza con subprocess y archivos binarios, sin redirección de texto PowerShell.

El paquete se guarda fuera del checkout, en directorio privado Windows, protegido íntegramente con DPAPI del usuario mediante CryptProtectData/CryptUnprotectData. Se comprueban realmente round-trip y alteración de bytes en Windows. La recuperación depende del perfil/equipo y de las condiciones de recuperación DPAPI; no se promete portabilidad entre equipos. Se exige registro local del respaldo propio, versión, inventario, tamaños, hashes, límites y rutas seguras antes de restaurar. Se rechazan traversal, duplicados y enlaces. Los temporales descifrados se limpian; el respaldo final se conserva y nunca se sobrescribe.

La restauración crea proyecto, base, puertos y volúmenes nuevos. pg_restore falla ante cualquier error; no se migran tablas antes ni se utiliza stamp. Antes de login se comparan las 15 tablas completas, usuarios, sesiones, auditoría, decisiones, Alembic y todos los archivos contra la fotografía. La clave HMAC se conserva: no se vuelve a firmar, entrenar o activar. La copia queda detenida e identificada al finalizar.

## Administrador propio e interfaz

El launcher leerá únicamente el acceso ADMIN solicitado. El acceso S2.2 se conserva. Un perfil de operador adicional usa entrada privada y se registra en un namespace Windows separado únicamente después de autenticar ADMIN contra el destino explícito. No crea usuarios, no impone la política de contraseña de fixtures y no sobrescribe entradas existentes. Las cuentas de instalación automática se crean mediante los servicios reales, permanecen exclusivas de pruebas y no son defaults del producto.

Solo se permiten correcciones concretas de foco y usabilidad: acceso al historial largo y eliminación de formularios vacíos inaplicables en casos cerrados, conservando borradores y conflictos 409. No cambian permisos, transiciones ni pipelines.

## Criterios técnicos de aceptación

- Instalación vacía comprobada con 15 tablas/head 0004 y riesgo_app; primer import e inferencia por interfaz, preparación sintética y comparación reproducible explícitas; recorrido de seguimiento y reportes con cuatro roles.
- Respaldo consistente, DPAPI nativo, verificación y restauración completa con fingerprints e inventario idénticos antes de login; pruebas negativas de corrupción, ausencia, incompatibilidad y colisión.
- Revisión API/UI de la copia y del activo: inferencia/sync reutilizan resultados, caso cerrado permanece cerrado, no aparecen nuevas actividades ni registros escolares. Cambios legítimos de sesiones/auditoría se separan.
- Caída real breve de PostgreSQL solo en copia aislada: Health 503 y Error 503 sanitizado, interfaz sin éxito falso y recuperación comprobada.
- Suite backend ampliada, pruebas de perfiles/recuperación, contrato/tipos, pip check, typecheck/build host e imágenes y diff check sobre el código final. Capturas reales en 1440×900, 768×1024 y 390×844 inspeccionadas sin afirmar certificación de accesibilidad.
- Documentación e índice finales con comandos PowerShell, destinos, hashes del código y locks, evidencia comprobada/fallida/no ejecutada y límites. Un criterio obligatorio sin ejecución deja el cierre pendiente.

## Consecuencias

Se añade infraestructura de recuperación y targeting sin dependencias nuevas. Los respaldos privados requieren custodia del usuario Windows y no sustituyen un plan institucional de continuidad. La simulación verifica software, no eficacia pedagógica ni validación académica. Se conserva toda evidencia S0–S5 y el entorno histórico detenido.
