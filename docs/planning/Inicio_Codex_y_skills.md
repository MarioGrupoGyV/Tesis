# Inicio de trabajo — alcance vigente S3

Leer AGENTS.md, README, Estado_Sprint_3.md, Estado_Sprint_2_2.md, Estado_Sprint_2_1.md, ADR 004/005, Plan_tesis_riesgo_escolar.md,
Sprints_y_aceptacion.md, Contrato_API.yaml y Esquema.sql antes de modificar.
Los cierres S0/S1/S2 y documentos en history son evidencia histórica, no instrucciones.

Usar PowerShell en Windows y Docker Desktop. infra/manage.py prepara infraestructura,
arranca, migra, reinicia, detiene y permite bootstrap explícito. No instalar una
distribución, GNU Make ni exigir terminal WSL. Python 3.12.12 de backend ejecuta
dentro del contenedor; el launcher del host solo coordina. Runtimes/locks conservados.

No crear cuentas predeterminadas, semillas, generadores, ejemplos escolares en el
entorno activo ni modos de demostración. No habilitar importación institucional:
falta protocolo de procedencia, escala, periodo, ventana, fechas y calidad.
Fixtures fabricados solo en bases aisladas de prueba, identificados como tales.
No enviar contraseñas por argumentos, archivos de cuentas o logs.

Conservar separación rutas/esquemas/servicios/repositorios/ML; contrato antes de UI.
Migraciones nuevas revisadas manualmente; ORM parcial no representa trece tablas.
No descartar cambios del usuario ni datos existentes. Probar con riesgo_app; propietario
solo para migración/diagnóstico. Respaldo y restauración preceden a retirar un entorno.

S3 aporta infraestructura predictiva y pruebas aisladas; entrenamiento institucional
requiere dataset autorizado y etiquetas futuras verificables. Mantener baseline,
Random Forest/SVM/XGBoost según plan, separación por estudiante, Pipeline sin fuga,
trazabilidad y abstención. Sin modelo: Modelo no disponible. No avanzar sin encargo.

No recrear cuentas S2.2 ni sus credenciales Windows. ML usa volumen privado separado,
manifestación de alcance aislado y confianza interna; una firma/hash no aprueba un
modelo institucional. Ambas restricciones de activación siguen vigentes. Consultar
docs/manuals/ML_S3.md. S4–S6 requieren nuevo encargo.

Elegir skills por necesidad real, no por palabras clave. Ninguna skill autoriza
cambiar metodología, enviar mensajes a terceros ni cargar datos personales.
Cierre: comandos PowerShell, host y runtime reales, comprobado/fallido/no ejecutado,
evidencias, archivos y dependencia siguiente. No fabricar pruebas visuales o métricas.
