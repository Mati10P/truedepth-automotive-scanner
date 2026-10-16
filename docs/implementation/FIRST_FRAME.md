# Primer frame TrueDepth en Windows

Fecha: 2026-10-16. Dispositivo del usuario: iPhone 16e, iOS 26.6.

## Decisión y estado comprobado

REA/Ghidra e investigación adicional de ICP quedan en pausa. No son dependencias para probar captura y transporte. Se conservan las preguntas de investigación existentes; no hay procesos REA que detener de esta implementación.

Implementados localmente: fuente Swift de una app de captura, proyecto declarativo XcodeGen, workflow manual para producir una IPA sin firma, receptor Python y visor HTML local. Se verificaron seis pruebas del receptor (fragmentación, persistencia exacta, corrupción, truncamiento, límites y TCP local). La demostración sintética pasa por el mismo decodificador y checksum.

**Pendiente:** compilar con Xcode, instalar en el iPhone y recibir datos reales. No se dispone de Xcode en este Windows. El workflow no se ha ejecutado ni se ha generado una IPA. Ninguna prueba sintética confirma la compatibilidad física del teléfono ni de su firma. Este entregable es el primer tramo de fase 0, no su aceptación completa.

## 1. Ver ahora el receptor funcionando

Desde la raíz del proyecto:

```powershell
python apps/windows/receive_frame.py --demo
```

O ejecutar `Capturar-frame.ps1 -Demo`. Abre una visualización interactiva identificada como DEMO SINTÉTICA. Cambiar mínimo/máximo ajusta solo el color; pasar el mouse muestra la profundidad por píxel.

Python 3.11.9 ya está disponible en esta PC. No hay paquetes Python adicionales que instalar. Los resultados quedan en `captures/`, excluidos de Git.

## 2. Compilar la app

La ruta prevista desde Windows es GitHub Actions, usando un runner macOS estándar dentro de la cuota disponible del repositorio privado. Antes de ejecutarla comprobar minutos y presupuesto en GitHub; no se ha autorizado gasto. No hacen falta credenciales Apple en GitHub.

1. Subir los cambios de esta implementación al repositorio privado, incluyendo `.github/workflows/ios-probe.yml`.
2. En GitHub → Actions → **Build TrueDepth Probe (unsigned)** → Run workflow. El disparo es manual; no se ejecuta automáticamente al subir código. GitHub debe conocer el workflow en la rama predeterminada para mostrar su disparo manual.
3. Cuando termine correctamente, descargar el artefacto `TrueDepthProbe-unsigned` y extraer `TrueDepthProbe-unsigned.ipa`.
4. Conservar el log, que registra las versiones reales de Xcode y XcodeGen. El runner y Homebrew pueden actualizarse; todavía no es una compilación fijada byte a byte.

Alternativa con un Mac disponible: instalar Xcode y XcodeGen, ejecutar los comandos del workflow. Para instalación directa con Xcode, habilitar firma y seleccionar el equipo personal; el proyecto está configurado inicialmente para compilación sin firma.

## 3. Instalar desde Windows

Se elige **Sideloadly** para esta prueba; no hace falta instalar además AltServer.

