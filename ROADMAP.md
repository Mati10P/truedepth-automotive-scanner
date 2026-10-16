# Plan de desarrollo — TrueDepth Automotive 3D Scanner

Versión 3.0, 2026-10-13. Sustituye el orden de fases anterior y concreta la experiencia iPhone como escáner de mano + estación Windows descrita por el usuario.

Referencias: [contexto](PROJECT_CONTEXT.md), [viabilidad y flujo detallado](docs/FEASIBILITY_AND_WORKFLOW.md), [capturas de interfaz](docs/references/README.md).

## Decisiones de partida

- Uso personal con iPhone 16e y Windows, Ryzen 5 7520U, 8 GB RAM y Radeon integrada; primera ruta de desarrollo sin gastos.
- App Swift/AVFoundation/Core Motion; motor Windows Python/Open3D/OpenCV; interfaz local TypeScript/Three.js con servicio FastAPI. Distribución como estación de escritorio; no depende de Blender ni de servicios de reconstrucción remotos.
- El iPhone captura, envía, conserva temporalmente datos y recibe botones de volumen. La PC dirige proyecto, tracking, fusión, edición, alineación y exportación. Portar operaciones al iPhone solo tras medir cuellos de botella.
- USB preferido para uso conectado si supera pruebas; Wi-Fi funcional desde el prototipo. Ambos comparten protocolo y estado de proyecto.
- RGB frontal para color junto con TrueDepth. Textura de salida opcional y separada del uso de RGB para tracking.
- Calibración de captura de Apple más verificación propia; balance de blancos opcional para color. No exigir tablero de EINSTAR antes de cada sesión.
- Marcadores opcionales. El MVP debe recuperar tracking sin ellos sobre regiones con características suficientes.
- Blender es destino e integración posterior. El criterio inicial de utilidad es diseño de carrocería y ajuste manual, con medidas independientes en montajes.

## Fase 0 — Circuito iOS, controles y transporte

Avance 2026-10-16: [primer circuito implementado en código](docs/implementation/FIRST_FRAME.md), receptor probado localmente con datos sintéticos. App iOS pendiente de compilación/instalación y prueba física. REA/ICP en pausa hasta disponer de datos reales.

Entregables:

- Proyecto mínimo iOS y compilación reproducible en macOS remoto, inicialmente GitHub Actions privado dentro de cuota. IPA para firma/instalación personal desde Windows; validar renovación sin perder archivos.
- Reporte de versión del sistema, formatos TrueDepth, calibración disponible y capacidades de control.
- Botones: volumen arriba iniciar/reanudar; abajo pausar. Mantener sesión de cámara activa en pausa; manejar eventos ended/cancelled, segundo plano y bloqueo.
- Prototipo de transporte con bloques de datos numerados y checksum por Wi-Fi, luego USB con iproxy. Guardar el reporte comparativo, incluyendo desconexiones y drivers necesarios.
- Comprobar, en ensayo separado, si ARKit aporta pose utilizable junto con profundidad frontal sin depender de detectar una cara. AVFoundation sigue siendo la ruta base.

Aceptación: instalar y actualizar la app en el 16e, confirmar botones y transmitir una sesión de 10 minutos con integridad verificada. El modo USB solo se anuncia funcional cuando pasa la prueba física. Si falla, continuar por Wi-Fi y mantener un impedimento documentado, sin asumir gastos ni comprar servicios.

## Fase 1 — Grabador y verificación métrica

Entregables:

- Captura RGB-D sincronizada, timestamps, calibración y movimiento; persistencia por bloques recuperables, profundidad sin compresión con pérdida.
- Rectificación, proyección a 3D y pruebas de escala, orientación, espejo y alineación color/profundidad.
- Pantalla Preparación: conexión, verificación de sensor y color; auto exposición/balance y bloqueo cuando el dispositivo lo admita.
- Visor de frame y exportación PLY; comparación filtrado/no filtrado.
- Banco de objetos medidos a distintas distancias, ángulos y luces; superficies mates, oscuras, brillantes y planas.

Aceptación: perfil de captura reproducible, intervalo de distancia recomendado y reporte de error/repetibilidad. No adoptar como límites los milímetros que aparecen en EXStar. Prototipo de captura listo; aún no es el MVP.

## Fase 2 — Motor reproducible de tracking y relocalización

Entregables:

