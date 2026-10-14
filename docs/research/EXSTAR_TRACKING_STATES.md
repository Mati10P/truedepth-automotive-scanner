# EXStar: seguimiento, pausa y actualización de la escena

Fecha: 2026-10-14. Continuación de [REA: primer pase](REA_FIRST_PASS.md).

## Preguntas de esta investigación

1. ¿Qué funciones consultan `trackRet` y qué hacen con ese resultado?
2. ¿Qué significa el comando `pause` en el controlador de seguimiento/fusión?
3. ¿Se pueden distinguir la configuración del seguimiento y la configuración de la fusión?
4. ¿Qué podemos adoptar como especificación de comportamiento y qué necesita más evidencia?

Objetivo estático: `C:\Shining3d\EXStar\ScanAlignFusionProcess.dll`, EXStar 1.2.2.0, SHA-256 `a31c489a10cce7ed093d036d891ef67edba9015aa46c9779fadc50b38683bc4e`. Se conserva la instalación original. Los resultados de descompilación permanecen en `.local/rea-evidence/`.

La biblioteca contiene controladores IR, WL y Sequence. Seguir una rama concreta no demuestra que todos los dispositivos o modos de EXStar usen esa misma ruta. La selección efectiva de controlador para EINSTAR debe trazarse por separado o verificarse con el dispositivo.

## Procedimiento reproducible

Para evitar reimportar la DLL en cada consulta se creó [rea-session.mjs](../../tools/rea-session.mjs). Usa el cliente MCP incluido en la instalación local de REA y arranca el servidor oficial con `--mcp`. No registra un servidor en Codex ni modifica su configuración. Mantiene un único proveedor Ghidra y procesa las consultas secuencialmente.

Requisitos: los de la primera investigación, con REA 6.4.0, Ghidra 12.1.4 y JDK 21. El helper usa un heap Java de 2 GB, 15 minutos para iniciar el análisis y un timeout del cliente de 1000000 ms por consulta.

```powershell
node tools/rea-session.mjs
```

Esperar el mensaje `ready`. Escribir un objeto JSON por línea. Ejemplo de apertura y consulta:

```json
{"name":"open_binary","arguments":{"path":"C:\\Shining3d\\EXStar\\ScanAlignFusionProcess.dll","provider_id":"ghidra"},"output":"tracking-open.json"}
{"name":"xrefs","arguments":{"address":"0x180148d50"},"output":"track-ret-xrefs.json"}
```

El helper guarda la respuesta completa en `.local/rea-evidence/` y muestra el nombre del archivo y si la herramienta reportó un error. Los nombres de salida deben ser nuevos: no sobrescribe evidencia. Inspeccionar `structuredContent.normalized_result`; las respuestas de apertura/cierre usan `structuredContent.result`.

Seguir cada dirección referenciada con `resolve_containing_procedure`, y consultar `procedure_pseudo_code` con la entrada real de la función. No confundir direcciones de cadenas con entradas de código. Los esquemas anunciados por la versión instalada se guardan en `session-tool-schemas.json`.

Terminar siempre con:

```json
{"close":true}
```

Esto cierra el objetivo, el cliente y el proceso del servidor. Las operaciones permitidas se limitan a apertura/cierre, referencias, resolución de funciones, metadatos y pseudocódigo. No ejecutan EXStar ni modifican sus bytes.

## Criterios para interpretar los hallazgos

- **Cadena:** solo demuestra que ese texto existe en el binario.
- **Referencia:** relaciona una dirección con código o datos analizados; no demuestra ejecución en vivo.
- **Rama descompilada:** permite describir una condición y sus acciones dentro de esa función, con los límites de tipos y llamadas que Ghidra pudo recuperar.
- **Hipótesis:** sirve para decidir qué inspeccionar después; no se presenta como comportamiento confirmado.
- **Requisito propio:** proviene del objetivo del proyecto, aunque EXStar no lo haya demostrado en esta investigación.

