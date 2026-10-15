# EXStar: preparación del escaneo de objetos y selección de frames

Fecha de documentación: 2026-10-15. Tercera tanda de análisis estático con REA 6.4.0 y Ghidra 12.1.4. Complementa [Seguimiento y pausa](EXSTAR_TRACKING_STATES.md); no reemplaza ni recorta el roadmap.

## Resultado

Se localizó un productor inicial de `FDO_IS_NEED`/`isNeed` en `scan_Object`. Su valor depende de una condición periódica y, en la ruta `fusion_without_track`, de una comparación entre dos poses. Por lo tanto, este indicador no debe interpretarse como una medida directa de confianza de tracking. Se transmite como un booleano compartido: falta seguir al receptor para saber si lo modifica antes de devolver el resultado.

Se confirmó también que esta función prepara una solicitud con geometría, pose, timestamp y opciones de textura, la registra como trabajo pendiente y la publica. No se recuperó en esta tanda el algoritmo que calcula la pose o recupera el seguimiento.

## Identidad y alcance

- Archivo original: `C:\Shining3d\EXStar\ScanAlignFusionProcess.dll`.
- SHA-256 antes y después: `a31c489a10cce7ed093d036d891ef67edba9015aa46c9779fadc50b38683bc4e`.
- Función principal: `0x180053e50`, 12529 bytes según Ghidra. El log incrustado la identifica como `IRSpeckleTrackFusionProcessControllerPrivate::scan_Object`.
- Auxiliar de comparación: `0x1800322a0`; nombre funcional propuesto, no símbolo original recuperado.
- Perfil de análisis: `90e13888e18b7d587414bb259f5e3dc44a7c9293bdf290ad8c459be524747d9f`.
- Las direcciones son virtuales de la imagen analizada; no direcciones observadas en un proceso en ejecución.

Se analizó la instalación original en lectura. No se ejecutó EXStar ni se modificaron sus archivos. El pseudocódigo es una reconstrucción de Ghidra, con tipos inferidos y advertencias de bloques considerados inalcanzables; no es el código fuente original.

## Paso a paso realizado

1. Abrir la DLL original en una sesión persistente del helper `tools/rea-session.mjs` para reutilizar el proceso de análisis durante las consultas.
2. Descompilar `0x180053e50`, previamente localizada mediante referencias al texto `scan_Object`.
3. Seguir la construcción de `cmd`, `rt`, `timeStamp`, `frameData` e `isNeed`, separando los campos enviados de los resultados calculados por otras funciones.
4. Obtener las referencias salientes: 2109 referencias totales, que incluyen datos y pila, no 2109 llamadas. REA informa una llamada sin destino resuelto en `0x18005402c`.
5. Descompilar el auxiliar `0x1800322a0` utilizado al inicializar `isNeed` en una de las rutas.
6. Contrastar ese productor con el consumidor `resFusion` del informe anterior y comprobar nuevamente el hash del archivo.

Los JSON completos se conservaron en `.local/rea-evidence/`; se publican las observaciones y su trazabilidad, no los binarios ni el pseudocódigo completo.

## Selección de operación

La función lee `FDO_CUR_FRAME_MARKER_REBUILD_RET` y campos de configuración internos. En una rama construye `cmd=fusion_and_track`; cuando se cumple una combinación de bits de modo y el resultado de marcadores vale cero, lo cambia a `fusion_without_track`. Existen además rutas de presentación sin enviar esa solicitud y una llamada virtual cuyo destino no quedó resuelto.

Los nombres de operación son observables. No prueban que `fusion_without_track` integre geometría sin una pose: la solicitud transporta `rt`, obtenido de `FDO_CUR_FRAME_RT`. Tampoco prueban relocalización, ni permiten asignar nombres definitivos a los bits de modo.

En otra ruta de presentación, `trackRet` se calcula a partir del resultado de marcadores, incluyendo un tratamiento especial de `0x2a100005`. No se identificó el nombre de ese código. Esto refuerza la necesidad de interpretar `trackRet` en el contexto de cada rama.

## Datos preparados para el motor

| Grupo | Campos observados | Alcance de la observación |
|---|---|---|
| Identificación | `handleName`, `from`, `timeStamp`, `fid` | Vinculan solicitud, controlador y frame |
| Geometría y pose | `specklePointCloud`, `rt`, `currentVids`, `increaseData` | Se transportan valores del objeto de frame; aquí no se demostró su cálculo |
| Selección y opciones | `isNeed`, `isPlane`, `samplingRadius`, `numThread`, `refCloudCount` | Sus nombres no establecen unidades, valores por defecto ni efectos completos |
| Textura | `hasTex`, `isTexModel`, y condicionalmente `texImage`, `rtLeft2Color`, `texFeature` | Hay rutas que transportan imagen, transformación y características de textura |
| Modo | Condicionalmente `isTexTrack`, `useParallel`, `scanning`, `withTex` | No todas las opciones aparecen en todas las ramas |

La función inserta el mapa de solicitud en la estructura pendiente del objeto en offset `+0x50`, usando la misma clave que coloca en `timeStamp`, bajo un mutex. Luego invoca `publish` mediante Qt con la cadena `Sn3DTrackFusionProcess`. En la tanda anterior se observó que `resFusion` busca ese timestamp y retira entradas pendientes en determinadas ramas.

Esto proporciona evidencia de correlación de trabajo asíncrono. No confirma persistencia en disco, entrega garantizada ni que el receptor concreto sea siempre el mismo en todos los modos.

## Cómo se inicializa `isNeed`

Los offsets siguientes son relativos al objeto controlador. Los nombres de las variables de configuración todavía no están recuperados.

