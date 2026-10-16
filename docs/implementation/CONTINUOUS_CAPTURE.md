# Capturas sucesivas y medición

Actualización: 2026-10-16. El modo predeterminado ahora es TCP persistente y requiere instalar la app **transporte v2**. Para la app antigua: `./Capturar-secuencia.ps1 -Transport legacy`. REA/ICP sigue en pausa. Ver [protocolo, telemetría y ensayo comparativo](TRANSPORT_DIAGNOSTICS.md).

## Ejecutar con el iPhone

1. Mantener PC e iPhone en la misma red, abrir TrueDepthProbe y activar TrueDepth.
2. Desde la raíz del proyecto ejecutar `./Capturar-secuencia.ps1`. Ingresar IP y código de la app en la consola.
3. Se abre un visor local que actualiza el mapa de profundidad. La sesión dura 600 segundos y solicita como máximo 5 capturas por segundo, con una sola solicitud en curso.
4. Al terminar, el visor permanece disponible. Ctrl+C detiene la captura o cierra el visor si ya terminó.

Alternativa: `python apps/windows/capture_sequence.py --duration 600 --fps 5`.

Demo sin teléfono: `./Capturar-secuencia.ps1 -Demo -Seconds 30`. Usa un mapa sintético fijo con IDs y timestamps sucesivos; sus tiempos no representan rendimiento del iPhone o de la red.

## Qué mide

| Dato | Interpretación |
| --- | --- |
| Frecuencia recibida | (Respuestas válidas − 1) / intervalo entre primera y última recepción. Incluye duplicados; es media de sesión, no frecuencia instantánea. |
| Sensor estimado | Diferencia de IDs / diferencia de timestamps de captura entre respuestas distintas consecutivas. Estima callbacks entregados por iOS, no detecta descartes anteriores al callback. |
| Solicitud media / p95 / máximo | Desde antes de conectar TCP hasta recibir y verificar el payload completo. Incluye conexión, preparación, transferencia y SHA-256. Solo solicitudes válidas. |
| Fallidas | Solicitudes con timeout, conexión interrumpida, protocolo inválido o checksum incorrecto. No son paquetes TCP perdidos. |
| Únicos / duplicados | Respuestas distintas y repeticiones del mismo ID y timestamp. |
| No muestreados | Suma de huecos de IDs entre respuestas válidas. La app devuelve el frame más reciente y no envía los intermedios; no es pérdida de red. |
| Discontinuidades | ID o timestamp retroceden, o cambian de forma incompatible. No se cuenta el salto como pérdida; se reinicia la referencia. |
| Omitidos por la pestaña | Respuestas válidas que el visor no llegó a mostrar desde su primera actualización; no afecta al CSV. |

No se resta el timestamp de iOS del reloj de Windows: no están sincronizados. La latencia completa sensor → pantalla queda pendiente. La antigüedad mostrada corresponde a la última recepción en Windows, no a la captura. El refresco del navegador consulta el último frame cada 200 ms, sin cola; pestañas en segundo plano pueden refrescar más lentamente.

El modo `persistent` reutiliza una conexión TCP y recibe telemetría de iOS después de cada frame. `legacy` conserva una conexión por solicitud para la app antigua. Ambos muestrean el frame más reciente; no envían todos los frames del sensor ni miden retransmisiones TCP.

## Archivos y límites

Cada ejecución crea `captures/sequence-<fecha>-<id>/`:

- `measurements.csv`: una fila por solicitud, tiempo, ID, timestamp, resultado y error si corresponde. Se vacía el buffer después de cada fila; no equivale a un ACK durable.
- `summary.json`: configuración básica, duración observada y métricas finales, incluso al detener con Ctrl+C.
- Con `-SaveDepth` o `--save-depth`: carpetas por respuesta válida, con `depth.f32le` y `metadata.json` originales. Incluye duplicados. A 640 × 480, 5 Hz y 10 minutos, solo depth ocupa aproximadamente 3,69 GB decimales. El guardado puede reducir la frecuencia observada.

Por defecto el mapa vive solo en memoria y se conservan las mediciones. Un error al guardar originales detiene la sesión; los errores de recepción se registran y se reintentan en el siguiente ciclo. Un cierre forzado del proceso puede impedir escribir el resumen; el CSV conserva las filas ya escritas. No hay recuperación de captura en el teléfono.

El visor escucha únicamente en `127.0.0.1` y usa un puerto libre. No publica archivos ni el código de acceso. La comunicación con el teléfono usa TD2 en modo persistente y conserva TD1 en modo legacy y requiere la misma red local de confianza. Los resultados permanecen excluidos de Git.

## Validación

`python -m unittest discover -s tests -v`: 11 pruebas pasan, incluyendo protocolo fragmentado, corrupción, truncamiento, almacenamiento exacto, IDs duplicados, saltos, reinicio de secuencia, tasas/p95, servidor HTTP local y recuperación tras checksum corrupto por TCP real local.

Demo local de 30 segundos verificada en el navegador: 145/145 respuestas válidas, aproximadamente 4,8 Hz y cero errores. Es una comprobación sintética del circuito, no evidencia de rendimiento físico. Después se completó el [ensayo de diez minutos con el iPhone](CONTINUOUS_CAPTURE_RESULTS.md): 2277 frames válidos, 32 solicitudes fallidas y pausas de hasta 10,32 segundos. La continuidad aún necesita mejoras.

Para una comparación reproducible: mantener resolución y objeto, anotar red/distancia y ahorro de energía, ejecutar primero a 5 Hz por diez minutos, conservar CSV/resumen, y comparar luego otras frecuencias y USB cuando esté disponible. No declarar fase 0 completa hasta validar también los demás criterios del roadmap.