## Hallazgos estáticos confirmados

### 1. Referencias y funciones localizadas

La búsqueda de referencias devolvió 57 direcciones para la cadena `trackRet` y 13 para `pause`. No son necesariamente 57 y 13 funciones diferentes. Se resolvieron entradas mediante el gestor de funciones de Ghidra, sin adivinarlas por proximidad.

| Función analizada | Evidencia usada para identificar su papel | Alcance |
|---|---|---|
| `0x1800139a0` | Referencias a `pause`, `trackRet`, `flushScanData` y registros del controlador IR | Coordinación de parada/pausa y envío de datos; el nombre original de la función no está recuperado |
| `0x1800574f0` | Cadena cualificada `IRSpeckleTrackFusionProcessControllerPrivate::sendDataToSceneController` dentro de los registros | Preparación de datos para la escena/cliente |
| `0x18007b550` | Referencia a `pause` y registros de `SequenceTrackFusionProcessControllerPrivate.cpp` | Otra ruta de espera de frames y envío final de datos, en la rama Sequence |
| `0x1800429a0` | Nombre cualificado `IRSpeckleTrackFusionProcessControllerPrivate::resFusion` dentro de los registros | Manejo de resultados, códigos y datos asociados a un timestamp |
| `0x1800640b0` | Nombre cualificado `IRSpeckleTrackFusionProcessControllerPrivate::trackFusionThread` dentro de los registros | Consumo de una cola de frames y selección de rutas según flags |

Los archivos locales `tracking-loop-pseudo.json` y `pause-secondary-pseudo.json` son etiquetas de trabajo. En particular, el nombre `tracking-loop` fue elegido antes de leer el resultado y **no significa que se haya identificado el bucle algorítmico de tracking**.

### 2. La coordinación de pausa tiene trabajo pendiente que completar

En `0x1800139a0` se observa esta secuencia general:

1. Consulta repetidamente un contador, con espera/cesión del hilo, entre registros que indican espera y recepción de frames. La interpretación de que espera trabajo pendiente se apoya en ambos elementos; todavía no se identificó la estructura completa de la cola.
2. Prepara comandos `pause` para rutas con destinos `norigid` o `rigid`, según un campo interno. Para la ruta rígida busca `SpeckleTrackAndFusionAlgManager`; hay caminos de llamada directa y publicación de mensajes.
3. Prepara una notificación con `type=pause` y la pasa a un auxiliar.
4. Prepara/publica `flushScanData`, con `scanType=handleScan` y datos asociados al escaneo. La función también contiene un camino de `cancelScan` y una notificación condicional `cleanProjData`.

La rama Sequence `0x18007b550` también espera a que un contador llegue a cero, prepara `type=pause` y entrega `flushScanData` a otro auxiliar.

**Límite:** todavía no se trazó el evento de UI que llama a estas funciones ni los receptores de todos esos mensajes. No se afirma que cualquier pausa manual recorra toda esta secuencia, que `flushScanData` implique por sí solo persistencia en disco, ni que `cleanProjData` borre o conserve todo el modelo. Tampoco demuestra reanudación/relocalización.

**Decisión propuesta para nuestro diseño:** distinguir `pausando` de `pausado`. La UI debe saber cuándo se dejó de aceptar captura y cuándo terminó el trabajo pendiente. La política sobre frames pendientes y persistencia debe ser explícita y verificable.

### 3. `trackRet` depende del contexto

En la función de envío a escena `0x1800574f0`, una rama que también agrega `isBody=true` reemplaza `trackRet` por el resultado booleano de comparar dos campos internos (offsets `0x5bc` y `0x5c0`). El significado exacto de esos campos sigue pendiente. En las rutas de pausa analizadas también se construye `trackRet=1` al preparar datos de marcadores personalizados.

