# Enfoque controlado — RGB-D v4

2026-10-19. Versión preparada 0.4.0/build 4. Validación física pendiente; consultar el resultado de compilación antes de instalar. Mantiene el protocolo TD3 y agrega metadatos de enfoque por par.

## Uso antes de ChArUco

1. Activar TrueDepth y apuntar el centro al tablero, inicialmente a unos 35 cm.
2. Pulsar **Enfocar centro**, esperar a que el estado sea estable y pulsar **Bloquear foco actual**.
3. Esperar **Foco bloqueado** con un par nuevo. Capturar con `Capturar-RGBD.ps1`; verificar la serie con `python tools/verify_focus.py captures/<serie>`.
4. Conservar ese bloqueo durante las vistas del tablero y las medidas. Volver a enfocar crea otro identificador de perfil y requiere revalidar calibración. Salir de la app invalida el bloqueo para evitar reutilizarlo silenciosamente.

El bloqueo fija una posición de lente, no un intervalo de distancias. Acercarse/alejarse puede reducir nitidez. Comprobar legibilidad de esquinas a varias distancias manteniendo foco fijo, y limitar el rango de trabajo según evidencia. 20–50 cm es un rango propuesto para ensayar, no el rango óptimo TrueDepth ya demostrado. Si hace falta reenfocar, usar un perfil distinto. La posición normalizada de lente no se convierte directamente a centímetros.

## Implementación y límites

- Consulta soporte de foco bloqueado, autofocus, autofocus continuo y posición personalizada. El botón de enfoque usa autofocus puntual en el centro cuando se admite. El bloqueo mantiene la posición actual y no fuerza una posición arbitraria.
- Modo, ajuste en curso, posición, capacidades, estado lógico y UUID de perfil se guardan en `capture_settings.focus`. La lectura se toma en el callback sincronizado, no es metadato óptico exacto de exposición.
- Borra el último par al cambiar foco. Espera el callback de bloqueo, establece una frontera conservadora usando el reloj de sesión en ese momento y acepta solo timestamps RGB/depth posteriores. No compara directamente el timestamp de dispositivo devuelto por el callback con el reloj de samples.
- Verifica modo locked, ausencia de ajuste y posición dentro de 0,0001 de la confirmada. Si cambian, invalida y deja de entregar pares nuevos. Un timeout de cinco segundos invalida callbacks tardíos mediante generación de solicitud.
- Una solicitud de red que ya tomó un snapshot antes del cambio puede terminar con el perfil anterior; cada par conserva su estado original. El verificador rechaza perfiles mezclados y pares sin bloqueo confirmado.
- Sin soporte de bloqueo se informa limitación y se permiten capturas etiquetadas sin calibración de foco confirmada. No se afirma que la cámara esté bloqueada.
- La exposición y el balance de blancos continúan con la configuración existente. El bloqueo no garantiza nitidez ni precisión de depth. La app debe permanecer en primer plano durante el ensayo.

## Validación requerida

Compilar con Xcode mediante workflow existente. Pruebas Python: transporte RGB-D y verificación de foco (estable, cambio de perfil/lente, ajuste en curso y frames anteriores a frontera). En iPhone: observar enfoque, confirmar bloqueo, mover el tablero sin reenfocar y medir nitidez, comprobar posición constante, reintento, salida/retorno y rechazo de mezclas. Solo entonces usar el perfil para calibrar ChArUco.

Fuentes: [Apple: bloqueo de foco](https://developer.apple.com/documentation/avfoundation/avcapturedevice/setfocusmodelocked(lensposition:completionhandler:)), [posición de lente](https://developer.apple.com/documentation/avfoundation/avcapturedevice/lensposition).
