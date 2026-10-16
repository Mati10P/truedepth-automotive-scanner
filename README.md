# TrueDepth Automotive 3D Scanner

Escáner de mano con iPhone TrueDepth y estación Windows para captura recuperable, limpieza, alineación, generación de mallas y exportación. La UI/UX toma EXStar como referencia principal.

## Estado

Inicio de implementación: documentación, inventario reproducible y primer análisis estático de EXStar con REA/Ghidra. Aún no hay app de captura ni motor de reconstrucción funcional. El desarrollo se mantiene inicialmente en el [repositorio privado de GitHub](https://github.com/Mati10P/truedepth-automotive-scanner); se hará público cuando esté listo. La selección de licencia open source está pendiente antes de esa publicación.

- [Contexto del proyecto](PROJECT_CONTEXT.md)
- [Plan completo](ROADMAP.md)
- [Primera etapa de ejecución](docs/implementation/START_HERE.md)
- [Viabilidad y flujo](docs/FEASIBILITY_AND_WORKFLOW.md)
- [Evaluación de MeshLab](docs/research/MESHLAB_EVALUATION.md)
- [Primera investigación con REA: pasos y evidencia](docs/research/REA_FIRST_PASS.md)
- [Seguimiento y pausa: funciones, condiciones y estados de EXStar](docs/research/EXSTAR_TRACKING_STATES.md)
- [Escaneo de objetos: solicitudes, poses y selección de frames](docs/research/EXSTAR_OBJECT_SCAN.md)
- [Adaptador de algoritmos: rutas de tracking, resultados y fallos](docs/research/EXSTAR_ALGORITHM_DISPATCH.md)
- [Motor de recuperación: candidatos, validación y separación de integración](docs/research/EXSTAR_RECOVERY_ENGINE.md)
- [Generación de candidatos: características, Hough y filtros geométricos](docs/research/EXSTAR_REGISTRATION_CANDIDATES.md)

## Inventario de EXStar

Requiere Python 3; solo usa la biblioteca estándar. Ejecutar desde esta carpeta, con una instalación propia de EXStar:

```powershell
python tools/inventory_exstar.py --source C:\Shining3d\EXStar --output .local/exstar-inventory.json
```

Lee ejecutables y DLL para calcular hashes y extrae nombres de temas/publicadores/suscriptores y asociaciones controlador/biblioteca de dos XML. No ejecuta EXStar ni exporta configuraciones completas. El archivo de salida debe ser nuevo y estar fuera de la instalación.

El desarrollo se publicará como open source con documentación reproducible. Las capturas de referencia y evidencias locales permanecen fuera de Git por ahora; los binarios de EXStar no forman parte del proyecto.
