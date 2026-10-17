# RGB y profundidad sincronizados — app v3

2026-10-16. Implementado y compilado; **instalación y captura física RGB-D pendientes**. La app anterior sigue activa en el teléfono: se verificó una solicitud depth con la conexión actual, sin metadatos de captura v3. Los códigos de acceso no se guardan en esta documentación.

## Instalación preparada

- IPA local: `dist/rgbd-v3/TrueDepthProbe-rgbd-v3.ipa`.
- Versión 0.3.0, build 3; mismo bundle `com.mati10p.truedepthprobe`.
- [Compilación correcta](https://github.com/Mati10P/truedepth-automotive-scanner/actions/runs/38987886041), commit iOS `10f93dbfca2d08db6fd3a00e51d4fb3d6b70a244`.
- SHA-256 IPA: `6088bb103b613249ebabc734a167f69c595c0c725dd48f26ec2446af7cf86e6e`.
- ZIP verificado contra digest de Actions: `cb850d7878b72d55db68e95c83aee8b495f5b056fa64798c634a3cb0260caa3a`.
- Antes del build: 20,7/3000 minutos incluidos usados, 0/2 GB de almacenamiento; presupuesto de consumo adicional Actions US$0 y bloqueado. No se cambiaron presupuestos.

Instalar la IPA mediante AltServer como en la instalación anterior. La pantalla nueva debe decir **TrueDepth · RGB-D v3**. Activar el sensor y usar el código nuevo que aparece al iniciar la app. La actualización aún debe probarse en el dispositivo; compilar no demuestra sincronización ni orientación correctas físicamente.

Desde Windows:

```powershell
./Capturar-RGBD.ps1 -Seconds 15 -Fps 1
```

El receptor pide IP y código, guarda ambos canales automáticamente y abre la vista de pares. También admite `python apps/windows/capture_sequence.py --transport rgbd --duration 15 --fps 1`. El modo RGB-D no se degrada silenciosamente al protocolo antiguo.

## Captura iOS

`AVCaptureDataOutputSynchronizer` coordina `AVCaptureVideoDataOutput` y `AVCaptureDepthDataOutput`. Solo se conserva un par si ambos contenedores existen, ninguno indica descarte y el timestamp del sample RGB difiere como máximo 1 ms del timestamp depth. No se emparejan dos buffers recientes obtenidos por callbacks independientes. El snapshot retenido contiene datos, timestamps, ID y configuración de la misma entrega, bajo bloqueo breve. La codificación se hace en la cola de preparación de red.

Depth continúa como float32 en metros sin filtrado ni cambio de escala. RGB se entrega como PNG sin redimensionar, codificado desde el buffer BGRA mediante Core Image a sRGB/RGBA8: es imagen procesada por la cámara y conversión de color, no datos Bayer RAW. PNG evita pérdidas adicionales de JPEG.

La app solicita rotación 0° cuando está soportada, desactiva espejo automático/espejo y estabilización cuando lo permite la conexión. Registra rotación, espejo y estabilización efectivos por canal; formato de vídeo/depth activo, tamaño y subtype, zoom y posición de lente. Conserva calibración original depth, intrínsecos, referencia y LUTs. El estado de orientación físico de pantalla no se interpreta como transformación de los buffers.

Cada par aceptado registra flags de descarte falsos y un contador acumulado de entregas rechazadas. El contador agrupa ausencia de canales, descartes y timestamps incompatibles; **no ofrece todavía motivos ni contadores separados por canal**. Tras dos segundos sin par aceptado reciente, la app rechaza solicitudes. Dentro de ese plazo pueden recibirse duplicados, identificados por ID/timestamp en Windows.

## Contrato TD3 y compatibilidad

Solicitud: `TD3 <codigo> <request_id>\n`, secuencial en conexión persistente con la misma telemetría TD2. La respuesta contiene:

1. Paquete depth `td-frame/1`: longitud JSON big endian, JSON, exactamente `payload_bytes` de depth.
2. Exactamente `header.rgb.payload_bytes` de PNG.
3. Longitud big endian y JSON de telemetría `td-telemetry/1`.

La cabecera conserva `sha256` y `payload_bytes` exclusivos de depth. Añade `rgb` (`td-rgb/1`, PNG, tamaño original, checksum propio, mismo frame ID, timestamp RGB, sRGB) y `synchronization` (método, flags, diferencia de timestamps y contador de rechazos). Los timestamps usan el reloj de captura, no UTC. Windows recalcula la diferencia desde los enteros value/timescale, exige ≤1 ms y comprueba que coincida con la declarada.

El receptor limita el PNG a 32 MiB y 20 megapíxeles, valida dimensiones IHDR, ambos checksums y telemetría antes de exponer el par. Tras un fallo borra el RGB pendiente y cierra la conexión: no combina el depth nuevo con color del intento anterior. El plazo total de solicitud incluye los dos canales y telemetría. `rgb_receive_validate_ms` separa el coste adicional; la llegada del frame se registra después de verificar ambos canales. No comparar tiempos RGB-D directamente con los ensayos depth-only como si el payload fuera igual.

TD1 y TD2 siguen devolviendo solo depth sin extensión RGB. Las capturas antiguas y el visor depth siguen siendo compatibles. El receptor original de una sola captura sigue usando TD1.

## Evidencia, inspección y marcas

Cada carpeta `frame-*` contiene `depth.f32le`, `rgb.png` y `metadata.json`. El visor vivo muestra el par aceptado como unidad y permite congelarlo, girar ambos canales 180° y marcar puntos. Al reanudar se descartan las marcas de inspección; el botón Guardar marcas descarga un JSON con ID, timestamps, checksums, canal y coordenadas nativas. El giro visual se invierte al guardar coordenadas. No se convierte automáticamente una marca RGB en una marca depth.

Para verificar originales guardados y abrir una vista offline:

```powershell
python tools/review_rgbd.py captures/<serie>/frame-000001
```

El generador verifica integridad antes de crear `pair-review.html` y no reemplaza una revisión existente. La revisión embebe el par, funciona sin servidor y permanece congelada. Los originales nunca se sobrescriben por marcar o girar.

**La sincronización temporal no prueba alineación geométrica.** La primera prueba física debe verificar orientación, correspondencia de los cuatro bordes y herraje, intrínsecos y punto exacto medido con cinta. No igualar resoluciones y asumir correspondencia, ni aceptar todavía mediciones dimensionales. No se implementó tracking, registro, reconstrucción o corrección de escala.

## Validación

33 pruebas Python pasan, incluyendo fragmentación, reutilización TCP TD3, integridad de ambos canales, incompatibilidad de frame ID, descartes, timestamps fuera de límite, tamaños fuera de límite, truncamiento, PNG inconsistente, telemetría incorrecta, ausencia de reutilización de color viejo, guardado de ambos originales y revisión offline. Se conservan las pruebas TD1/TD2 y de geometría.

El visor offline se probó en navegador con datos sintéticos etiquetados: ambas imágenes cargan, el giro cambia la vista y las marcas se guardan en coordenadas nativas independientes. La app Swift compiló con éxito en Xcode mediante el workflow existente. Falta probar captura real, coste de codificación PNG, frecuencia sostenida y orientación del RGB codificado en este iPhone.

Fuentes de API: [sincronizador](https://developer.apple.com/documentation/avfoundation/avcapturedataoutputsynchronizer), [depth sincronizado](https://developer.apple.com/documentation/avfoundation/avcapturesynchronizeddepthdata), [sample buffer sincronizado](https://developer.apple.com/documentation/avfoundation/avcapturesynchronizedsamplebufferdata).
