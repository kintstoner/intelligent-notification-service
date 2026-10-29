# 4. Como mucho un reintento de IA, y solo cuando puede ayudar

[English](0004-at-most-one-ai-retry.md)

- Estado: aceptada
- Fecha: 2026-10-29

## Contexto

El scorecard divide las llamadas a la IA entre las llamadas a `/process`: verde por debajo de 1,5, rojo desde 2,5.
Reintentar hasta que el modelo devuelva JSON limpio subiría ese ratio, y no hace falta: los guardrails reparan el JSON
sucio (ADR 3). Algunos fallos sí merecen otra llamada: un rechazo de política (aleatorio en el mock), un error de red,
una respuesta sin mensaje.

## Decisión

Como mucho `1 + AI_MAX_RETRIES` llamadas por petición (2 por defecto). Solo se hace una segunda llamada en estos casos:

| Primera llamada | ¿Reintento? | Motivo si vuelve a fallar |
|---|---|---|
| Timeout, error de transporte, 5xx | Sí | `ai_unavailable` |
| Rechazo de política (sin JSON) | Sí | `ai_refused` |
| Objeto que no se puede leer ni con las reparaciones | Sí | `ai_output_unreadable` |
| Objeto válido sin mensaje | Sí | `missing_message` |
| "Unable to identify the destination/type" | No: la misma entrada da la misma respuesta | `missing_information` |
| 4xx del motor de IA (clave mala), respuesta sin choices | No | `ai_unavailable` |
| El destinatario no cuadra con el canal tras el fallback | No | `invalid_notification` |
| JSON sucio (bloques, claves renombradas, comillas simples...) | Nunca: lo arreglan los guardrails | |

## Consecuencias

- Ratio medido en la prueba de carga oficial: **1,10** (3.021 llamadas a la IA para 2.749 llamadas a `/process`).
- Alrededor del 10 % de las respuestas son rechazos; un reintento convierte la mayoría en notificaciones enviadas.
- Los rechazos se distinguen por su texto, que es una heurística: un texto de "falta información" poco habitual se
  reintentaría una vez, gastando una llamada.
