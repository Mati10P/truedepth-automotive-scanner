# Escáner de mano TrueDepth y estación de trabajo Windows

Fecha de investigación: 2026-10-13.

Esta especificación incorpora el flujo descrito por el usuario y las 18 capturas de EXStar. Las imágenes son referencias de interacción, no pruebas de las capacidades de TrueDepth. Los resultados siguientes proceden de documentación; todavía no se han probado en el iPhone ni en la PC del usuario.

## 1. Decisión de producto

El iPhone se utiliza como cabezal de captura de mano. La PC es la estación principal: configura, muestra el escaneo en vivo, conserva el proyecto, permite inspeccionar y reanudar, limpia, alinea, genera mallas y exporta. Blender es un destino y una integración posterior; el flujo principal no necesita tener Blender abierto.

La pantalla del iPhone apunta al objeto durante la captura. La app muestra conexión y estado mínimo, mantiene la cámara activa y ofrece controles físicos y avisos. El usuario no necesita mirar esa pantalla para escanear.

## 2. Qué está documentado y qué falta verificar

| Tema | Evidencia y conclusión | Prueba pendiente |
|---|---|---|
| Profundidad y color frontal | Apple ofrece captura TrueDepth con RGB y profundidad sincronizados mediante AVFoundation. Usaremos ese par RGB-D. [Apple](https://developer.apple.com/documentation/avfoundation/streaming-depth-data-from-the-truedepth-camera) | Formatos, frecuencia, estabilidad térmica y calidad efectiva del iPhone 16e. |
| Botones de volumen | AVCaptureEventInteraction permite recibir acciones de volumen con una sesión de cámara activa; no entrega estos eventos en segundo plano. [Apple WWDC25](https://developer.apple.com/videos/play/wwdc2025/253/) | Validar eventos, cancelaciones y feedback en la versión instalada de iOS. |
| USB-C | El iPhone 16e usa USB 2, hasta 480 Mb/s nominales. [Apple](https://support.apple.com/en-us/122208) | Caudal útil, latencia, cable, controlador y desconexiones. No equivale a 480 MB/s. |
| Túnel USB | libusbmuxd documenta Windows e iproxy para reenviar un puerto de PC a un servicio en iOS. [Proyecto](https://github.com/libimobiledevice/libusbmuxd) | Nuestro servicio iOS, emparejamiento, controlador Apple y transporte de sesiones largas. |
| Red por USB | Apple documenta Personal Hotspot por USB con Windows y Apple Devices/iTunes. [Apple](https://support.apple.com/en-ca/guide/iphone/iph45447ca6/ios) | Disponibilidad del hotspot y comunicación local entre nuestra app y la PC; no tomarlo como requisito del producto. |
| Calibración | AVDepthData puede entregar parámetros de calibración para interpretar la captura. [Apple](https://developer.apple.com/documentation/avfoundation/avdepthdata/cameracalibrationdata) | Exactitud métrica, sesgos y rectificación correcta. |
| Balance de blancos | AVFoundation ofrece ajuste y bloqueo de ganancias, sujeto a capacidades del dispositivo. [Apple](https://developer.apple.com/documentation/avfoundation/capture-device-white-balance) | Consistencia del color bajo la iluminación de trabajo. |
| Cámaras simultáneas | Las combinaciones admitidas se consultan en el dispositivo. [Apple](https://developer.apple.com/documentation/avfoundation/avcapturedevice/discoverysession/supportedmulticamdevicesets) | No se ha confirmado una configuración concreta del 16e con profundidad frontal y cámara trasera simultáneas. |

## 3. USB, Wi-Fi y distribución del procesamiento

### Transporte

Se implementará un contrato de captura común con adaptadores Wi-Fi y USB. La PC inicia la conexión al servicio de la app iOS: directamente por la red local o por el puerto local reenviado mediante iproxy. La app debe estar abierta; conectar el cable no sustituye a la app ni expone directamente TrueDepth como periférico de profundidad estándar.

USB es el transporte preferido para la experiencia de uso solicitada, condicionado a superar la prueba física. Wi-Fi será un transporte completo y la primera referencia funcional para aislar problemas de captura de los del puente USB. No se requiere subir escaneos a Internet. Personal Hotspot por USB queda como alternativa de investigación si falla el túnel, no como dependencia de una tarifa de datos.

El puente USB deberá respetar las licencias de sus componentes al distribuirse. La conexión Wi-Fi requerirá permiso de red local y emparejamiento explícito con la PC. El teléfono conservará bloques de captura hasta confirmar su recepción persistente.

Prueba de transporte: misma carga, perfil y duración de 10 minutos por USB y Wi-Fi; medir MB/s reales, retraso percentil 95, integridad, frames omitidos, batería y temperatura. Incluir desenchufar/reconectar y saturación de la PC. Cambiar de transporte abre una conexión nueva y deduplica por sesión/frame, sin integrar dos veces los mismos datos.

Ejemplo de presupuesto, NO formato confirmado del sensor: profundidad float32 de 640×480 a 15 fps requiere aproximadamente 18,4 MB/s; RGB de 640×480 sin compresión, 13,8 MB/s. El total supera 32 MB/s antes del protocolo. Por eso se medirán formatos reales y se comprimirán datos cuando convenga. La profundidad persistida no tendrá compresión con pérdida.

### Procesamiento

| iPhone | PC |
|---|---|
| Acceso al sensor mediante iOS y sincronización RGB-D | Tracking, búsqueda de referencias y validación de poses |
| Lectura de calibración y movimiento | Fusión local, nube acumulada y mapa de calidad |
| Compresión, envío y respaldo temporal | Visor, herramientas y almacenamiento principal |
| Botones físicos, audio y háptica | Alineación entre proyectos y reconstrucción final |
| Estado térmico y diagnóstico | Edición de malla y exportación |

Esta distribución es el punto de partida de ingeniería. No se supone que la PC de 8 GB sea más rápida que el iPhone en cualquier operación. Se medirá tiempo de captura, envío, tracking, fusión y render por separado. Si la PC no alcanza el objetivo, primero se reducirán resolución de trabajo y carga visual, manteniendo los originales; después se portarán al iPhone operaciones concretas que el perfilado identifique. El flujo de usuario permanece igual.

La PC no será un simple monitor: mantiene el estado del proyecto y controla la reconstrucción. Tampoco hace falta generar la malla final a máxima resolución durante cada frame. El preview será una nube de puntos o surfels, con una superficie provisional opcional claramente identificada.

## 4. Controles físicos y estados

- Volumen arriba: iniciar o solicitar reanudación.
- Volumen abajo: pausar, sin finalizar el proyecto ni borrar datos.
- Finalizar captura/generar nube: acción en la PC, distinta de pausar.
- Eventos físicos procesados al soltar el botón, con protección contra duplicados; una cancelación no inicia captura.
- La cámara sigue activa durante preview, pausa y relocalización, salvo interrupción del sistema. Así los controles pueden seguir recibiéndose.
- Al bloquearse el teléfono, pasar la app al fondo o perderse la cámara: pausar y conservar datos. Al volver, exigir relocalización.
- Reanudar sobre datos existentes cambia a ALINEANDO. Solo tras validar pose se vuelve a ESCANEANDO. Girar el visor con el mouse nunca modifica la pose del escáner.
- Volumen abajo detiene inmediatamente la aceptación local de nuevos frames; el comando lleva una frontera de frame para excluir datos en vuelo posteriores a esa pausa.
- Desconexión de PC: pausa y feedback local; los bloques pendientes se conservan. La reconexión no reanuda integración automáticamente.

La asignación diferenciada de volumen arriba/abajo usa los manejadores secundario/primario documentados por Apple. Su adaptación concreta se comprobará en el SDK y teléfono elegidos. [Eventos de captura](https://developer.apple.com/videos/play/wwdc2025/253/)

## 5. Preparación: verificación y color

El primer paso de la estación será Conectar → Verificar sensor → Ajustar color, si corresponde.

La calibración disponible en la captura se utilizará para rectificar los mapas, interpretar sus unidades y relacionar color/profundidad. No se copiará automáticamente la rutina de tablero de EINSTAR. La documentación consultada no establece que haya que repetir esa rutina antes de usar TrueDepth.

Se ofrecerá una verificación dimensional inicial con plano y distancias conocidas. Si aparece un sesgo reproducible, una fase posterior podrá ajustar un perfil de corrección de software, validado con medidas independientes y con el perfil original conservado. Esto no se presentará como recalibración interna del hardware Face ID.

El balance de blancos pertenece al color: auto al preparar, opción de referencia neutra y bloqueo durante un pase con iluminación estable. No corrige por sí mismo profundidad ni escala. El uso de una carta gris se apoya en la API de ganancias para una referencia neutra. [Apple](https://developer.apple.com/documentation/avfoundation/avcapturedevice/grayworlddevicewhitebalancegains)

## 6. Textura: frontal y trasera

La captura normal combina TrueDepth con RGB frontal. Ambas observan el objeto del mismo lado del teléfono. La cámara trasera mira hacia el lado opuesto; habilitarla a la vez no proporciona automáticamente color de la superficie que está midiendo TrueDepth. Esta limitación geométrica existe aunque MultiCam admita la combinación.

Se separan dos controles:

1. Usar información visual para tracking: activado en el modo híbrido, incluso si no se exporta color.
2. Guardar color/textura para el modelo final: opcional; sin textura se siguen guardando los keyframes necesarios para seguimiento/relocalización.

Primero se soportará color por punto/vértice. La textura fotográfica con atlas UV llegará después. Un pase independiente de fotos con la cámara trasera para mejorar la textura será avanzado: requiere estimar poses, calibración, correspondencias, visibilidad y consistencia de iluminación. No se ofrecerá como una simple casilla de captura simultánea garantizada.

## 7. Flujo de escritorio y semántica de las herramientas

### Preparar un grupo y un proyecto

Project Group representa el objeto o vehículo completo. Cada Project es una captura independiente, posiblemente con varias pausas y reanudaciones. El primero establece el marco del grupo; los siguientes tienen su propio marco hasta ser alineados. Una revisión de nube/malla es un resultado derivado, no un proyecto nuevo.

Crear/abrir grupo → nuevo proyecto → perfil de objeto y resolución de reconstrucción → modo de tracking y textura → preview. La resolución mostrada no se anunciará como precisión del sensor.

### Escanear, inspeccionar y completar

La interfaz tendrá visor central grande, panel izquierdo con cámara y ajustes, barra de distancia vertical, herramientas laterales, árbol de proyectos y estado de procesamiento. El diseño se inspira en la disposición de las capturas con nombres e iconos propios.

Distancia al objeto seleccionado, no al fondo: azul demasiado lejos, verde dentro del intervalo probado, rojo demasiado cerca; gris cuando no hay lectura confiable. Los límites se obtienen de las pruebas TrueDepth. Esta convención visual coincide con la documentación del fabricante. [Referencia SHINING 3D](https://docs.shining3d.com/einstarvega/1.2.0/en-us/preview/)

Calidad de los datos: verde = suficientes observaciones consistentes bajo el perfil actual; amarillo = cobertura útil pero insuficiente; rojo = observaciones escasas o inconsistentes. Se considerarán diversidad de vistas, ángulo, estabilidad de profundidad y confianza de pose. Repetir el mismo frame no debe convertir artificialmente la zona en verde. Una superficie nunca observada aparece como hueco/desconocida, no como geometría roja inventada. Verde no certifica tolerancia dimensional.

Pausar permite rotar e inspeccionar la nube. Al solicitar continuar, se muestra el frame actual frente a la nube conservada y se busca una zona reconocible. Mientras no exista alineación validada no se incorporan datos. Lost Tracking y Not enough features to align tienen texto, icono y sonido, además de color.

### Limpiar y generar nube

Herramientas: lazo, rectángulo, pincel, plano de corte, selección visible/a través, componente conectado, invertir, borrar, deshacer/rehacer, aplicar/cancelar. En nubes, conectividad se estima por vecindad espacial con umbral ligado a densidad; en mallas, por adyacencia topológica. Selección sobre preview se resuelve contra los datos completos, no solamente contra los puntos simplificados mostrados.

El flujo seleccionar objeto → Connected Domain → Invert → Delete será soportado. Si el objeto toca la mesa o existe un puente de ruido, ambos pueden pertenecer al mismo componente: se podrá cortar primero el contacto o separar manualmente. Se previsualizará toda selección antes de borrar. El comportamiento de selección está documentado como referencia por [SHINING 3D](https://docs.shining3d.com/einstarvega/1.0.1/en-us/data-edit-pc/).

Generate Point Cloud crea la nube consolidada usando las poses aceptadas y las exclusiones de edición. Optimize and Generate Point Cloud refina poses/conexiones válidas y vuelve a fusionar; tarda más. Esta segunda acción no sustituye quitar piso/mesa ni recuperar superficies nunca observadas. La distinción entre generación y optimización también aparece en [EXStar Hub](https://docs.shining3d.com/exstar-hub/1.1.1/einstar-rockit/en-us/pc-scanning/).

Las ediciones conservan máscaras/procedencia para no hacer reaparecer puntos borrados al regenerar. Si una optimización cambia poses y vuelve ambiguo aplicar una selección antigua, se exige revisar la edición afectada. Nuevas mediciones de la misma zona pueden incorporarse al reanudar: borrar puntos existentes no crea una prohibición espacial permanente.

### Otra cara del objeto y alineación

Para dar vuelta el objeto: pausar/finalizar el proyecto, limpiar el entorno, girar físicamente la pieza y crear un nuevo Project dentro del mismo Group. El usuario no debe reanudar con la pose previa como si el objeto no se hubiera movido.

Align muestra tres paneles: Fixed Window, Floated Window y Alignment Result. Se eligen proyectos, se ejecuta Auto Align o se marcan al menos tres pares no colineales distribuidos sobre el objeto; luego se refina. Apply guarda la transformación tras mostrar superposición y métricas de error. El proyecto fijo conserva su pose durante la operación; optimización global es una acción posterior diferenciada. No se ajusta escala para ocultar errores de calibración.

### Malla, edición y exportación

Mesh Model ofrece tres modos propios claramente definidos:

- Abierta: conserva superficies no observadas como huecos; opción predeterminada para diseño automotriz.
- Semicerrada: rellena únicamente huecos por debajo del límite seleccionado y revisado por el usuario.
- Cerrada/watertight: intenta producir una superficie cerrada e informa si la validación falla. El resultado se marca como completado artificialmente donde corresponda.

Los nombres siguen el flujo de referencia, pero la semántica anterior es nuestra especificación, no una afirmación de equivalencia con el algoritmo propietario. [Tipos de malla EXStar](https://docs.shining3d.com/exstar-hub/1.1.1/einstar2/en-us/pc-mesh/)

Recommended Parameters propone valores según perfil medido, densidad, extensión y presupuesto de memoria. Se muestran los valores antes de aplicar. Cambiar parámetros genera otra revisión desde la nube conservada y permite comparar o volver atrás.

Mesh Editing incluye simplificación, suavizado conservador, eliminación de componentes flotantes, limpieza de artefactos, normales y relleno de huecos seleccionados. Los orificios funcionales no se rellenan por defecto. La primera versión del relleno manual será plana; continuidad tangente/curvatura se añadirá tras validarla con casos adecuados. La precisión se vuelve a medir después de suavizar y simplificar.

Exportación: PLY para puntos/atributos; OBJ con MTL e imágenes cuando exista textura UV; STL para geometría; GLB texturizado en fase avanzada. Unidades explícitas y manifiesto lateral para formatos que no las registren de forma fiable. Se exportan geometría original o revisión elegida; el proyecto nativo guarda datos y procedencia completos.

## 8. Incertidumbres que requieren hardware

- Instalación y renovación de la app desde Windows en el iOS del usuario.
- Acceso efectivo a calibración, formatos y sincronización de captura.
- Transporte USB con nuestro servicio, drivers disponibles y cable concreto.
- Frecuencia/latencia sostenibles sin sobrecalentar el teléfono ni agotar la RAM de la PC.
- Fiabilidad de los botones durante todas las transiciones de captura.
- Precisión local y deriva sobre paneles automotrices reales.
- Relocalización sin marcadores: viable como objetivo en regiones observables; no garantizada en cualquier superficie.

No se ha implementado ni medido ninguna de estas capacidades todavía. El plan de validación está en [ROADMAP.md](../ROADMAP.md).