Por tanto, **el campo transportado a la UI no debe tratarse automáticamente como el retorno crudo del algoritmo**. Hace falta identificar su productor, modo y consumidor antes de asignarle una semántica universal de éxito/pérdida/recuperación. Que una rama escriba `1` no demuestra que acabe de relocalizar.

### 4. Actualización de escena y distancia

`0x1800574f0` prepara un mensaje con:

- `cmd=putSceneData`.
- `target=SpeckleSendDataToClientController`.
- `type=frameOrIncrease`.
- `updateCameraOrDistance=true`.
- Campos adicionales condicionados por el estado, incluidos `trackRet`, `isBody` y `clearPrompt`.

Después solicita la publicación mediante Qt. Esto confirma una ruta explícita de datos hacia el cliente/vista. No identifica todavía la fórmula de distancia, la paleta de calidad ni el mecanismo que conserva el mapa geométrico.

Se descompiló también el auxiliar `0x180056f50`: contiene el registro `sendCurStateToSceneController`, copia el mapa recibido, agrega `cmd=setConfig` y publica el mensaje. Así se confirma que `type=pause`, `clearCurData` y `cleanProjData` pasan por una ruta de notificación/configuración de escena. El efecto final de esos tipos sigue dependiendo del receptor.

### 5. Hay controles separados de validez, procesamiento y presentación

En `trackFusionThread` (`0x1800640b0`) se observa:

- Obtención de frames mediante `Sn3DFrameDataQueue::get` y reintento cuando no hay datos.
- Una espera cuando el número de entradas de una estructura pendiente alcanza un límite interno. Es evidencia de regulación de trabajo pendiente, no una medición de la latencia real.
- Lectura de `FDO_CUR_FRAME_VALID`. Si es falso, no entra en las llamadas de procesamiento de la rama válida; incrementa un contador.
- Al superar cuatro frames inválidos consecutivos, y mientras un flag de salida no esté activo, prepara `type=clearCurData` para un auxiliar. Un frame válido reinicia ese contador.
- Para frames válidos, lee por separado `FDO_CUR_FRAME_FUSING` y selecciona funciones distintas según ese flag y el modo interno. Una de las llamadas apunta a `0x180053e50`, localizada mediante referencias al nombre `scan_Object`.

**Límites:** no está identificado todavía quién determina `FDO_CUR_FRAME_VALID`, por lo que no se equipara automáticamente con confianza de pose o pérdida de tracking. `clearCurData` tampoco prueba que se borre el escaneo acumulado; falta seguir su receptor. El umbral observado no es una recomendación para nuestro sensor.

En `resFusion` (`0x1800429a0`) se leen `timeStamp` y `errorCode` del mensaje recibido. En la rama con el campo interno de modo `0x44` distinto de cero:

- Si `errorCode != 0` y existe la entrada del timestamp, prepara datos para la escena con `trackRet=0` y una transformación almacenada, llama a `sendDataToSceneController`, actualiza auxiliares de estado y retira esa entrada pendiente. No sigue el bloque de procesamiento del caso cero.
- Si `errorCode == 0`, busca la entrada pendiente y examina `useParallel`; un valor verdadero retorna por una ruta separada.
- Para el caso no paralelo lee un indicador bajo `isNeed`. Un bloque condicionado por ese indicador contiene, entre otras operaciones, la preparación/publicación de `cmd=integrate`, con condiciones adicionales dentro del bloque.
- Más adelante prepara `trackRet=1` y envía datos a la escena. Esa asignación queda fuera del bloque principal condicionado por `isNeed`.

La rama de modo cero contiene un tratamiento especial del código `0x2a30000b`, junto con otros campos internos, al calcular `trackRet`. Se registra el valor como ancla sin asignarle un nombre de error no verificado.

La retirada de la entrada pendiente se comprobó descompilando `0x180041a20`: busca la clave numérica recibida y libera/rebalancea el nodo correspondiente del mapa Qt. En la llamada observada, la clave es el timestamp del resultado. Esto no es una eliminación del modelo 3D acumulado.

