# Inicio de trabajo — alcance vigente S5

Leer AGENTS.md, README, Estado_Sprint_5.md, Manual_Seguimiento_Reportes_S5.md, ADR 008, matriz S5 y Estado_Sprint_4.md, Manual_Uso_S4.md, ADR 007 y Estado_Sprint_3_1.md y cierres S3/S2.2/S2.1, ADR 004/005/006,
Manual_Estudio_Sintetico.md, Plan_tesis_riesgo_escolar.md, Sprints_y_aceptacion.md,
Contrato_API.yaml y Esquema.sql antes de modificar.
Los cierres S0/S1/S2 y documentos en history son evidencia histórica, no instrucciones.

Usar PowerShell en Windows y Docker Desktop. infra/manage.py prepara infraestructura,
arranca, migra, reinicia, detiene y permite bootstrap explícito. No instalar una
distribución, GNU Make ni exigir terminal WSL. Python 3.12.12 de backend ejecuta
dentro del contenedor; el launcher del host solo coordina. Runtimes/locks conservados.

No crear cuentas predeterminadas, semillas al arrancar ni modos de demostración.
S3.1 autoriza exclusivamente generación/importación controlada de SYNTHETIC mediante
comandos ADMIN explícitos y CSV registrado exacto. No habilitar importación institucional:
falta protocolo de procedencia, escala, periodo, ventana, fechas y calidad.
Los fixtures de prueba permanecen aislados; el estudio activo identifica sus
registros generados como SYNTHETIC, sin convertirlos en información institucional.
No enviar contraseñas por argumentos, archivos de cuentas o logs.

Conservar separación rutas/esquemas/servicios/repositorios/ML; contrato antes de UI.
Migraciones nuevas revisadas manualmente; no usar autogeneración con la metadata ORM parcial.
No descartar cambios del usuario ni datos existentes. Probar con riesgo_app; propietario
solo para migración/diagnóstico. Respaldo y restauración preceden a retirar un entorno.

S3 aporta infraestructura predictiva y pruebas aisladas; entrenamiento institucional
requiere dataset autorizado y etiquetas futuras verificables. Mantener baseline,
Random Forest/SVM/XGBoost según plan, separación por estudiante, Pipeline sin fuga,
trazabilidad y abstención. Sin modelo: Modelo no disponible. No avanzar sin encargo.

No recrear cuentas S2.2 ni sus credenciales Windows. ML usa volumen privado separado,
manifiestos v2 SYNTHETIC_STUDY/SYNTHETIC y compatibilidad con v1 ISOLATED_TEST/REAL de
las pruebas S3. Una firma/hash no aprueba un modelo institucional. 0003 sustituye
las restricciones de activación por aprobación técnica exclusivamente SYNTHETIC;
REAL sigue prohibido. Consultar los manuales ML y del estudio. S4 conecta acceso, Inicio, Estudiantes, Datos y Modelos. S5 está autorizado para seguimiento/resumen/CSV sintéticos. Únicamente migración 0004 y orquestación transaccional inferencia/seguimiento; no modificar matemática ML, migraciones 0001–0003, criterios ni regenerar/reentrenar el estudio activo. S6 requiere nuevo encargo.

Elegir skills por necesidad real, no por palabras clave. Ninguna skill autoriza
cambiar metodología, enviar mensajes a terceros ni cargar datos personales.
Cierre: comandos PowerShell, host y runtime reales, comprobado/fallido/no ejecutado,
evidencias, archivos y dependencia siguiente. No fabricar pruebas visuales o métricas.

Consultar también Estado_Sprint_3_1.md y contrato 0.5.0; no reescribir los cierres ni migraciones históricos.

S5 conserva locks y extiende API a 0.5.0; TanStack Query, rutas estables, contexto y caché por actor. ProcessingStatus fallido deshabilita escrituras; no inferir preparación desde health. Evidencias nuevas prefijo s5, historial inmutable. ADMIN sincroniza, ADMIN/TUTOR gestionan según sección, DIRECTOR solo consulta/exporta y RESEARCHER mantiene sesión/Inicio limitado. CSV actual por matrícula, auditar solicitud sin afirmar apertura/guardado. No usar checker de base vacía ni check_s4 sobre seguimiento ya poblado; usar check_s5.
