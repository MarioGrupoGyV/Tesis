# Registro manual M1

Abrir Seguimiento Escolar con una cuenta autorizada. El registro académico local
funciona sin modelo. Guardar una medición no evalúa riesgo por sí solo.
**Bloque 1 (2026-10-17):** en periodos SYNTHETIC con modelo técnico activo, ADMIN puede
pulsar «Evaluar riesgo de este estudiante» en la ficha para evaluar la última revisión
(simulación; sin valor de validación académica). REAL no se evalúa: sigue respondiendo
`INSTITUTIONAL_PROCESSING_NOT_READY`. Guion: [Guion_Demo_Manual.md](Guion_Demo_Manual.md).

1. **Preparar (ADMIN).** En Estudiantes → Periodos → Nuevo periodo, indicar
   código, año y fechas del mismo año, y escoger el origen efectivo REAL o
   SYNTHETIC. Después seleccionar el periodo y abrir Secciones → Nueva sección:
   grado, código y tutor activo existente. No se crean cuentas desde esta vista.
   Editar permite corregir catálogos; con matrículas se conserva su estructura.
   Bloquear o reabrir un periodo es una acción explícita en Editar periodo.
2. **Registrar (ADMIN).** Nuevo estudiante pide código, nombre y sección. Los
   espacios del código se normalizan y se usa mayúscula; las tildes del nombre
   se conservan. Revisar el resumen y guardar estudiante/matrícula juntos.
   Si el código ya existe, usar Buscar alumno existente y seleccionarlo para
   matricularlo en otro periodo del mismo origen. Nunca se reemplaza su identidad
   automáticamente. Crear sección desde este formulario conserva el borrador al
   regresar; Cancelar vuelve sin guardar la sección.
3. **Medir y consultar (ADMIN/TUTOR de la sección).** En la ficha, Mediciones →
   Nueva medición. Registrar ventana, corte y momento en que todos los datos ya
   estaban disponibles, en hora de Lima. Puede indicar disponibilidades distintas
   por variable. Promedio 0–20, asistencia/actividades 0–100 %, participación 1–5
   e incidencias enteras ≥0. Dejar vacío lo desconocido; cero sí es un dato. Basta
   una variable para una medición parcial. Guardar conserva esa ausencia y muestra
   pendiente de evaluación. Un promedio de cierre debe registrarse como
   Cierre/referencia; no se inventa fecha objetivo o horizonte futuro.

La fecha observada puede ser histórica. El servidor registra por separado el
autor y la digitación actuales en UTC; las pantallas muestran America/Lima.
Recargar permite comprobar lo guardado. La lista Mediciones conserva todas las
revisiones y sus valores; Historial muestra los eventos registrados.

**Corregir medición** crea otra revisión del mismo corte y exige motivo. La
anterior sigue disponible; ninguna evaluación anterior pasa a la nueva revisión.
Si otra persona corrigió primero, se conserva el borrador y se informa conflicto.
Consultar revisión actual conserva los valores escritos; revisarlos antes de
confirmar la corrección sobre la revisión vigente. Una misma clave de envío no
puede reutilizarse con contenido diferente. Ante conexión incierta, consultar
primero el resultado; no hay reintentos automáticos de escrituras.

**Editar datos / desactivar** es secundario y exclusivo ADMIN. Exige motivo y
confirmación. Desactivar conserva historial y bloquea nuevas escrituras; reactivar
es explícito. Cambiar sección de una matrícula con mediciones está bloqueado en
M1 para conservar el sentido histórico. No existe borrado físico en el producto.

DIRECTOR consulta sin modificar. RESEARCHER conserva su acceso general, sin
fichas nominativas. Recursos ajenos e inexistentes usan el mismo 404 seguro.
Los periodos bloqueados solo admiten consulta y la reapertura ADMIN explícita.

CSV conserva vista previa/confirmación y trazabilidad originales. No se importan
en M1 los tres Excel anunciados. Modelos conserva sus herramientas existentes;
el paquete retrospectivo eliminado del activo no se recupera. El origen REAL de
un registro manual no acredita autenticidad, autorización institucional,
consentimiento o elegibilidad y no habilita importación/entrenamiento/inferencia.