**Conclusión acotada:** hay una separación real entre obtener un frame, decidir por qué ruta procesarlo, emitir trabajo de integración y preparar su representación visual. No se ha recuperado todavía el algoritmo que produce la pose, evalúa su confianza o reconoce una zona ya escaneada.

### 6. Tabla de condiciones observadas

| Punto | Condición observada | Acción comprobada | Lo que sigue sin demostrar |
|---|---|---|---|
| Hilo IR | No hay frame en la cola | Reintenta, cede el hilo y puede registrar timeout | Política completa de pérdida de conexión |
| Hilo IR | `FDO_CUR_FRAME_VALID=false` | Incrementa contador y evita la rama de procesamiento válido | Si el motivo es profundidad, tracking u otro filtro |
| Hilo IR | Más de cuatro inválidos consecutivos y flag de salida desactivado | Entrega `clearCurData` a un auxiliar | Qué contenido elimina el receptor |
| Resultado IR, modo no cero | `errorCode != 0` y timestamp presente | Envía `trackRet=0`/transformación almacenada a escena y retira trabajo pendiente | Significado de cada código y conservación global del mapa |
| Resultado IR, modo no cero | `errorCode=0`, no paralelo, indicador `isNeed` activo | Habilita un bloque que incluye una ruta de publicación `integrate` | Criterios que producen `isNeed` y efecto final del receptor |
| Presentación IR | Rama que agrega `isBody=true` | Recalcula el `trackRet` enviado al cliente | Semántica exacta de los contadores comparados |
| Coordinación IR / Sequence | Contador de trabajo pendiente llega a cero | Continúa la preparación de pausa y envío final de datos | Evento exacto de UI que disparó esta ruta |

**Decisión propuesta para nuestro protocolo:** conservar campos distintos para validez del frame, validez/confianza de pose, integración aceptada y estado de presentación. Nunca decidir si se fusiona geometría a partir del color de la preview o de un booleano pensado solo para la UI.

## Registro de evidencia

Todos los IDs siguientes proceden de REA/Ghidra sobre el hash de DLL indicado arriba. Los JSON MCP completos están bajo `.local/rea-evidence/` y no se publican con el repositorio.

| Archivo local | Operación / ancla | Evidence ID |
|---|---|---|
| `track-ret-xrefs.json` | Referencias a `0x180148d50` | `ev_167cac29495d6ee6e0621aa25318dada1485ddb54fdbc6bee1835455cb21d03a` |
| `pause-xrefs.json` | Referencias a `0x180149144` | `ev_b5e4bf1a13fb5d729ec6cd9b8c768bb75bc6cda78c7cdcee223f4738f385da75` |
| `tracking-loop-pseudo.json` | Descompilación `0x1800139a0` | `ev_008ae6a336e6ef0e0c5d96354cfc311cee8bac2882251659139c9be3da46d377` |
| `send-scene-pseudo.json` | Descompilación `0x1800574f0` | `ev_d3b18906fae1f699eac35613ac7ab1b954f6b4714f2a286d87d4957af17c6a0f` |
| `pause-secondary-pseudo.json` | Descompilación `0x18007b550` | `ev_5d49f113f93b037aad3723fd86c82889fb0e04364450ed43e1c7ac90532feb58` |
| `res-fusion-pseudo.json` | Descompilación `0x1800429a0` | `ev_e8cd966a068fd93587bace1e11998b9bbbf0cfacef5a35603fe444bace87d2f8` |
| `track-thread-pseudo.json` | Descompilación `0x1800640b0` | `ev_4aa523d673b02ebf20e6137a748acc24f9f26e14969f67dbdbc2e55053c6f9a5` |
| `pending-frame-remove-pseudo.json` | Descompilación `0x180041a20` | `ev_2bd0a2618a5c1c49d26be35a629dc58a710f08a199480a14df7ce6d412b99cf0` |
| `state-event-publish-pseudo.json` | Descompilación `0x180056f50` | `ev_194127e6c19b10247f308d7bfbe667e30e26656c93e072d9d55c78cf928efb33` |

