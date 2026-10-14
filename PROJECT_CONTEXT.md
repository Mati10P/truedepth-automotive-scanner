# TrueDepth Automotive 3D Scanner
**Especificación técnica y plan de investigación — Versión 3.0**

Actualización: 2026-10-13, incorporando el flujo de escritorio y las 18 referencias visuales aportadas por el usuario.

El plan vigente está en [ROADMAP.md](ROADMAP.md). Las conclusiones documentadas sobre USB/Wi-Fi, procesamiento, botones, cámaras y calibración, junto con el flujo detallado, están en [viabilidad y flujo](docs/FEASIBILITY_AND_WORKFLOW.md). Las capturas se conservan en [referencias visuales](docs/references/README.md).

## 0. Experiencia de uso acordada

El iPhone funciona como escáner de mano: captura TrueDepth y RGB frontal, con volumen arriba para iniciar/reanudar y volumen abajo para pausar. La PC muestra la nube en vivo y es el centro de configuración, inspección, limpieza, alineación, generación de mallas y exportación. Blender será un destino y una integración adicional.

Se prioriza USB para el uso conectado si pasa la prueba física; Wi-Fi es una alternativa completa. El cable no expone automáticamente TrueDepth a Windows: hace falta nuestra app y una capa de comunicación. La distribución inicial usa el iPhone para captura/envío/respaldo y la PC para tracking y reconstrucción, con optimización posterior según mediciones de rendimiento.

Flujo principal: conectar/verificar → ajustar color si corresponde → crear Project Group y Project → preview → escanear → pausar/inspeccionar/relocalizar/completar → limpiar → generar nube u optimizar y generar → nuevo Project para otra cara → alinear → generar malla → editar → exportar.

El desarrollo parte de Windows, con primera ruta de compilación/instalación sin gastos. Los marcadores son opcionales; el MVP debe relocalizar sin ellos en regiones con referencias suficientes. La primera aplicación práctica es carrocería con ajuste manual y medidas independientes en montajes.

## 1. Visión del proyecto

Desarrollar un sistema de escaneo 3D automotriz que utilice la cámara frontal TrueDepth del iPhone 16e como sensor de profundidad y ofrezca funcionalidades comparables a las del software de los escáneres profesionales EINSTAR y EinScan.

El objetivo principal es escanear progresivamente un vehículo completo, específicamente un Volkswagen Gol G2 de 1998, para obtener geometría dimensionalmente fiel que pueda utilizarse en Blender para diseñar paragolpes, alerones, body kits y otras piezas.

El sistema debe priorizar cuatro capacidades:

1. Captura de geometría precisa con TrueDepth.
2. Tracking robusto y recuperación ante pérdidas de seguimiento.
3. Alineación automática de múltiples escaneos independientes.
4. Reconstrucción y exportación de modelos utilizables para diseño automotriz.

Se busca implementar la mayor parte posible mediante software gratuito y de código abierto, sin depender de hardware profesional costoso.

## 2. Problema principal: el tracking

La principal limitación observada en aplicaciones como EM3D es su dificultad para mantener y recuperar la posición espacial del sensor.

### 2.1. Cómo funciona el tracking

Los escáneres necesitan calcular cómo se desplaza el sensor respecto al objeto.

Cada nuevo frame de profundidad debe posicionarse correctamente respecto a los anteriores.

Según el cuarto video, existen tres métodos especialmente relevantes:

**Geometry tracking**

Identifica características geométricas distintivas del objeto: bordes, agujeros, curvaturas y cambios de profundidad.

Problema: una puerta o un capó pueden tener muy pocas características para estimar el movimiento.

**Texture tracking**

Utiliza características visuales de las imágenes RGB, como patrones, contrastes o detalles de la superficie.

Puede resultar útil cuando la geometría carece de detalles, pero existen referencias visuales.

**Marker tracking**

Utiliza marcadores reconocibles para conocer la posición y orientación del sensor.

Es particularmente interesante para superficies grandes, lisas o repetitivas.

### 2.2. Propuesta: tracking híbrido

Investigar un sistema que combine:

- Geometría obtenida mediante TrueDepth.
- Características visuales de la cámara RGB frontal.
- Marcadores físicos reconocibles.
- Información de movimiento de los sensores inerciales.
- SLAM, odometría RGB-D y optimización de poses.
- Seguimiento de posición mediante ARKit, si sus configuraciones compatibles permiten utilizarlo en este escenario.

