# Ensayo físico de capturas sucesivas — 2026-10-16

Prueba de 600,01 segundos con iPhone 16e, iOS 26.6 (23G71), mapas TrueDepth 640 × 480, conexión Wi-Fi y app instalada sin cambios. Receptor configurado para un máximo de 5 solicitudes/s, una conexión TCP por solicitud. REA/ICP permanece en pausa.

## Resultados

| Medición | Resultado |
| --- | ---: |
| Solicitudes | 2309 |
| Frames recibidos y verificados por SHA-256 | 2277 |
| Solicitudes fallidas | 32 (1,39 %) |
| Frecuencia recibida, media entre primera y última recepción | 3,81 Hz |
| Tiempo de solicitud válida, media | 124,24 ms |
| Tiempo de solicitud válida, p95 | 149,73 ms |
| Tiempo de solicitud válida, máximo | 3244,37 ms |
| Mayor intervalo entre recepciones válidas | 10,32 s |
| Duplicados / discontinuidades de secuencia | 0 / 0 |
| Errores de checksum registrados | 0 |
| IDs del sensor intermedios no recibidos | 12808 |

Los 32 fallos se dividen en 13 timeouts y 19 rechazos de conexión (`WinError 10061`). El receptor reanudó la recepción automáticamente. El minuto 7 fue el peor: 147 frames y 8 errores. El minuto 9 recibió 276 frames sin errores.

## Interpretación

Se verificó adquisición sucesiva durante diez minutos y recuperación automática ante fallos de solicitud. La continuidad aún no es adecuada para asumir un flujo estable: hubo pausas de hasta 10,32 segundos y no se sostuvo el objetivo de 5 Hz.

El tiempo de solicitud incluye conexión, preparación, transferencia y validación. No representa latencia sensor → pantalla. Los 12808 IDs intermedios combinan el muestreo deliberado del frame más reciente y los intervalos sin recepción; no son paquetes perdidos ni una medida de pérdidas de red. El contador de iOS tampoco mide descartes previos al callback del sensor.

Esta prueba no identifica la causa de los rechazos y timeouts: hace falta instrumentar el servicio iOS y correlacionar conexión/captura/envío antes de atribuirlos al Wi-Fi. El siguiente trabajo recomendado es diagnosticar estas pausas y evaluar una conexión persistente con telemetría, antes de añadir reconstrucción 3D. No se declara completada toda la fase 0.

## Evidencia y reproducción

Evidencia local excluida de Git: `captures/sequence-20261016T061829Z-0ce35e96/measurements.csv`, `summary.json` y `analysis.json`. No se guardaron mapas de profundidad en esta sesión: se conservaron las mediciones y los originales solo pasaron por memoria para validar y visualizar.

`analysis.json` agrupa errores por mensaje, cuenta resultados por intervalos de 60 segundos desde el inicio y calcula la diferencia máxima de `elapsed_s` entre respuestas válidas consecutivas. El porcentaje de fallos es 32/2309 × 100. El resumen utiliza percentil p95 por rango más próximo sobre solicitudes válidas.

Para repetir: `./Capturar-secuencia.ps1 -Seconds 600 -Fps 5`, con TrueDepthProbe activa en primer plano, ingresando IP y código actuales en la consola. Conservar las condiciones de red y anotar cualquier cambio de app, dispositivo o ahorro de energía.