La configuración del primer pase sugiere dónde buscar, pero los hallazgos de este documento provienen de referencias y pseudocódigo. La descompilación conserva límites: tipos inferidos, auxiliares no trazados y posibles referencias indirectas no recuperadas. No se ejecutó EXStar durante estas consultas.

## Cierre y verificación

- Se completaron siete descompilaciones y se conservaron 23 registros de evidencia en la sesión.
- `close_binary` guardó `.local/rea-evidence/tracking-session-snapshot.json` (593864 bytes), y luego se cerraron el cliente y el servidor. La respuesta quedó en `tracking-close.json`.
- Ese snapshot informa **cero entradas primitivas/workflow reutilizables**: conserva los 23 registros de evidencia, pero no debe presentarse como una base de Ghidra capaz de evitar el análisis de consultas nuevas.
- Se comprobó de nuevo el SHA-256 de la DLL original después de las consultas; coincide con la línea base.
- El helper pasó comprobación de sintaxis y una prueba de inicio/cierre con entrada por tubería. Un intento de solicitar `set_address_name` fue rechazado por la lista permitida antes de llamar a REA o crear un archivo de salida.
- Se comprobaron los enlaces locales y la existencia de todos los identificadores de evidencia citados. No quedaron procesos Java de esta investigación después del cierre.
- La publicación en GitHub contiene documentación y el helper reproducible. Pseudocódigo, snapshot, logs y binarios permanecen fuera de Git.

## Comportamiento que nuestro producto debe validar

Estos requisitos ya pertenecen al proyecto; no son conclusiones sobre el algoritmo interno de EXStar:

| Situación | Comportamiento requerido |
|---|---|
| Preview antes de escanear | Mostrar profundidad, distancia y estado; mantener separada la vista del frame de la geometría aceptada |
| Escaneo con pose válida | Incorporar geometría y actualizar indicadores de cobertura/calidad |
| Pérdida de seguimiento | Suspender la incorporación, conservar lo válido y guiar hacia una zona ya escaneada |
| Pausa manual | Conservar sesión y permitir inspeccionar el modelo |
| Reanudación después de mover el iPhone | Validar la alineación con el modelo antes de incorporar geometría |
| Objeto girado para otra cara | Crear un proyecto/escaneo independiente y alinearlo después |

Una captura de prueba debe registrar timestamps, transición de estado, motivo de rechazo y el último frame aceptado. La prueba de recuperación debe comprobar que no se añadió geometría durante una pose inválida y que no se perdió el modelo previo. El estado visual verde no equivale por sí solo a precisión dimensional garantizada.

## Próximas preguntas acotadas

1. Seguir el productor de `FDO_CUR_FRAME_VALID` y del indicador `isNeed`, separando adquisición, pose y criterio de integración.
2. Examinar `scan_Object` (`0x180053e50`) y el adaptador de algoritmos para localizar el cálculo de pose y la gestión del mapa de referencia.
3. Identificar los códigos de resultado, en particular `0x2a30000b`, a partir de sus productores y usos; no asignarles significados por intuición.
4. Seguir los receptores de `setConfig`/`type=pause`, `clearCurData`, `cleanProjData` y `flushScanData`, y contrastar la ruta con UI Lab donde sea accesible.
5. Verificar qué controlador selecciona el modo EINSTAR utilizado como referencia.

La investigación no confirma todavía relocalización automática, algoritmo de registro, conservación del mapa en todos los modos, tolerancias geométricas ni compatibilidad del motor propietario con TrueDepth. Los siete procedimientos descompilados aportan una base concreta para especificar coordinación, colas y estados sin dar esos puntos por resueltos.
