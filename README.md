# TrueDepth Automotive 3D Scanner

Escáner de mano con iPhone TrueDepth y estación Windows para captura RGB–profundidad, inspección y futura reconstrucción 3D. El objetivo es obtener geometría útil para diseñar piezas automotrices en Blender. La experiencia de uso toma EXStar como referencia.

## Estado actual — 22 de octubre de 2026

La app **v10 está instalada y probada en el iPhone 16e**, con recepción de RGB y profundidad sincronizados en Windows. Se completó una calibración ChArUco y una corrección experimental de profundidad, comprobadas con los originales del tablero y de la caja de referencia.

**El error de profundidad bajó aproximadamente un 76 %: de 19,5 a 4,8 mm RMS, unas cuatro veces menos**, en las cinco poses del tablero reservadas para comprobación. Este resultado corresponde al conjunto de calibración RGB con ChArUco y corrección de profundidad; no a ChArUco por sí solo.

El proyecto sigue en validación geométrica. Todavía no hay reconstrucción acumulada ni tracking operativo. La correspondencia exacta en discontinuidades RGB–profundidad y la exactitud general del escáner siguen pendientes.

## Captura y control comprobados

- App iOS instalada mediante AltServer; captura física realizada con iOS 26.6.
- RGB nativo de **1440 × 1080** y profundidad de **640 × 480**, sincronizados mediante `AVCaptureDataOutputSynchronizer`.
- Guardado de originales PNG, profundidad float32 en metros y metadatos con timestamps, configuración y SHA-256.
- Transporte TCP persistente y visor experimental de nube de puntos. En una prueba de diez minutos se recibieron 2906 respuestas válidas, sin errores, a 4,84 Hz.
- Foco remoto manual en v10: registra por separado el valor solicitado y el real; comprueba finalización, modo bloqueado, ausencia de ajuste y estabilidad antes de aceptar la captura.
- Un único perfil de foco confirmado durante la caja previa, las 25 poses del tablero y las cajas posteriores.

El valor real de la lente puede diferir del solicitado. La v10 verifica y registra el valor que informa el dispositivo; no garantiza que el hardware adopte cualquier decimal exactamente.

