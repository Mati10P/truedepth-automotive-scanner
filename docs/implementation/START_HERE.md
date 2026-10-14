# Primera etapa de ejecución

Fecha: 2026-10-14. Complementa el roadmap aprobado; conserva sus fases y requisitos.

## Primer paso: especificación basada en evidencia de EXStar

Resultado buscado: una matriz de pantallas, acciones y estados, vinculada a evidencia, que permita implementar nuestra experiencia de escaneo sin adivinar el comportamiento del producto de referencia.

1. Conservar una línea base reproducible de la instalación original y mapear los temas de comunicación declarados por EXStar.
2. Recorrer las funciones disponibles en la copia UI Lab, registrar navegación, herramientas, estados habilitados/deshabilitados y comportamiento de aplicar/cancelar. Usar las referencias visuales para funciones inaccesibles sin escáner y marcarlas como pendientes de observación directa.
3. Preparar REA y dirigir el análisis a preguntas concretas: pausa/reanudación, pérdida de tracking, generación de nube, organización de proyectos, alineación y trabajos de malla. Los nombres de DLL y temas son pistas, no prueba de algoritmos internos.
4. Documentar hallazgos y decisiones en archivos versionables; revisar el plan ante evidencia nueva.

La inspección inicial del arranque se realizó con análisis estático y observación de la UI. No se ha ejecutado todavía una sesión con REA; no hay herramienta REA/Ghidra expuesta en esta sesión.

## Base del repositorio

- README y script de inventario reproducible.
- Evidencia local separada mediante `.gitignore`.
- Repositorio inicial privado: [Mati10P/truedepth-automotive-scanner](https://github.com/Mati10P/truedepth-automotive-scanner). La carpeta local se vincula a ese remoto para conservar el historial desde el inicio.
- Pendiente: elegir licencia compatible con las dependencias definitivas, hacerlo público cuando esté listo y trasladar entregables a issues/hitos de GitHub. La sincronización inicial utiliza Git y la autenticación disponible; `gh` no está disponible en PATH.

## Primer hito funcional del producto: fase 0

Una app mínima instalada en el iPhone 16e que detecte los formatos TrueDepth disponibles y entregue datos de prueba a Windows. Validar también start/pause con botones y el circuito de compilación, firma y actualización.

La primera demostración verificable es ver en la PC un frame real de profundidad recibido del iPhone, con dimensiones, timestamp y calibración. Después: ensayo continuo de 10 minutos y comparación Wi-Fi/USB según el roadmap. Este hito permite medir el sensor antes de comprometer el motor de reconstrucción.

Para completarlo físicamente se necesita acceso al iPhone, conocer su versión de iOS y completar la firma/instalación con la cuenta del usuario. La preparación local y la especificación pueden avanzar antes.

## Cierre de esta etapa de investigación

- Inventario repetible de binarios y comunicación declarada.
- Matriz de UI con origen y nivel de certeza por observación.
- Lista de decisiones implementables y preguntas pendientes.
- Tarea concreta para la app iOS y receptor Windows.

Las funciones de posprocesamiento de PyMeshLab se evaluarán sobre datos reales en las fases 4–5; su adopción sigue condicionada a las pruebas documentadas.
