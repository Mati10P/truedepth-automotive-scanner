# Primer ensayo físico RGB-D — 2026-10-16, Uruguay

App v3 instalada por el usuario. Serie UTC `captures/sequence-20261017T005404Z-70401517/`, iniciada a las 21:54 del 16 de octubre en Uruguay. Se recibieron **10 pares únicos en 10,005 s**, una conexión TD3, cero errores, duplicados o reconexiones. La solicitud completa promedió 169,6 ms; máximo 303,8 ms. La preparación iOS promedió 39,3 ms. Es un ensayo de 1 solicitud/s, no prueba de frecuencia máxima o continuidad prolongada.

## Integridad y sincronización verificadas

Los 10 pares contienen RGB PNG 640 × 480 y depth float32 640 × 480, ambos sin redimensionar. Se volvieron a verificar los 20 checksums, timestamps y coincidencia de IDs, y se decodificaron los 10 PNG con Pillow. La diferencia entre timestamps de ambos canales es exactamente cero en los 10 pares. El contador acumulado de pares rechazados permanece en 9 desde el primer al último frame: hubo rechazos antes de esta serie, no aumentó durante el intervalo muestreado.

Metadatos efectivos: rotación 0°, espejo false y estabilización raw 0 en ambas conexiones; zoom 1, formato activo RGB y depth 640 × 480, depth sin filtrado. Calibración original con dimensiones de referencia 4032 × 3024, ambas LUT de 42 valores. Primer frame: fx=fy=431,4895 px escalados, cx=318,5683, cy=241,0944.

La imagen RGB muestra caja, herraje, escuadra transparente y apoyo sobre papel. La superposición directa con depth coincide visualmente en estructuras principales sin un giro o espejo grueso, pero conserva bandas sin profundidad y diferencias de borde. **No constituye validación cuantitativa de alineación subpíxel**, ni justifica tratar la escuadra transparente como referencia de profundidad. Se preservan las dos imágenes originales.

## Primera selección informada por RGB

Esquinas leídas manualmente del RGB del primer par, en píxeles nativos: A=(213,172), B=(415,162), C=(418,310), D=(223,323). Son marcas provisionales del asistente, no confirmadas por el usuario. ROI de madera inferior, alejada del herraje: [(237,253),(394,244),(397,294),(239,305)]. Las marcas se transfieren por coordenada a depth como hipótesis explícita de correspondencia, dado el formato y orientación coincidentes, pendiente de validar.

Se ajustó el plano interior robusto y se intersectaron los rayos de las cuatro marcas. Esta vez el alto **no usa la intersección con un plano de mesa**: sus extremos se identifican visualmente en RGB, aunque su profundidad sigue inferida por el plano. No se debe afirmar que se midieron directamente las esquinas con depth.

| Longitud | Mediana de 10 pares, LUT inversa diagnóstica | Referencia física previa |
|---|---:|---:|
| Ancho superior AB | 17,73 cm | 18,4 cm |
| Ancho inferior DC | 18,30 cm | 18,4 cm |
| Alto izquierdo AD | 13,78 cm | 14,0 cm |
| Alto derecho BC | 13,81 cm | 14,0 cm |

Todos los ajustes convergieron; RMS mediano de puntos aceptados 2,21 mm. No es precisión dimensional. Las marcas permanecen fijas en toda la serie; la variación temporal no incluye incertidumbre al seleccionar esquinas ni error de registro RGB-depth. No se reconfirmó físicamente la distancia en este turno: la última distancia declarada de 40 cm se conserva como antecedente, no medición nueva.

En el primer frame, pinhole da ancho superior/inferior 17,97/18,51 cm y altos ~13,95 cm; LUT inversa da 17,76/18,29 y ~13,79 cm; LUT directa de control da 18,18/18,73 y ~14,12 cm. No elegir la proyección que más se acerca a la referencia. La discrepancia de ~5,6 mm entre ancho superior e inferior en el análisis de serie persiste y requiere revisar registro, marcas y planitud antes de aceptar precisión o corregir escala.

## Evidencia y siguiente verificación

En la serie: `pair_integrity.json`, `summary.json`, `integrity_check.json`, `rgb_corner_selection.json`, `rgb_corner_audit.json`, `rgb_corner_series.json`, `rgbd-correspondence.png`, `frame-000001/pair-review.html` y los diez pares originales. Scripts auxiliares locales: `.local/verify_first_rgbd.py`, `.local/analyze_first_rgbd_series.py`. Ningún original se sube a GitHub.

El flujo físico RGB-D queda comprobado para esta serie corta. El siguiente trabajo geométrico es cuantificar la correspondencia de bordes RGB-depth y la sensibilidad de las marcas sobre estos originales. No continuar acumulando distancias ni corregir escala por el aparente acierto de una altura. REA/ICP permanece en pausa.
