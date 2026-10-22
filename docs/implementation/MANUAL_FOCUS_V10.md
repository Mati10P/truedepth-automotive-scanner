# Foco remoto v10

La solicitud manual se transmite sin compensaciones ni redondeo decimal a nueve cifras desde Windows; AVFoundation recibe Float, su tipo nativo. La app conserva requested_position separado de lens_position. No se garantiza igualdad física con el número solicitado.

La confirmación requiere callback de finalización, modo locked, isAdjustingFocus falso y posición real estable dentro de 0,0001 durante al menos 0,5 segundos de observaciones. Cambios reinician la ventana. Capturas posteriores usan un perfil nuevo y límite del reloj de sincronización; cambios posteriores invalidan el bloqueo. El estado remoto y los metadatos conservan solicitado y real. La UI muestra ambos.

No se corrigió por un supuesto escalón de 1/255: dos observaciones no prueban una transferencia universal. En v9 solicitar 0,529411793 devolvió 0,5333333015; solicitar 0,533333333 devolvió 0,5372549295.

Siete pruebas Python de foco aprobadas. La estabilidad óptica y comportamiento físico de v10 requieren instalarla y repetir tablero y caja con el mismo perfil.
