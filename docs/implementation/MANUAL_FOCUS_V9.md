# Foco manual remoto v9

La v8 solo acepta TD1/TD2/TD3 para lectura. La v9 agrega `TDF <codigo> status` y `TDF <codigo> set:<posicion>` terminados en LF. Una conexión por comando, respuesta JSON y cierre; mismo código de autenticación que la captura, sin registrarlo. Posiciones finitas de 0 a 1 y soporte de posición personalizada obligatorio.

Uso Windows: `python apps/windows/control_focus.py --host IP --token CODIGO --position 0.56078434`. Omitir posición consulta estado. El cliente espera hasta ocho segundos y solo acepta bloqueo confirmado, lente estable y diferencia menor a 0,0001 respecto al pedido. Verificar después pares RGB-D posteriores al bloqueo con `tools/verify_focus.py`.

La app guarda el objetivo manual y lo solicita de nuevo al activar cámara o regresar al primer plano. Cada solicitud crea un perfil nuevo; nunca reutiliza el perfil anterior. Autofocus explícito elimina el objetivo guardado. Si la lente cambia durante captura, se invalida el bloqueo y se dejan de entregar pares hasta una nueva solicitud. No se garantiza identidad óptica entre sesiones por repetir el valor de lente.

Evidencia del 22 de octubre: tablero inicial y caja tenían lente 0,5607843399 y perfil ABBF5B0C-538C-4F41-B1D2-975D6E0A8732. La siguiente toma tenía lente 0,4235293865, perfil FC5A893C-1C52-4F34-9FE2-EE13DBE55F89 y bloqueo sin confirmar. No hay evidencia suficiente para atribuir el reinicio a una acción del usuario o evento específico.

Validación local: siete pruebas de foco (incluye cuatro de cliente remoto) y seis de transporte RGB-D. La prueba física requiere instalar v9. Conservar RGB 1440x1080 y profundidad 640x480. Repetir referencia de caja bajo el perfil nuevo antes de calibrar.

API Apple: https://developer.apple.com/documentation/avfoundation/avcapturedevice/setfocusmodelocked(lensposition:completionhandler:)