- Descargar únicamente desde [Sideloadly oficial](https://sideloadly.io/). Seguir sus requisitos vigentes para Windows y componentes Apple. No se detectaron carpetas Sideloadly/AltServer en Program Files durante esta sesión; esto no descarta instalaciones portables o por usuario.
- Conectar el iPhone por cable, desbloquearlo y aceptar confiar en esta computadora.
- Seleccionar la IPA compilada y el teléfono en Sideloadly. La firma utiliza la cuenta Apple del usuario; ingresar credenciales y segundo factor directamente en esa aplicación, nunca en el repositorio o este chat.
- Completar la confianza del perfil y Modo de desarrollador si iOS lo solicita. Una cuenta gratuita exige renovar periódicamente la instalación según las restricciones vigentes de Apple/Sideloadly.
- La compatibilidad anunciada es iOS 26+; **iOS 26.6 en este teléfono sigue pendiente de prueba**, no garantizada por esta implementación.

Sideloadly firma/instala; no compila Swift. Por eso instalarlo por sí solo no produce nuestra app.

## 4. Obtener el primer frame real

1. PC e iPhone en la misma red Wi-Fi de confianza, sin aislamiento entre clientes. El servicio no usa nube, Bonjour ni requiere abrir un puerto entrante en Windows.
2. Abrir TrueDepthProbe en el teléfono, pulsar **Activar TrueDepth** y permitir cámara y red local. Mantener la app en primer plano. Si se niega un permiso, corregirlo en Ajustes y reiniciar la app.
3. Apuntar la **cámara frontal** a un objeto mate con relieve, inicialmente a unas decenas de centímetros como ensayo, sin asumir alcance ni precisión garantizados.
4. En Windows ejecutar `python apps/windows/receive_frame.py` o `Capturar-frame.ps1`. Ingresar la IP y código de 12 caracteres mostrados en el iPhone.
5. Se recibe una instantánea reciente; se verifica SHA-256 antes de guardarla y abrir el visor. Repetir el comando obtiene otra captura independiente.
6. Confirmar origen `iphone-truedepth`, dimensiones reales, timestamp de captura, píxeles válidos y calibración no nula. Si falta calibración, se conserva el frame y se indica que el hito está incompleto.

Si falla: comprobar IP, código, permisos, misma red y app abierta. El código cambia al reiniciar la app. Una conexión cerrada puede indicar código incorrecto o ausencia de frame reciente. La app muestra los fallos de cámara/red que detecta. El visor guarda la última captura solicitada, **no es vídeo en vivo**.

## Contrato td-frame/1

Windows inicia TCP al puerto 8765 del teléfono y envía exactamente `TD1 <código>\n`. iOS responde con 4 bytes de longitud JSON (uint32 big-endian), JSON UTF-8 y payload depth. Una solicitud por conexión, que luego se cierra. El código limita accesos accidentales, pero el transporte no está cifrado: usar una red local de confianza.

- Depth: float32 little-endian, metros, filas contiguas de `width * 4` bytes, sin padding. Se copia fila por fila desde CVPixelBuffer. NaN, infinitos y valores no positivos se conservan en el original y aparecen negros en el visor.
- Checksum SHA-256 del payload; máximo 1 MiB de JSON y 2048 × 2048 píxeles aceptados por el receptor.
- Timestamp: valor y timescale originales de CMTime; segundos adicionales para lectura. Reloj de captura, **no UTC ni reloj sincronizado con Windows**. Receipt registra aparte la hora UTC de recepción.
- Calibración opcional: matriz intrínseca por filas y dimensiones de referencia; extrínseca por filas; tamaño de píxel; centro y tablas de distorsión originales en base64. `null` significa no proporcionada, nunca una matriz inventada.
- El buffer mantiene su orientación nativa y se desactiva el espejo cuando la conexión lo permite. No se aplica rotación de pantalla ni rectificación. Las intrínsecas corresponden a sus dimensiones de referencia; no usarlas directamente como si fueran las dimensiones del mapa.
- Se incluyen formatos de video/depth disponibles, versión del SO, filtrado y calidad/exactitud declaradas por AVDepthData. El formato se elige entre capacidades reales; no se promete resolución o fps concretos.

Por captura: `depth.f32le`, `metadata.json`, `receipt.json`, `frame.html`. El HTML incluye una copia del depth para visualizarlo sin servidor ni dependencias externas. No se comparte automáticamente nada. La transferencia actual no implementa ACK durable ni reanudación; el teléfono mantiene solo el frame reciente en memoria. Los bloques recuperables del roadmap son un siguiente entregable.

No incluye todavía RGB sincronizado, IMU, controles de volumen, streaming continuo, USB, nubes 3D, ICP ni reconstrucción. No se genera una nube antes de validar calibración, distorsión y orientación con datos reales.

## Validación local

```powershell
python -m unittest discover -s tests -v
python apps/windows/receive_frame.py --demo --no-open
```

Fuentes consultadas: [captura TrueDepth de Apple](https://developer.apple.com/documentation/avfoundation/streaming-depth-data-from-the-truedepth-camera), [AVDepthData](https://developer.apple.com/documentation/avfoundation/avdepthdata), [Sideloadly FAQ](https://sideloadly.io/faq.html), [runners GitHub](https://github.com/actions/runner-images). La investigación necesaria se limitó a captura y ruta de compilación/instalación; no se reabrió REA.
