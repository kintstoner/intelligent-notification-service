# 6. Caché de extracciones disponible pero desactivada por defecto

[English](0006-extraction-cache-off-by-default.md)

- Estado: aceptada
- Fecha: 2026-10-29

## Contexto

La prueba de carga repite cuatro frases. Cachear las extracciones por `user_input` idéntico dejaría el ratio de
llamadas a la IA cerca de cero, lo que no dice nada de cómo se comporta el servicio con un modelo real y se leería como
hacer trampa con el scorecard.

## Decisión

La caché existe detrás de `EXTRACTION_CACHE_ENABLED`, `false` por defecto. Activada, una extracción correcta se
reutiliza para un texto de petición idéntico; los fallos nunca se cachean.

## Consecuencias

- El scorecard muestra el coste real de la extracción (ratio 1,10).
- En producción tiene sentido como deduplicación: la misma petición enviada dos veces (un cliente que reintenta, un
  doble clic) no debería pagar una segunda extracción. Entonces necesitaría un límite de tamaño y un TTL; el dict
  actual no tiene límite y vive en memoria.