El software debería adaptar el método de tracking según las características de la superficie.

No debe asumir que el tracking de ARKit funcionará automáticamente con cualquier objeto observado por TrueDepth.

### 2.3. Solución al problema Lost Tracking

**Función crítica del proyecto.**

Cuando el software pierde el tracking:

1. Detecta que la estimación de posición ya no es confiable.
2. Detiene temporalmente la incorporación de geometría.
3. Conserva todo el escaneo válido anterior.
4. Muestra un aviso: "Tracking Lost — Move back to previously scanned area".
5. Intenta reconocer una región previamente escaneada.
6. Calcula su posición relativa al modelo existente.
7. Verifica la confianza de la nueva alineación.
8. Reanuda la captura sin comenzar un proyecto nuevo.

También debe incorporar el aviso "Not enough features to align" cuando no existan referencias suficientes.

### 2.4. Protección contra alineaciones incorrectas

Un problema particularmente grave, mencionado en los videos, ocurre cuando el escáner cree estar en una posición equivocada y comienza a superponer datos en el lugar incorrecto.

Por ejemplo, pueden aparecer dos copias de una misma pinza de freno.

Funciones propuestas:

- Detectar alineaciones geométricamente inconsistentes.
- Rechazar automáticamente frames con tracking poco confiable.
- Pausar antes de que se incorpore geometría incorrecta.
- Permitir deshacer los últimos 10, 30 o 60 segundos de captura.
- Guardar puntos de recuperación periódicos.
- Permitir revertir una sesión hasta el último estado válido.

Se deben conservar los datos brutos y el historial de poses para poder corregir errores sin perder necesariamente toda la captura.

## 3. Escaneo progresivo de un vehículo completo

El sistema no debe depender de escanear todo el vehículo en una sola sesión.

La propuesta es trabajar mediante proyectos compuestos por múltiples escaneos.

Ejemplo:

- Scan 01: paragolpes y parrilla delantera.
- Scan 02: capó y guardabarros izquierdo.
- Scan 03: puerta y lateral izquierdo.
- Scan 04: techo.
- Scan 05: lateral derecho.
- Scan 06: portón y paragolpes trasero.

Cada fragmento deberá compartir suficiente geometría o referencias espaciales con otros fragmentos.

### 3.1. Alineación automática

Inspirándose en EXStar, implementar:

1. Selección de dos o más escaneos.
2. Detección automática de superficies coincidentes.
3. Estimación inicial de posición y orientación.
4. Ajuste fino mediante registro geométrico.
5. Validación de la calidad de alineación.
6. Optimización global de los fragmentos.
7. Fusión de las regiones correctamente alineadas.

Algoritmos y herramientas para investigar:

- ICP (Iterative Closest Point).
- Point-to-plane ICP.
- Global registration mediante descriptores geométricos.
- Pose graph optimization.
- Loop closure.
- Bundle adjustment, cuando existan observaciones visuales y calibraciones apropiadas.

### 3.2. Alineación manual asistida

La interfaz tendrá Fixed Window, Floated Window y Alignment Result. Auto Align propone una transformación; la selección manual ayuda a estimarla y después se refina. Apply guarda el resultado revisado. La captura fija no cambia de pose durante la alineación de ese par.

Si el software no puede alinear automáticamente dos escaneos, debe permitir identificar manualmente tres o más puntos correspondientes.

Estos puntos proporcionarían una estimación inicial, seguida de alineación automática más precisa.

La función es especialmente importante para superficies con geometría repetitiva o poca superposición.

### 3.3. Minimización de errores acumulados

Unir escaneos sucesivamente puede producir una desviación creciente de las dimensiones originales.

El sistema debería:

- Conservar la escala métrica original.
- Registrar la incertidumbre de las alineaciones.
- Evitar depender exclusivamente del escaneo anterior.
- Detectar conexiones con regiones capturadas anteriormente.
- Utilizar referencias dimensionales conocidas.
- Ejecutar optimización global para distribuir y reducir errores.
- Permitir comprobar las dimensiones totales del vehículo.

Las medidas físicas no deben sustituirse por estimaciones no verificadas.

## 4. Marcadores para superficies automotrices

Los videos muestran que los paneles lisos y las geometrías repetitivas son algunos de los mayores obstáculos para el tracking.

