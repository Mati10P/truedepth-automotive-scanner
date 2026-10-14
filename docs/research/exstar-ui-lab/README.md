# EXStar: copia para explorar la interfaz

Fecha: 2026-10-14. Versión instalada: 1.2.2.0.

## Resultado

La copia abrió la interfaz principal sin el bloqueo inicial por NVIDIA. Se verificó visualmente la pantalla Offline y el diálogo oficial de Modo Invitado. Ese diálogo informa que permite importar proyectos EINSTAR y editar mallas, y que calibrar/escanear requiere el equipo y activación. No se probaron operaciones de malla ni cálculo CUDA. No se operó el diálogo de cuenta automáticamente.

## Cómo abrir

- Acceso directo del escritorio: `C:\Users\matip\Desktop\EXStar - UI Lab.lnk`.
- Ejecutable: `C:\Shining3d\EXStar-UI-Lab\EXStar.exe`.
- Carpeta de trabajo: `C:\Shining3d\EXStar-UI-Lab`.
- En la pantalla de cuenta, el usuario puede seleccionar el Modo Invitado oficial.

## Cambio aislado

Se copió la instalación completa, verificando los hashes antes de modificar la copia. En `PrestartCheck.dll`, offset de archivo `0x2824`, se cambió `85 DB` (`test ebx, ebx`) a `31 DB` (`xor ebx, ebx`). Esto toma la rama de éxito existente de la respuesta del chequeo CUDA y evita su mensaje seguido de cierre. Es un cambio de un byte; no emula CUDA ni sustituye el escáner. Los controles de cuenta/activación no se modificaron.

El original de la DLL de prueba está en `C:\Shining3d\EXStar-UI-Lab\_patch_backup\PrestartCheck.dll`. Con la aplicación y sus procesos cerrados, restaurar esa DLL en la raíz de la copia revierte el parche.

## Fidelidad del análisis

Usar `C:\Shining3d\EXStar` para análisis estático y comportamiento original; etiquetar las observaciones de esta copia como UI Lab. Ninguno de los 1894 archivos originales de la línea base cambió, verificado después de abrir la aplicación. El primer intento del lanzador resolvió la instalación original y produjo logs nuevos; estos están enumerados en `verification.json` y no forman parte de la línea base.

- `original-sha256.json`: hashes de la instalación antes de las pruebas.
- `patch-manifest.json`: hashes de la DLL original/modificada, offset y propósito.
- `verification.json`: comparación posterior del original.

Estos tres archivos JSON son evidencia local excluida de Git; no se incluyen en un clon del repositorio. El script `tools/inventory_exstar.py`, ubicado en la raíz del proyecto, permite generar un nuevo inventario de una instalación propia.

El aislamiento es de archivos de instalación, no una máquina virtual: el programa puede usar servicios, registro y datos de usuario compartidos. Saltar el arranque no garantiza estabilidad de las funciones que dependan de CUDA.
