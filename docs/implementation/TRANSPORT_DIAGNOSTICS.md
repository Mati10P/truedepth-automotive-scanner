# Diagnóstico del transporte persistente

2026-10-16. REA/ICP sigue en pausa. No se implementa todavía nube de puntos ni reconstrucción.

## Cambios

- iOS conserva el último frame bajo un bloqueo breve. La captura, la preparación (copia, calibración, SHA-256 y serialización), la red y el archivo de registro usan colas separadas.
- TCP persistente: una solicitud en curso, respuesta completa y luego siguiente solicitud. No hay cola de frames ni reintentos ocultos. Windows cierra y reconecta tras cualquier error; cada intento queda en CSV.
- Se elimina el cierre obligatorio a los diez segundos de vida de cada conexión. Cada fase de espera/solicitud tiene ahora un límite renovable de 15 segundos en iOS. Windows limita la solicitud entera a cinco segundos o al tiempo restante del ensayo, incluso si siguen llegando bytes poco a poco.
- iOS registra estados del listener/conexión, aceptación, recepción de solicitud, inicio y fin de envío y razón de cierre. El código de acceso y los mapas no se registran.
- La app ofrece **Compartir registro de transporte** para exportar el JSONL de la ejecución actual. Este archivo permite investigar también solicitudes fallidas que no pudieron devolver telemetría a Windows. Los registros anteriores permanecen en Documents de la app.

## Instalación y prueba

La compilación [38862697352](https://github.com/Mati10P/truedepth-automotive-scanner/actions/runs/38862697352), commit `8df583d`, terminó correctamente. IPA local: `dist/transport-v2/TrueDepthProbe-transport-v2.ipa`. SHA-256: `abf73984dba39a2cc4ff1cf664fcb463500132dd2e078983e63847ff99c2baaf`. El ZIP descargado se verificó contra el digest publicado por Actions. Antes del build se comprobaron 10,3/3000 minutos incluidos usados y presupuesto adicional de Actions de US$0 bloqueado.

1. Instalar con AltServer como en la prueba inicial. La pantalla debe decir **TrueDepth · transporte v2**.
2. Activar TrueDepth, conservar red, posición y condiciones de la prueba anterior y ejecutar `./Capturar-secuencia.ps1 -Seconds 600 -Fps 5`. Introducir IP y código actuales.
3. Conservar `measurements.csv`, `summary.json` e `ios-telemetry.jsonl`. Exportar además el registro del teléfono si hay pausas o errores.
4. Comparar con la evidencia anterior mediante:

```powershell
python tools/compare_transport.py captures/sequence-20261016T061829Z-0ce35e96 captures/<nueva-sesion>
```

El script genera `comparison.json` dentro de la sesión nueva. Referencia física: 2277/2309 frames, 3,8107 Hz, 32 errores (1,3859 %) y pausa máxima de 10,32 s. El [nuevo ensayo físico](PERSISTENT_TRANSPORT_RESULTS.md) terminó: 2889 frames válidos, cero errores, 4,8157 Hz y pausa máxima de 2,24 s.

La app antigua exige `-Transport legacy` o `--transport legacy`. No se degrada silenciosamente de TD2 a TD1, para no atribuir resultados al transporte equivocado.

## Contrato TD2

Solicitud ASCII: `TD2 <codigo> <request_id>\n`. ID decimal positivo creciente en cada conexión. Se envía solo la siguiente solicitud cuando se recibió toda la respuesta anterior. Límite de línea: 128 bytes. Líneas inválidas, pipelining y códigos incorrectos provocan cierre.

Respuesta: paquete `td-frame/1` original (uint32 big-endian de longitud JSON, JSON, payload) seguido de uint32 big-endian de longitud de telemetría y JSON `td-telemetry/1`. Windows limita la telemetría a 16 KiB, comprueba su ID y valores de tiempo y mantiene la conexión para el siguiente frame. El comando `TD1 <codigo>\n` conserva exactamente una respuesta sin tráiler y cierre.

El tráiler lleva `session_id`, `connection_id`, `request_id`, tamaño del paquete, instantes monotónicos de recepción de solicitud y fin de envío y duraciones por etapa. Es posterior al callback `.contentProcessed` del envío del frame. Ese callback indica procesamiento local del envío por Network.framework; **no confirma recepción remota ni persistencia en disco**. Windows verifica el payload por SHA-256 antes de aceptarlo y también exige el tráiler completo en modo persistente.

## Interpretación de tiempos

| Campo | Qué mide |
| --- | --- |
| `connect_ms` | Apertura TCP en Windows; cero si se reutilizó conexión. |
| `request_send_ms` | Entrega del comando a la pila TCP de Windows. |
| `first_byte_ms` | Desde que termina el envío del comando hasta el primer byte de respuesta recibido. Incluye esperas/preparación/red. |
| `header_ms` | Desde inicio de lectura de respuesta hasta cabecera completa y validada. Incluye la espera del primer byte. |
| `ios_queue_ms` | Espera desde solicitud válida hasta inicio de preparación. |
| `ios_prepare_ms` | Construcción completa del paquete en iOS, incluido checksum y JSON. |
| `ios_dispatch_ms` | Espera para volver a la cola de red después de preparar. |
| `ios_send_ms` | Desde llamada de envío hasta callback local de procesamiento. |
| `payload_receive_ms` | Lectura del payload en Windows después de validar cabecera. |
| `validation_ms` | Cálculo y comparación de checksum en Windows. |
| `request_ms` / `frame_request_ms` | Solicitud → frame validado; conserva la definición comparable con el ensayo anterior. En filas fallidas `request_ms` mide hasta el error. |
| `telemetry_ms` | Lectura y validación del tráiler posterior al frame. |
| `transaction_ms` | Conexión/solicitud, frame y tráiler completo. |
| `failure_stage` | Etapa en la que falló el intento; vacío para éxito. |

Envío iOS y recepción Windows se solapan: no se suman ni equivalen por separado a latencia de red pura. No se restan relojes entre dispositivos. La llegada usada para frecuencia e intervalo máximo se toma al verificar el payload, antes del tráiler; si el tráiler falla, la solicitud completa se registra fallida. Solo solicitudes válidas entran en los promedios/p95/máximos; las filas fallidas conservan los tiempos disponibles y el mensaje de error.

`summary.json` incluye conexiones, reconexiones, errores por mensaje, pausa máxima entre válidos y estadísticas por etapa. `comparison.json` también calcula el silencio máximo incluyendo el inicio y el final de cada sesión, para no esconder una desconexión al final. Los huecos de ID siguen siendo frames no muestreados, no pérdida de paquetes.

## Alcance de la validación

Compilación real de iOS verificada mediante Xcode en Actions. Pruebas Python ejercitan TCP local real, fragmentación, reutilización, corrupción, reconexión, tráiler faltante/inválido, límite total ante goteo lento y guardado de métricas. La repetición física de diez minutos confirma una mejora considerable; permanece una pausa aislada de 2,24 s en transferencia/recepción. Hay evidencia suficiente para comenzar un visor experimental, sin declarar resuelta toda la continuidad ni habilitar REA/ICP.