Investigar el uso de marcadores físicos.

### 4.1. Tipos de marcadores

**Marcadores visuales impresos**

- AprilTag.
- ArUco.
- Patrones identificables de alto contraste.

**Marcadores utilizados por escáneres profesionales**

- Puntos reflectantes.
- Dianas infrarrojas.

Debe investigarse cuáles pueden ser detectados mediante las imágenes RGB o los datos TrueDepth disponibles públicamente.

No se puede asumir que los marcadores reflectantes infrarrojos diseñados para EINSTAR funcionarán de la misma manera con el iPhone.

### 4.2. Características deseadas

- Identificación individual de los marcadores.
- Estimación de la posición y orientación de la cámara.
- Reconocimiento desde diferentes ángulos.
- Capacidad de recuperación del tracking.
- Referencias compartidas entre sesiones.
- Posibilidad de definir dimensiones o distancias conocidas entre referencias.

También se debe investigar cómo distribuirlos sobre el vehículo para mantener suficientes referencias visibles sin cubrirlo innecesariamente de stickers.

Los marcadores deben permanecer fijos respecto al vehículo durante las capturas que dependen de ellos.

## 5. Calidad del escaneo en tiempo real

Inspirarse en los indicadores visuales de EINSTAR.

### 5.1. Indicador de distancia

Mostrar una barra que indique:

- Too close: rojo.
- Optimal distance: verde.
- Too far: azul.
- Sin lectura confiable: gris.

Los límites deben definirse mediante pruebas de TrueDepth, no copiando los valores de un escáner profesional.

### 5.2. Indicador de calidad

Utilizar colores para representar la calidad o cobertura estimada.

Propuesta inicial:

- Verde: región suficientemente observada.
- Amarillo: región que necesita más capturas.
- Rojo: región con datos insuficientes o inconsistentes.

El software debe distinguir entre:

1. Cobertura: cuánto de la superficie fue capturado.
2. Calidad de profundidad: cuán utilizables son las mediciones.
3. Confianza del tracking: cuán confiable es la posición del sensor.
4. Precisión geométrica: cuánto se aproxima la reconstrucción a la geometría real.

Estas métricas no son equivalentes.

Una región verde no debe considerarse automáticamente dimensionalmente exacta.

La visualización durante captura será una nube o surfels y, opcionalmente, una superficie provisional. Una zona nunca observada permanecerá desconocida o como hueco; no se inventará una superficie roja. La calidad combinará observaciones independientes, ángulos, consistencia de profundidad y confianza de pose: repetir frames idénticos no basta para volver una zona verde.

### 5.3. Detección de regiones problemáticas

El usuario debe poder identificar:

- Agujeros.
- Zonas incompletas.
- Superficies con ruido.
- Regiones mal alineadas.
- Datos flotantes.
- Superficies deformadas.
- Capturas con ángulos desfavorables.

Después de inspeccionar el modelo, debería ser posible regresar a una región determinada y agregar nuevas mediciones.

## 6. Pausa, reanudación y corrección

EXStar muestra que el usuario puede pausar una captura, inspeccionar el modelo y continuar.

El proyecto debería permitir:

- Pausar sin finalizar la sesión.
- Rotar y examinar el modelo.
- Identificar regiones problemáticas.
- Reanudar mediante relocalización automática.
- Corregir capturas anteriores.
- Eliminar datos incorrectos.
- Deshacer segmentos recientes.
- Guardar proyectos incompletos.
- Continuar otro día.

Es importante diferenciar dos operaciones:

**Resume:** continuar una captura dentro de la misma sesión, después de recuperar la posición.

**New scan:** comenzar una captura independiente que se alineará posteriormente con el proyecto.

Ambas son necesarias.

Al pausar, el usuario puede girar el visor sin alterar la pose física del escáner. Reanudar desde el botón del iPhone activa primero la relocalización; no incorpora geometría hasta validar la alineación. La app mantiene activa la sesión de cámara durante la pausa cuando iOS lo permita. Bloquear el teléfono o enviar la app al fondo interrumpe la captura y conserva el avance.

## 7. Captura de datos TrueDepth

### 7.1. Información necesaria

La aplicación iOS debe intentar obtener:

- Mapas de profundidad.
- Frames RGB sincronizados.
- Timestamp de cada captura.
- Parámetros intrínsecos de cámara.
- Información de calibración disponible.
- Orientación del teléfono.
- Datos inerciales.
- Calidad y validez de los mapas de profundidad.
- Transformaciones espaciales estimadas y su confianza.

Los datos deben poder guardarse sin quedar limitados a una malla final.

### 7.2. Calibración

Antes de implementar una calibración propia, investigar la calibración que proporciona Apple.

La ruta inicial utiliza AVDepthData.cameraCalibrationData y una verificación dimensional propia. No se exige la rutina de tablero de EINSTAR antes de cada escaneo. Una corrección adicional de software deberá justificarse con sesgos medidos y pruebas independientes; no se presentará como recalibración interna del sensor Face ID. El balance de blancos es un ajuste opcional del color, separado de la calibración geométrica.

Evaluar:

- Distorsión óptica.
- Error de escala.
- Error de profundidad en función de la distancia.
- Ruido temporal.
- Estabilidad entre capturas.
- Posibles diferencias entre mapas filtrados y sin filtrar.

Cualquier calibración adicional debe evaluarse mediante mediciones de referencia.

### 7.3. Pruebas de alcance y precisión

Realizar experimentos con superficies y objetos de dimensiones conocidas.

Variar:

- Distancia.
- Ángulo.
- Iluminación.
- Color.
- Textura.
- Reflectividad.
- Velocidad de movimiento.

Registrar tanto resolución espacial como error dimensional.

## 8. Procesamiento y reconstrucción

### 8.1. Generación de nubes de puntos

Convertir cada mapa de profundidad en coordenadas tridimensionales utilizando la calibración de cámara.

Conservar, cuando corresponda:

- Posición XYZ.
- Color.
- Frame de origen.
- Timestamp.
- Pose estimada.
- Indicadores de validez.

### 8.2. Limpieza de datos

Investigar herramientas para:

- Eliminar puntos aislados.
- Filtrar datos inconsistentes.
- Separar el automóvil del fondo.
- Eliminar piso, paredes y otros elementos no deseados.
- Recortar regiones mediante lazo, polígono o plano.
- Detectar y eliminar componentes desconectados.
- Corregir errores de captura.

**Precaución:** una función automática que elimina componentes desconectados podría borrar detalles legítimos, como espirales, cables o piezas separadas.

Debe existir una vista previa antes de aplicar operaciones destructivas.

Herramientas requeridas: lazo, rectángulo, pincel, plano de corte, selección visible/a través, Connected Domain, Invert, borrar, aplicar/cancelar y deshacer/rehacer. En nube, conectividad se estima espacialmente; el contacto con mesa/piso puede conectar ambos y requerir un corte previo. Las exclusiones deben sobrevivir a regeneraciones mediante procedencia de datos y revisiones de edición.

Generate Point Cloud consolida las mediciones aceptadas. Optimize and Generate Point Cloud añade refinamiento de poses y nueva fusión; no sustituye eliminar el entorno ni captura superficies ausentes.

### 8.3. Reconstrucción de superficies

Investigar la integración de múltiples frames RGB-D y la generación de mallas mediante técnicas como TSDF.

Considerar:

- Fusión de mediciones repetidas.
- Reducción de ruido.
- Preservación de bordes.
- Conservación de curvaturas.
- Control de la resolución.
- Detección de agujeros.

### 8.4. Mallas abiertas y cerradas

**Requisito:** permitir exportar mallas abiertas.

Para ingeniería inversa, una superficie incompleta pero medida correctamente puede ser más útil que una superficie cerrada mediante geometría inventada.

El software debe permitir elegir:

- Open mesh.
- Cierre parcial de agujeros seleccionados.
- Watertight mesh, solamente cuando sea necesario.

En Mesh Model se presentan como abierta, semicerrada y cerrada, con Recommended Parameters visibles y revisables. La semicerrada solo completa huecos bajo criterios seleccionados; la cerrada debe validar su cierre e informar fallos. Se puede volver atrás y generar otra revisión sin perder la nube.

Mesh Editing incluye simplificar, optimizar, suavizar, quitar componentes flotantes y rellenar huecos seleccionados con clic. Los orificios funcionales se conservan por defecto. Relleno plano primero; continuidad tangente o curvatura en fases avanzadas.

Nunca debe presentar geometría reconstruida artificialmente como si hubiera sido medida.

### 8.5. Simplificación de mallas

