# Integración retrospectiva EVAL_RETRO_V1

Fecha: 2026-10-11, America/Lima. Solicitud explícita: integrar y verificar el
SVM del ZIP. El usuario confirma datos reales y autorización para procesamiento
local. Esta declaración no audita procedencia ni autoriza activación institucional.

Destino: módulo ADMIN de evaluación retrospectiva separado del contexto SYNTHETIC
activo. Paquete y nuevas ejecuciones en almacenamiento privado fuera del checkout;
no incorporar códigos ni filas al repositorio. No modificar las cuatro cuentas,
modelo activo, cortes, predicciones, alertas o intervenciones históricos.

1. Inspeccionar protocolo/artefacto, hash del ZIP y discrepancias con cinco variables
   del núcleo S3. Registrar tres entradas exactas y cortes B1/B2.
2. Implementar adaptador exclusivo app/ml, sin fit, sin scripts ejecutables del ZIP,
   con validación temporal/escala y propuestas sin notificaciones/intervenciones.
3. Registro CLI ADMIN explícito del paquete fijado por SHA-256; almacén privado
   autenticado y append-only. API con rol/CSRF servidor, lectura agregada y reporte
   anonimizado. Interfaz secundaria Modelos con historial/ejecución retrospectiva.
4. Reproducir las 60 filas derivadas B2 y contrastar todas las clases con el ZIP.
   Verificar scaler B1, no ajustar B2. Se localizó el Excel original en Downloads
   con el hash esperado: auditoría de 720 notas parciales, 240 ventanas y referencia
   RIESGO_V1 contra el CSV derivado. Verificar declaraciones no autentica el origen.
5. Pruebas ML/temporalidad/permisos/integridad/CSV, regresión backend en PostgreSQL
   aislado, contrato/tipos/build, recorrido navegador real y persistencia.
6. Documentar resultados reales, compatibilidad de versiones, limitaciones de
   sustento académico y diferencia entre cálculo del ZIP e integración nueva.

No hay S7, migración de datos académicos, commit/push ni servicio externo.
Las ejecuciones se fechan en UTC y se presentan en Lima. Toda divergencia de
versiones se registra: cargar un pickle de otra versión no acredita compatibilidad
soportada. Se mantienen los pins existentes y el único backend/.venv.