- Reproductor de grabaciones con el mismo contrato que la entrada en vivo.
- Odometría RGB-D y refinamiento geométrico contra mapa local; keyframes con descriptores y profundidad.
- Detección de mala pose por correspondencias, residuos, movimiento y degeneración geométrica.
- Relocalización visual con estimación robusta de pose y refinamiento ICP; búsqueda geométrica adicional para regiones sin textura pero con forma distintiva.
- Validación temporal antes de aceptar una recuperación; mapa previo inalterado durante pérdida.
- Nube/surfels para preview y fusión TSDF por fragmentos para resultados derivados.

Aceptación: replay con pérdidas inducidas conserva el mapa y recupera desde una zona anterior sin marcadores. Evaluar también regiones equivocadas y geometría repetitiva. Registrar decisiones por frame para reproducir fallos.

## Fase 3 — MVP: escaneo de mano con preview en PC

Entregables:

- Crear grupo/proyecto, preparar sensor, preview, iniciar/pausar desde volumen, inspeccionar girando la nube y reanudar por relocalización.
- Disposición inicial EXStar: visor central, panel de cámara/ajustes a la izquierda, barra vertical de distancia, herramientas a la derecha y estado inferior.
- Barra distancia azul/lejos, verde/adecuado, rojo/cerca, gris/sin lectura. Distancia medida sobre región objetivo válida.
- Mapa básico de calidad verde/amarillo/rojo, derivado de observaciones independientes, consistencia y pose; desconocido queda sin superficie inventada.
- Lost Tracking/Not enough features to align y guía para regresar; avisos sonoros/hápticos y comandos confirmados.
- Deshacer 30 segundos reconstruyendo desde originales; guardado y recuperación frente a caída de red o proceso.
- Generar nube consolidada, exportar PLY y malla abierta OBJ básica.

Aceptación: escanear una pieza con referencias geométricas/visuales, pausar, inspeccionar, pedir reanudación desde el teléfono, recuperar y completar una zona pobre. Funciona sin marcadores en ese escenario. El MVP no requiere escanear un panel liso completo sin referencias.

## Fase 4 — V1: nube editable y múltiples proyectos

Entregables:

- Lazo, rectángulo, pincel, corte por plano, selección visible/a través, connected domain, invertir y borrar; vista previa, aplicar/cancelar y deshacer persistente.
- Conectividad espacial para nubes; advertir visualmente si el componente incluye la mesa por contacto/ruido. Selecciones conservadas con procedencia y aplicadas a resolución completa.
- Generate Point Cloud y Optimize and Generate Point Cloud como operaciones distintas. Optimizar refina poses y vuelve a fusionar, sin sustituir edición del entorno.
- New Project dentro de Project Group para capturar otra cara del objeto tras girarlo.
- Align con Fixed/Floated/Result, Auto Align y correspondencias manuales no colineales; métricas, aplicar/cancelar y revisiones de transformación.
- Optimización global del grupo como operación explícita, preservando el anclaje elegido; reapertura y continuación en otra fecha.

Aceptación: limpiar una pieza sobre mesa, girarla, capturar otra cara, alinear sin usar el entorno como referencia y guardar el conjunto. Regenerar no resucita datos borrados. El proyecto fijo no se mueve durante la alineación de pares.

## Fase 5 — V1.5: generación y edición de malla

Entregables:

- Mesh Model desde nubes alineadas con modos abierto, semicerrado (huecos pequeños seleccionados por umbral) y cerrado, validando el resultado.
- Recommended Parameters según perfil/ruido/densidad y memoria; parámetros visibles y reproducibles.
- Revisiones independientes de malla, volver atrás, cambiar parámetros y regenerar desde nube conservada.
- Simplificación, suavizado conservador, limpieza de artefactos, componentes flotantes y normales con comparación antes/después.
- Identificación de contornos de huecos y relleno manual plano por selección. Relleno tangente/curvatura se reserva para fase 8.
- PLY, OBJ y STL con unidades explícitas y procedencia de regiones completadas. Color por vértice/punto donde el formato lo soporte; textura UV y sus archivos cuando se incorpore esa función.

Aceptación: completar todo el flujo de las capturas de referencia y producir una malla de ingeniería abierta o una variante cerrada revisada. Un agujero funcional no desaparece sin selección/autorización de edición. Exportación verificada en Blender.

## Fase 6 — V2: robustez automotriz e integración

Entregables:

- ArUco como ayuda opcional, restricciones visuales/geométricas ponderadas por confianza e información inercial como orientación/predicción.
- Cierres de recorrido validados y reducción de deriva; deshacer 10/30/60 segundos y puntos de recuperación.
- Perfiles de preview y fusión adaptados al presupuesto de memoria. Portar kernels medidos a C++ o al iPhone cuando las mediciones justifiquen el cambio.
- Separar modos de visualización calidad, textura, neutro y error de alineación; mejorar recomendaciones de regiones a recapturar.
- Atlas UV desde RGB frontal, exportación OBJ+MTL+texturas y pruebas de costuras/exposición.
- Complemento Blender para conexión con motor, sesiones, fragmentos, preview simplificado e importación final a escala.

Aceptación: recorridos repetidos sobre lateral/puerta/rueda; comparación con/sin marcadores, menor deriva y recuperación medible. El software informa cuando una superficie no permite estimar pose de forma confiable.

## Fase 7 — Gol completo y primera pieza física

Entregables:

- Escalar de esquina a lateral y luego carrocería por fragmentos con solapamiento y conexiones cruzadas.
- Mantener referencias fijas respecto al auto y medidas físicas reservadas exclusivamente para comprobación.
- Reconstrucción por bloques con distintos niveles de detalle; no cargar todo a máxima resolución en RAM.
- Escaneos locales de montajes complementados por calibre/medidas manuales.
- Diseñar un tramo de lip u otra pieza pequeña y verificar ajuste con plantilla/prototipo antes de una pieza grande.

Aceptación: modelo completo con reporte de dimensiones, incertidumbre práctica, zonas no medidas y deriva. Primera pieza con ajuste comprobado físicamente.

## Fase 8 — Extensiones avanzadas

- Fusión visual-inercial calibrada y optimización conjunta de geometría/observaciones visuales.
- Relocalización entre sesiones con cambios de iluminación y distribución opcional del tracking al iPhone para capturar sin PC.
- Fotos traseras en una pasada separada para textura de mayor detalle; pose y proyección verificadas, sin asumir captura de la misma superficie desde cámaras opuestas.
- Relleno manual tangente/curvatura y cierre avanzado con control de desviación geométrica.
- GLB texturizado y herramientas de medición más completas.

Cada capacidad se valida sobre el mismo banco de capturas que la versión anterior. REA queda como investigación acotada a preguntas concretas; no es dependencia del escáner.

## Contratos compartidos

- Modelo Group → Project → CaptureSegment → Frame; nubes y mallas son revisiones derivadas. Asociar calibración, poses y operaciones de edición por identificadores estables.
- Metros internos y transformaciones cámara→proyecto→grupo explícitas. El control de la vista 3D no altera estas transformaciones.
- Protocolo versionado bidireccional para capacidades, configuración, frames y comandos. Identificadores únicos, confirmación de persistencia y frontera de pausa evitan duplicación o integración después de detener.
- Estados de captura: PREVIEW, TRACKING, PAUSED, LOST, RELOCALIZING, DISCONNECTED. El estado de cámara activa es independiente de estar integrando. Una pausa o desconexión exige pose validada al reanudar.
- Ediciones no destructivas: máscaras/procedencia sobre mediciones, revisiones de poses y parámetros de malla. Las operaciones pesadas muestran progreso, admiten cancelación y no destruyen el resultado anterior.
- Colas acotadas: si no se puede persistir o procesar, reducir perfil de trabajo o pausar con aviso. Nunca crecer hasta consumir toda la RAM ni ocultar retrasos.

## Criterios iniciales de aceptación

Son metas de ingeniería, no precisión ya demostrada del sensor.

| Área | Meta inicial |
|---|---|
| Métrica local | Error absoluto ≤3 mm en el 95 % de al menos 20 medidas de 100–500 mm sobre objetos favorables; repetir capturas tres veces. |
| Relocalización MVP | Al menos 18/20 recuperaciones en ≤5 s desde volver a una región reconocible y 0 falsas aceptaciones en 20 casos negativos. |
| Datos | Conservar bloques confirmados tras desconexión/cierre, no duplicar frames al reconectar y no integrar frames posteriores a pausa. |
| Preview | ≥5 actualizaciones/s y latencia de estado p95 <1 s en perfil validado; medir tracking, transferencia y visualización por separado. |
| Recursos | Objetivo motor ≤3 GB y visor ≤1 GB; registrar RAM total con servicios del sistema. |
| Calidad | Frames idénticos repetidos no mejoran el indicador; zonas no vistas siguen desconocidas; degradación de pose no vuelve verde una región. |
| Edición | Conservar exclusiones al regenerar, deshacer/rehacer y detectar cambios de pose que exijan revisar una selección. |
| Grupo | Alineación sin cambio de escala, fijo estable, métricas verificables y proyecto recuperable tras reiniciar. |
| Vehículo | Error ≤10 mm en el 95 % de distancias de control de 0,5–2 m distribuidas por carrocería, no utilizadas para ajustar. |
| Malla/exportación | Mantener orificios funcionales, marcar completados, verificar cierre cuando se solicita, y conservar unidades/ejes/color en destinos compatibles. |