Incorporar simplificación controlada para reducir el peso de los modelos.

Funciones deseadas:

- Seleccionar cantidad aproximada de polígonos.
- Previsualizar pérdida de detalles.
- Preservar bordes y características importantes.
- Mantener una copia del modelo original.
- Exportar versiones de diferentes resoluciones.

Esto es especialmente relevante por las limitaciones de memoria y GPU de la computadora disponible.

## 9. Interfaz de escritorio y conexión con Blender

La aplicación iOS será responsable de obtener datos del sensor.

Un proceso de escritorio recibirá o importará las capturas para reconstrucción y visualización.

La estación de escritorio es el producto principal: visor central, cámara y configuración a la izquierda, barra vertical de distancia, acciones laterales, selección/edición inferior y árbol de Project Group/Projects. La disposición y el recorrido se inspiran en EXStar; no es necesario abrir Blender para escanear ni editar.

Project Group representa el objeto completo. Cada Project corresponde a una captura independiente, que admite pausas y reanudaciones. Dar vuelta físicamente el objeto requiere una nueva captura que luego se alinea. Nubes y mallas son revisiones derivadas conservando los originales.

### 9.1. Visualización en tiempo real

Mostrar progresivamente:

- Nube de puntos.
- Geometría acumulada.
- Posición estimada de la cámara.
- Trayectoria de escaneo.
- Regiones ya capturadas.
- Calidad de captura.
- Avisos de tracking.

### 9.2. Control remoto

Debido a que TrueDepth se encuentra en la parte frontal del iPhone, la pantalla generalmente apuntará hacia el vehículo durante el escaneo.

Se requiere una forma de controlar o supervisar la aplicación sin ver directamente esa pantalla.

Posibilidades:

- Conexión USB mediante puente de comunicación, tras validación, y alternativa Wi-Fi local.
- Interfaz de escritorio con control y visualización en vivo.
- Indicaciones sonoras.
- Alertas hápticas.
- Volumen arriba para iniciar/reanudar y volumen abajo para pausar, mediante eventos de captura de iOS.

Textura opcional mediante RGB frontal sincronizado con TrueDepth. Usar RGB para tracking es independiente de guardar textura para exportar. La cámara trasera apunta al lado contrario; su posible uso para texturas de más detalle se reserva a otra pasada con registro de fotografías, no se presupone color simultáneo de la misma superficie.

### 9.3. Integración con Blender

Objetivo adicional: un complemento que permita recibir y visualizar las capturas directamente en Blender, conservando la estación de escritorio independiente.

Funciones deseadas:

- Conectar con el iPhone.
- Visualizar el escaneo.
- Administrar sesiones.
- Inspeccionar alineaciones.
- Ocultar o mostrar fragmentos.
- Importar la malla final.
- Conservar la escala.

No es necesario ejecutar todos los algoritmos dentro de Blender.

El procesamiento de nubes de puntos podría realizarse mediante un motor externo.

## 10. Exportación y utilización en CAD

Formatos principales:

- PLY: conservar nubes de puntos y atributos.
- OBJ: importar mallas en Blender.
- STL: geometría de superficie para otros flujos de fabricación.

Debe conservarse la escala física y registrarse la unidad utilizada.

### Dos niveles de precisión

**Modelo global del automóvil**

Captura la silueta, los volúmenes principales y la disposición de las piezas.

Útil para diseño visual, análisis de interferencias y desarrollo conceptual de carrocería.

**Escaneos locales de precisión**

Se enfocan en regiones como soportes, agujeros, bordes de paragolpes y puntos de montaje.

Se complementan con mediciones manuales mediante calibre u otros instrumentos.

El modelo global puede ser una referencia, mientras que los detalles funcionales se reconstruyen con CAD y mediciones verificadas.

## 11. Preparación de las superficies

Los videos destacan que los escáneres ópticos suelen tener dificultades con:

- Pintura negra.
- Superficies brillantes.
- Materiales reflectantes.
- Transparencias.
- Iluminación solar intensa.
- Geometría repetitiva.

Investigar técnicas para mejorar la captura:

- Iluminación difusa.
- Escaneo en espacios cerrados.
- Marcadores visuales temporales.
- Productos específicos de matizado para escaneo.

Cualquier producto aplicado a la pintura automotriz debe comprobarse previamente para evitar daños en el acabado, plásticos o adhesivos.

