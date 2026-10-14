# Evaluación de MeshLab para TrueDepth Automotive 3D Scanner

Fecha: 2026-10-14. Evaluación documental mediante fuentes oficiales; no se instalaron paquetes ni se hicieron benchmarks. El plan existente no se modifica.

## Conclusión

Sí conviene evaluar MeshLab como herramienta de comparación y PyMeshLab como biblioteca de procesamiento posterior. La recomendación es mantener la interfaz propia con la experiencia de EXStar y llamar a los filtros desde el motor Python. No basar el escáner completo en la aplicación MeshLab.

## Capacidades verificadas

MeshLab ofrece registro ICP, ajuste global, limpieza, reconstrucción, simplificación, texturas y análisis geométrico. [Sitio oficial](https://www.meshlab.org/).

PyMeshLab permite cargar datos, aplicar filtros y guardar resultados desde Python. Esto permite integrar operaciones sin abrir la UI de MeshLab. [Repositorio oficial](https://github.com/cnr-isti-vclab/PyMeshLab), [guía inicial](https://pymeshlab.readthedocs.io/en/latest/intro.html).

| Necesidad | Encaje propuesto |
|---|---|
| Limpieza y simplificación | Candidato para fases 4–5 y comparación con el motor base. |
| Alinear proyectos terminados | ICP como alternativa/comparación; nuestro sistema conserva selección de pares, inicialización, validación y revisiones. |
| Generar malla | Comparar Ball Pivoting y Screened Poisson con los resultados de la fusión. |
| Rellenar huecos elegidos | Usar selección de caras de borde; nuestro visor identifica el agujero y traduce el clic a esa selección. |
| Suavizar y editar | Ejecutar sobre revisiones derivadas; medir cuánto cambia la geometría. |
| Captura TrueDepth y transporte | Desarrollar en la app iOS y el protocolo del proyecto. |
| Tracking/relocalización en vivo | Mantener el motor propio previsto; registro entre modelos no equivale a recuperación en vivo. |
| Calidad verde/amarillo/rojo | Derivar de observaciones, profundidad y pose; no asumir que un atributo de calidad de MeshLab tiene esa semántica. |
| UI/UX EXStar | Implementar visor, estados, controles y flujos propios; PyMeshLab aporta operaciones, no esa experiencia. |

Los últimos cuatro puntos y la distribución por fases son decisiones de arquitectura propuestas, no prestaciones prometidas por MeshLab.

## Detalles que condicionan la integración

Los filtros documentados incluyen `compute_matrix_by_icp_between_meshes`, `meshing_decimation_quadric_edge_collapse`, `meshing_close_holes`, `generate_surface_reconstruction_ball_pivoting` y `generate_surface_reconstruction_screened_poisson`. Poisson requiere puntos orientados; Ball Pivoting usa normales y un radio que afecta los huecos. En Close Holes, el umbral se expresa en cantidad de aristas, no milímetros. [Filtros oficiales](https://pymeshlab.readthedocs.io/en/latest/filter_list.html).

No equiparar Poisson con geometría medida: conservar la nube y revisar las superficies completadas. No prometer que estos filtros reproducen exactamente los modos semi/watertight o los rellenos plano/tangente/curvatura de EXStar.

`MeshSet` no es seguro para ejecutar filtros simultáneamente sobre el mismo objeto. Propuesta: un proceso de trabajo separado, operaciones serializadas por revisión y resultados guardados antes de aplicarlos. Si un filtro no admite cancelación interna, cancelar el proceso sin perder la entrada. [API MeshSet](https://pymeshlab.readthedocs.io/en/latest/classes/meshset.html).

Hay distribución para Windows de 64 bits. La documentación de instalación no exige NVIDIA/CUDA; eso no prueba que todos los plugins funcionen en la Radeon disponible ni que una carrocería completa quepa en RAM. Validar el subconjunto elegido y procesar por fragmentos. [Instalación](https://pymeshlab.readthedocs.io/en/latest/installation.html), [paquetes publicados](https://pypi.org/project/pymeshlab/).

PyMeshLab declara GPL-3.0. Antes de adoptar la dependencia como parte distribuida, registrar la licencia del proyecto y compatibilidad de los componentes concretos; GPL-3.0 es una opción candidata, aún no una licencia elegida. [Repositorio y licencia](https://github.com/cnr-isti-vclab/PyMeshLab).

## Prueba propuesta antes de adoptarlo

1. Usar un entorno aislado y fijar versión; registrar filtros disponibles y errores de carga.
2. Comparar con Open3D sobre las mismas nubes y mallas: pieza con orificios funcionales, dos capturas solapadas y un panel incompleto.
3. Medir tiempo, RAM máxima, desviación geométrica, escala, conservación de huecos y atributos. Empezar con fragmentos pequeños y escalar según resultados.
4. Verificar exportación en Blender, repetibilidad y recuperación ante fallo/cancelación.
5. Adoptar solo las operaciones con ventaja demostrada, documentando parámetros y resultados en GitHub.

Esta evaluación favorece usar PyMeshLab en el posprocesamiento; no demuestra todavía rendimiento ni precisión sobre capturas reales de nuestro iPhone.