La [rama de la app v10](https://github.com/Mati10P/truedepth-automotive-scanner/tree/codex/v10-stable-focus) y su [compilación verificada](https://github.com/Mati10P/truedepth-automotive-scanner/actions/runs/39837267130) conservan esa versión. Este README describe el avance comprobado del proyecto; las implementaciones experimentales y sus artefactos locales no están todas integradas en `main`.

## Calibración y resultados

Se utilizó un tablero ChArUco de 5 × 7 casillas de 25 mm, marcadores de 18 mm y diccionario `DICT_4X4_50`, con impresión compensada y confirmación física del usuario.

El ajuste usa **20 poses** y conserva **5 poses reservadas** para comprobación. La revisión adicional comprende los cinco originales de cada pose: **125 pares RGB–profundidad**. Las repeticiones temporales no se cuentan como posiciones independientes.

| Comprobación | Resultado |
| --- | --- |
| Calibración RGB: RMS de reproyección de ajuste | 0,159 píxeles |
| Calibración RGB: RMS medio de las poses reservadas | 0,158 píxeles |
| Profundidad reservada, antes de corregir | 19,5 mm RMS |
| Profundidad reservada, después de corregir | 4,8 mm RMS |
| Reducción del error de profundidad | Aproximadamente 76 % |
| Mayor error absoluto entre las medianas dimensionales de la caja | 1,94 mm |

La corrección utiliza una proyección común para RGB y profundidad y un modelo empírico de profundidad elegido con validación entre poses de entrenamiento. **Las dimensiones de la caja no se usaron para ajustar el modelo.** Se comprobaron después en tres posiciones, con 25 capturas en total.

Medianas de la caja elevada, usando el plano de cada panel para sus propias esquinas:

| Medida | Referencia del usuario | Resultado |
| --- | ---: | ---: |
| Ancho superior | 184 mm | 182,98 mm |
| Ancho inferior | 184 mm | 184,58 mm |
| Alto izquierdo | 140 mm | 139,45 mm |
| Alto derecho | 140 mm | 140,07 mm |

Estos errores dimensionales y el RMS del tablero son métricas distintas. **El resultado no garantiza una precisión de 2 mm para cualquier objeto, distancia o posición.** Persisten residuos locales, huecos en los bordes y sensibilidad a la selección de planos. El fondo de 144 mm de la caja todavía no pudo comprobarse con estas vistas frontales. La incertidumbre de las medidas físicas del tablero y la caja tampoco está certificada.

La corrección está implementada para procesamiento offline y exportación de nube PLY. Conserva huecos, comprueba la configuración y excluye puntos fuera de la cobertura de calibración. No se aplica automáticamente al visor en vivo. La profundidad original de entrenamiento abarca aproximadamente 0,292–0,419 m, con cobertura lateral limitada; no se extrapola como calibración general.

Las herramientas locales incluyen ajuste, comparación de modelos, evaluación de caja, validación temporal, gráficos y exportación. Se verificaron **13 pruebas pertinentes** de geometría, foco y calibración. Los originales y las mediciones detalladas permanecen conservados localmente.

## Próximos pasos

1. Verificar los residuos de profundidad en las posiciones más exigentes, la estabilidad entre sesiones y el rango de trabajo con referencias físicas medidas.
2. Resolver y comprobar la correspondencia residual RGB–profundidad en bordes observables; los huecos actuales no permiten localizar todas las discontinuidades.
3. Comprobar el fondo de la caja y otras dimensiones independientes antes de aceptar reconstrucciones métricas generales.
4. Probar pose y estabilidad con los marcadores ArUco del tablero existente. El tracking por marcadores no sustituye la calibración de profundidad.
5. Integrar una calibración validada al visor y continuar con seguimiento, recuperación de posición y acumulación 3D. REA/ICP siguen en pausa.

Las 25 poses originales ya están capturadas y conservadas. Las próximas capturas deben responder a verificaciones concretas; no es necesario repetir toda la serie por defecto.

## Código y documentación

El repositorio se mantiene privado durante el desarrollo; la selección de licencia open source está pendiente antes de hacerlo público. La documentación enlazada a continuación incluye antecedentes: para el estado más reciente prevalece este README.

- [Primer frame: ejecución, compilación e instalación](docs/implementation/FIRST_FRAME.md)
- Demo del receptor: `python apps/windows/receive_frame.py --demo`
- [Contexto del proyecto](PROJECT_CONTEXT.md)
- [Plan de desarrollo](ROADMAP.md)
- [Primera etapa de ejecución](docs/implementation/START_HERE.md)
- [Viabilidad y flujo](docs/FEASIBILITY_AND_WORKFLOW.md)
- [Evaluación de MeshLab](docs/research/MESHLAB_EVALUATION.md)
- [Investigación con REA](docs/research/REA_FIRST_PASS.md)
- [Tracking y pausa en EXStar](docs/research/EXSTAR_TRACKING_STATES.md)
- [Escaneo de objetos y selección de frames](docs/research/EXSTAR_OBJECT_SCAN.md)
- [Adaptador de algoritmos](docs/research/EXSTAR_ALGORITHM_DISPATCH.md)
- [Motor de recuperación](docs/research/EXSTAR_RECOVERY_ENGINE.md)
- [Generación de candidatos de registro](docs/research/EXSTAR_REGISTRATION_CANDIDATES.md)

## Inventario de EXStar

Requiere Python 3 y usa solo la biblioteca estándar. Ejecutar desde la raíz del repositorio, con una instalación propia de EXStar:

```powershell
python tools/inventory_exstar.py --source C:\Shining3d\EXStar --output .local/exstar-inventory.json
```

La herramienta calcula hashes y extrae nombres de temas, publicadores, suscriptores y asociaciones de dos XML. No ejecuta EXStar. El archivo de salida debe ser nuevo y estar fuera de la instalación.

Las capturas, los códigos de sesión, las credenciales, el material de firma y los binarios propietarios quedan fuera del repositorio.