## 12. Rendimiento y recursos

Hardware disponible:

**Teléfono:** iPhone 16e con TrueDepth.

**Computadora:** Ryzen 5 7520U, 8 GB RAM y gráficos Radeon integrados.

El software debería diseñarse teniendo en cuenta recursos limitados.

Estrategias:

- Procesamiento incremental.
- Guardado de escaneos por fragmentos.
- Previsualizaciones simplificadas.
- Procesamiento diferido de mallas.
- Almacenamiento de datos brutos.
- Reducción temporal de resolución para previsualización.
- Evitar mantener toda la nube de puntos en memoria RAM.

El sistema debería permitir trabajar progresivamente incluso si el procesamiento final de un modelo completo resulta demasiado costoso para hacerse en tiempo real.

## 13. Herramientas a investigar

**Apple AVFoundation**

Captura de mapas de profundidad y RGB sincronizados, calibración y parámetros del sensor.

**ARKit y Core Motion**

Seguimiento espacial compatible y mediciones inerciales.

**OpenCV**

Seguimiento de características visuales, detección de marcadores y estimación de poses.

**Open3D**

Registro geométrico, ICP, alineación global, integración RGB-D y optimización de nubes de puntos.

**MeshLab**

Limpieza, procesamiento, reparación y simplificación de mallas.

**Blender**

Visualización, edición, diseño de superficies y preparación de piezas.

**REA — Reverse Engineer Anything**

Investigar el funcionamiento de aplicaciones TrueDepth existentes, como EM3D, cuando sea necesario comprender comportamientos no documentados.

Repositorio: https://github.com/morluto/rea

**Software comercial de referencia**

- SHINING 3D EXStar.
- EinScan.
- RecFusion.

## 14. Pruebas y criterios de éxito

No evaluar el proyecto únicamente por la apariencia visual.

Medir:

**Precisión dimensional**

Comparar dimensiones obtenidas del modelo contra medidas físicas conocidas.

**Repetibilidad**

Escanear el mismo objeto varias veces y analizar diferencias.

**Error de alineación**

Comparar fragmentos superpuestos y registrar las desviaciones.

**Robustez del tracking**

Registrar cuántas veces se pierde el seguimiento y en qué condiciones.

**Recuperación del tracking**

Medir qué porcentaje de pérdidas permite recuperarse sin reiniciar.

**Deriva acumulada**

Comprobar si el modelo se deforma a medida que se incrementa el recorrido del escáner.

**Cobertura**

Evaluar qué proporción de la superficie objetivo se capturó correctamente.

**Rendimiento**

Medir memoria RAM, tamaño de archivos, velocidad de captura y tiempo de procesamiento.

## 15. Desarrollo por etapas

El detalle y los criterios de aceptación están en [ROADMAP.md](ROADMAP.md).

0. Circuito de instalación iOS desde Windows, botones y evaluación USB/Wi-Fi.
1. Grabador RGB-D, calibración disponible y verificación métrica del sensor.
2. Tracking y relocalización reproducibles sobre capturas grabadas.
3. MVP: escaneo de mano, preview/calidad/distancia en PC, pausa, inspección y reanudación recuperable.
4. V1: limpieza de nube, generación/optimización y grupos con alineación entre proyectos.
5. V1.5: generación de malla, parámetros, edición, relleno selectivo y exportación.
6. V2: robustez automotriz, marcadores opcionales, deriva, rendimiento, texturas e integración Blender.
7. Gol completo y primera pieza física con ajuste comprobado.
8. Extensiones avanzadas: fusión visual-inercial, captura autónoma, fotografía trasera separada y reconstrucción avanzada.

La recuperación de tracking se valida antes de declarar terminado el MVP. La experiencia de escritorio existe desde el MVP y luego incorpora las herramientas avanzadas.

## 16. Preguntas técnicas todavía abiertas

1. ¿Cuál es la precisión real de TrueDepth a diferentes distancias y sobre distintas superficies?
2. ¿Qué resolución y frecuencia de mapas de profundidad permite obtener el iPhone 16e?
3. ¿Se puede aprovechar ARKit para tracking espacial mientras se capturan mapas de profundidad frontales?
4. ¿Hasta qué punto puede utilizarse RGB-D odometry sin depender de ARKit?
5. ¿Qué tipo de marcadores ofrece mejores resultados con las cámaras accesibles del iPhone?
6. ¿Cuánta superposición necesitan los fragmentos para alinearse confiablemente?
7. ¿Se puede lograr una recuperación de tracking suficientemente robusta para paneles grandes?
8. ¿Cuánto error acumulado se produce al reconstruir un vehículo completo?
9. ¿Qué procesos pueden ejecutarse directamente en el iPhone y cuáles necesitan la computadora?
10. ¿Qué nivel de precisión permitiría diseñar piezas automotrices que encajen correctamente?