Las pruebas incluyen objetos tocando el piso, geometría repetitiva, falta de textura, brillo, movimiento rápido, bloqueo de teléfono, pulsaciones repetidas, cambios de red, disco lleno y calentamiento. Si un objetivo no se cumple, se identifica la causa y se revisa el alcance explícitamente.

Estado actual: especificación e investigación documental. No hay app, motor ni resultados físicos implementados todavía.


## Ampliación acordada — 2026-10-14

Estos requisitos se agregan al plan existente sin eliminar fases, entregables ni criterios de aceptación.

### UI/UX fiel a EXStar

- La interfaz y la experiencia de uso del proyecto deben ser exactamente iguales a EXStar donde sea viable, o lo más parecidas posible. Su sencillez, organización y facilidad de uso son criterios explícitos de diseño y aceptación.
- Aprovechar el acceso a EXStar para documentar pantallas, distribución de paneles, jerarquía visual, navegación, herramientas, controles del visor, mensajes, estados y secuencias de interacción. Distinguir lo observado directamente de lo pendiente de verificar con hardware o proyectos de ejemplo.
- Aplicar esta referencia desde el MVP y ampliarla en cada fase: preparación, escaneo, pausa/reanudación, limpieza, grupos de proyectos, alineación Fixed/Floated/Result, generación y edición de malla y exportación.
- Comparar cada flujo implementado con su equivalente en EXStar mediante capturas y recorridos de tareas. Documentar las diferencias necesarias por TrueDepth, el iPhone y el hardware disponible, conservando la sencillez del recorrido.
- Implementar la interfaz con código y recursos propios del proyecto. La fidelidad visual y funcional es el objetivo; las capacidades y límites que se muestran deben corresponder al sistema real.

### Proyecto open source y documentación en GitHub

- Todo el desarrollo debe quedar documentado en un repositorio público open source de GitHub, con código fuente y una licencia open source explícita compatible con las dependencias elegidas.
- Documentar objetivos, plan, arquitectura, protocolo, formatos de datos, decisiones técnicas, instalación, compilación, uso, pruebas, resultados, limitaciones y hallazgos del análisis de EXStar/REA. Mantener instrucciones reproducibles y una guía de contribución.
- Registrar tareas y errores en issues, organizar fases mediante hitos y conservar el historial de cambios y decisiones. Cada entrega de una fase debe incluir su documentación y evidencia de validación actualizadas.
- Publicar el código propio, scripts reproducibles y conclusiones del análisis. Mantener fuera del repositorio público los binarios originales o modificados de EXStar, credenciales, datos personales y archivos sin permiso de redistribución; documentar cómo reproducir el análisis sobre una instalación local.
- La referencia anterior a GitHub Actions privado describe la ruta inicial de compilación; el producto y su documentación tienen como destino el repositorio público open source. Documentar cualquier componente de firma o configuración que deba permanecer privado.

### Plan abierto a modificaciones según el análisis de REA con EXStar

- Este plan es una base de trabajo revisable. Los resultados del análisis de EXStar con REA pueden modificar arquitectura, tecnologías, prioridades, orden de fases, entregables y criterios de aceptación.
- Registrar cada hallazgo con su evidencia, versión de EXStar, entorno observado y grado de certeza; diferenciar resultados de la instalación original y de la copia UI Lab.
- Antes de iniciar una fase, revisar los hallazgos disponibles y actualizar el plan cuando aporten una mejora o invaliden una hipótesis. Registrar qué cambió, por qué y qué impacto tiene en las fases siguientes.
- Mantener el historial de revisiones en GitHub para conservar las decisiones anteriores. Que el plan sea revisable no implica quitar ahora ninguna de las capacidades acordadas.


## Decisión de publicación inicial

Por decisión posterior del usuario, el desarrollo comienza en el repositorio privado https://github.com/Mati10P/truedepth-automotive-scanner y se hará público cuando el proyecto esté listo. Esta decisión actualiza el momento de publicación indicado arriba: se mantienen el objetivo open source, la documentación continua y la elección de una licencia compatible antes de hacerlo público.
