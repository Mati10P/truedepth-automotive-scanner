# Ensayo físico de TCP persistente — 2026-10-16

Duración: 600,02 s. iPhone TrueDepth, 640 × 480, Wi-Fi, objetivo 5 Hz, sin guardar originales depth. App transporte v2 compilada desde `8df583d`; receptor de la implementación `69290bc`. REA/ICP sigue en pausa.

| Medición | Anterior: TCP por frame | TCP persistente |
| --- | ---: | ---: |
| Frames válidos | 2277 | 2889 |
| Solicitudes | 2309 | 2889 |
| Errores | 32 (1,39 %) | 0 |
| Frecuencia recibida | 3,81 Hz | 4,82 Hz |
| Solicitud media | 124,24 ms | 71,02 ms |
| Solicitud p95 | 149,73 ms | 102,86 ms |
| Solicitud válida máxima | 3244,37 ms | 2120,12 ms |
| Mayor intervalo entre válidos | 10,32 s | 2,24 s |
| Conexiones TCP | Una por solicitud | 1 |
| Reconexiones durante la sesión | No aplica | 0 |
| Duplicados / discontinuidades | 0 / 0 | 0 / 0 |

La frecuencia mejoró aproximadamente 26,4 % y el intervalo máximo disminuyó 78,3 %. No hubo timeouts, rechazos de conexión ni errores de checksum en este ensayo. Cada uno de los 2889 registros CSV corresponde a una telemetría iOS con el mismo request ID, y todos pertenecen a una única conexión iOS.

## Dónde estuvo la pausa

La solicitud 26 tardó 2120,12 ms. Sus etapas fueron: espera del primer byte 13,39 ms, preparación iOS 4,42 ms, procesamiento local del envío iOS 51,73 ms, recepción del payload en Windows 2105,28 ms y validación 0,63 ms. El intervalo entre recepciones válidas fue 2,2374 s.

El retraso se concentra en transferencia/recepción, no en construir el frame. El callback de envío de iOS no confirma recepción remota: estos datos no permiten atribuirlo exclusivamente al Wi-Fi ni separar retransmisiones de esperas de las pilas TCP o de planificación del receptor. Las etapas entre dispositivos se solapan; no se suman y no se restan relojes distintos.

| Etapa | Media | p95 | Máximo |
| --- | ---: | ---: | ---: |
| Cola de preparación iOS | 0,91 ms | 1,21 ms | 3,17 ms |
| Preparación iOS | 6,33 ms | 8,04 ms | 9,69 ms |
| Procesamiento local de envío iOS | 7,00 ms | 26,69 ms | 313,29 ms |
| Recepción de payload Windows | 39,75 ms | 69,98 ms | 2105,28 ms |
| Validación SHA-256 Windows | 0,80 ms | 1,11 ms | 9,36 ms |

Los diez minutos recibieron respectivamente 280, 290, 290, 290, 290, 290, 291, 288, 290 y 290 frames; todos sin errores. La frecuencia inferior a 5 Hz también incluye el ritmo de solicitudes, la espera del sistema y el trabajo local entre solicitudes; no equivale directamente a insuficiencia de ancho de banda.

## Decisión y límites

El transporte permite avanzar a un **visor experimental de nube de puntos** con manejo explícito de antigüedad y pausas, conservando la telemetría. Todavía no se puede declarar flujo sin pausas ni aptitud para tracking continuo. REA/ICP permanece en pausa y no se declara completada la fase 0.

Se cambiaron simultáneamente persistencia TCP, separación de colas y telemetría. El ensayo demuestra mejora del conjunto; no aísla cuánto aporta cada cambio ni garantiza el mismo resultado en otras condiciones de red. El registro local iOS queda disponible en la app para exportación; los tráileres recibidos ya están preservados en Windows.

## Evidencia

Carpeta local excluida de Git: `captures/sequence-20261016T064701Z-c710126a/`, con `measurements.csv`, `summary.json`, `ios-telemetry.jsonl`, `session_metadata.json` y `comparison.json`. La finalización del proceso de captura y la escritura de estos archivos no dependieron de que Codex siguiera respondiendo.

Reproducir la comparación:

```powershell
python tools/compare_transport.py captures/sequence-20261016T061829Z-0ce35e96 captures/sequence-20261016T064701Z-c710126a
```