| Condición en la rama que prepara la solicitud | Booleano inicial |
|---|---|
| Flag en `+0x598` desactivado | `false` |
| Flag activo; se incrementa el contador `+0x5a0` y no coincide la periodicidad definida por `+0x59c` | `false` |
| Coincide la periodicidad y la operación es `fusion_and_track` | `true` |
| Coincide la periodicidad y la operación es `fusion_without_track` | Negación del resultado booleano del auxiliar `0x1800322a0` |

La periodicidad se observa como un módulo del contador por el entero de configuración. No se establecieron el valor de ese entero, su inicialización ni su validación. No corresponde presentar una frecuencia concreta de integración.

El auxiliar recibe la pose almacenada en `+0x548`, la pose `rt` de la solicitud y dos umbrales de configuración en `+0x5a8` y `+0x5a4`. Compara:

1. La distancia euclídea entre los componentes 9, 10 y 11 de ambos arreglos.
2. Tres ángulos entre grupos correspondientes de tres componentes de los primeros nueve valores, mediante productos escalares normalizados y `acosf`.

Devuelve verdadero en su byte bajo si la distancia y los tres ángulos son menores que sus respectivos umbrales. En el llamador se niega ese resultado para inicializar el booleano de la ruta `fusion_without_track`.

**Interpretación respaldada, todavía parcial:** la estructura es compatible con comparar traslación y orientación para evitar seleccionar poses demasiado similares. Se conocen las operaciones y sus condiciones; siguen sin confirmar las unidades de traslación, los umbrales efectivos, las convenciones matriciales y cuándo se actualiza la pose de referencia. La conversión angular visible usa `180 / 3.14`; no se debe copiar como recomendación numérica para nuestro motor.

El valor se guarda en un `shared_ptr<bool>` dentro de `FDO_IS_NEED` y se recupera para el campo `isNeed` de la solicitud. El consumidor analizado anteriormente lee ese booleano compartido. **No se comprobó que conserve su valor inicial durante todo el procesamiento.**

## Consecuencias para nuestro proyecto

Estas son decisiones propuestas para nuestra implementación, no funciones nuevas atribuidas a EXStar:

- Separar validez de adquisición, calidad de pose, selección para integración y estado visual. Un frame puede servir para seguimiento aunque no aporte geometría nueva.
- Registrar el motivo de selección o rechazo y el identificador del frame. La cadencia y la novedad de vista deben ser criterios explícitos, medibles y distintos del éxito de tracking.
- Definir mensajes propios con timestamp, unidades, convención de pose, versión de calibración y propiedad de los datos. Los punteros compartidos internos de EXStar no constituyen un protocolo transportable del iPhone a Windows.
- Mantener separadas textura de exportación y características RGB usadas para seguimiento. Aquí se observan campos para ambos propósitos; su efectividad con TrueDepth debe medirse con datos propios.
- Validar que una pose inválida nunca permita incorporar geometría al modelo aceptado, aunque otro indicador de selección esté activo.

El roadmap mantiene sus requisitos. Estos hallazgos afinan la especificación de captura y procesamiento; no justifican retrasar indefinidamente la prueba de un frame TrueDepth real en Windows.

## Evidencia y duración

| Archivo local | Consulta | Evidence ID |
|---|---|---|
| `scan-object-pseudo.json` | Descompilar `0x180053e50` | `ev_c46d1c6fadd6639ecbcabc91158d0c25205626b41a4525cc7e6e427d8315adf7` |
| `scan-object-outgoing.json` | Referencias salientes de `0x180053e50` | `ev_e8b4feb748f87c87317783f559627a4cac09d6507ba4fe73114cdabc5a2c0e34` |
| `scan-pose-comparison-pseudo.json` | Descompilar `0x1800322a0` | `ev_9fbfbba2c8fa0d8c67133a1acec2a7c0a4d3c515343a72cd9a43bd960160ce89` |

El log del servidor registra 581335,66 ms para la primera consulta, que disparó la preparación de Ghidra; 4560,23 ms para referencias y 84,91 ms para el auxiliar. Son duraciones de herramientas, no el tiempo total de lectura e interpretación. No hay evidencia de que internet haya sido el cuello de botella de estas consultas locales.

Tras la interrupción del turno, la sesión de terminal ya no estaba disponible. Se conservaron las tres respuestas exitosas; no se obtuvo un snapshot de cierre para esta tanda. La comprobación posterior no encontró procesos Java/Node con líneas de comando de REA, el helper o Ghidra. No se abrió otra sesión para repetir cálculos ya guardados.

## Preguntas que siguen abiertas

Actualización: [Del comando de escaneo al motor de tracking](EXSTAR_ALGORITHM_DISPATCH.md) sigue los receptores en `Sn3DAlgorithmWrapper.dll` y confirma una escritura posterior a la llamada del motor sobre `isNeed` en la ruta de textura. El algoritmo interno permanece pendiente; las preguntas siguientes conservan el estado al cerrar esta tercera tanda.

1. Seguir los receptores de `fusion_and_track` y `fusion_without_track` en el adaptador de algoritmos, incluyendo posibles escrituras al booleano compartido.
2. Identificar la inicialización de los umbrales y la actualización de la pose almacenada en `+0x548`.
3. Localizar el productor de `FDO_CUR_FRAME_VALID`, que todavía no puede equipararse a tracking válido.
4. Identificar el algoritmo de recuperación, su mapa de referencia y criterios de aceptación. Esta tanda no lo demuestra.
5. Confirmar qué ramas ejecuta realmente EINSTAR y contrastarlas con observaciones de funcionamiento cuando exista hardware adecuado.

Se cerró una pregunta concreta: dónde y con qué condiciones se inicializa `isNeed` en esta ruta. No se considera terminado el análisis de EXStar ni demostrada la reutilización de su motor con TrueDepth.