## 17. Referencias audiovisuales

**Video 1 — Escaneo de un Dodge Viper con EINSTAR**

https://youtu.be/rORuE8Oyxd0

Aportes: escaneo por partes, marcadores, alineación automática, alineación manual de tres puntos, problemas de geometría repetitiva, función de deshacer capturas, MeshLab y uso de escaneos para CAD automotriz.

**Video 2 — Comparativa Intel L515, Revopoint POP y LiDAR del iPhone**

https://youtu.be/qEDek-ztaAw

Aportes: movimiento lento, superposición entre capturas, alcance limitado, escaneo de autos completos, preparación de superficies, selección de resolución y errores acumulados al combinar fragmentos.

**Video 3 — Comparativa entre escáneres económicos y EinScan HX**

https://youtu.be/MTE7XbOJvgk

Aportes: tracking y relocalización, comparación entre TrueDepth frontal y LiDAR trasero del iPhone, monitor externo para TrueDepth, alineación entre sesiones y necesidad de mediciones físicas complementarias.

**Video 4 — The Truth About 3D Scanning, Making for Motorsport**

https://youtu.be/Ac4Rs-tFZOU

Aportes: geometry tracking, texture tracking, marker tracking, precisión frente a resolución, limitaciones ópticas, costos computacionales e ingeniería inversa de CAD.

**Video 5 — Revisión y demostración del EINSTAR**

https://youtu.be/X7-D7VVmB20

Aportes: calibración, balance de blancos, distancia óptima, indicadores de calidad, pausa, recuperación de tracking, eliminación de ruido, fusión de proyectos, creación de mallas y herramientas de posprocesamiento.

## 18. Definición de éxito

El objetivo final es disponer de un escáner 3D de bajo costo que aproveche TrueDepth y permita trabajar de forma progresiva, recuperable y verificable.

El software debería permitir:

- Capturar geometría real.
- Mantener el tracking siempre que existan referencias suficientes.
- Recuperarse cuando se pierde.
- Deshacer capturas incorrectas.
- Escanear un objeto en múltiples sesiones.
- Alinear los fragmentos automáticamente.
- Evaluar la cobertura y calidad.
- Procesar la geometría sin inventar detalles innecesarios.
- Exportar un modelo con escala real a Blender.

El criterio definitivo será la **utilidad del resultado para diseñar y fabricar piezas**, no solamente la calidad visual del modelo.


## 19. Requisitos adicionales acordados — 2026-10-14

Esta ampliación conserva íntegramente el contexto y el alcance anteriores.

- **UI/UX:** debe ser exactamente igual a EXStar donde sea viable, o lo más parecida posible, priorizando su sencillez y facilidad de uso. El acceso a la interfaz permite documentar y comparar pantallas, navegación, controles y flujos desde el MVP hasta las fases avanzadas, con implementación propia y adaptaciones justificadas para TrueDepth.
- **Open source:** todo el proyecto y su desarrollo deben quedar documentados en un repositorio público de GitHub, con código propio, licencia open source, decisiones técnicas, instrucciones reproducibles, resultados de pruebas y conclusiones de investigación. Binarios de EXStar y datos privados quedan fuera de la publicación.
- **Plan revisable:** el plan está abierto a modificaciones según los resultados del análisis de REA con EXStar. Cada cambio debe conservar su evidencia, justificación e historial en GitHub.

Los entregables y criterios transversales de esta ampliación están detallados al final de [ROADMAP.md](ROADMAP.md).


## Decisión de publicación inicial

Por decisión posterior del usuario, el desarrollo comienza en el repositorio privado https://github.com/Mati10P/truedepth-automotive-scanner y se hará público cuando el proyecto esté listo. Esta decisión actualiza el momento de publicación indicado arriba: se mantienen el objetivo open source, la documentación continua y la elección de una licencia compatible antes de hacerlo público.
