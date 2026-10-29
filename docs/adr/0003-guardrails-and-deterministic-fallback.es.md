# 3. Guardrails y fallback determinista; el mensaje nunca se inventa

[English](0003-guardrails-and-deterministic-fallback.md)

- Estado: aceptada
- Fecha: 2026-10-29

## Contexto

Leído en `provider/responses.py`: la mitad de las respuestas de la IA son JSON limpio. El resto traen claves
renombradas (`Recipient/body/channel`, `To/Message/Type`, `destination/text/method`), campos extra, falta `type` o
`to`, bloques Markdown, JSON dentro de una frase, salida cortada, comillas simples, claves sin comillas o un rechazo
en texto plano.

## Decisión

Tres pasos, cada uno un conjunto de funciones puras:

1. **Guardrails** ([`guardrails.py`](../../app/services/guardrails.py)): quitar los bloques ```` ``` ````; localizar el
   primer `{...}` balanceado, saltando las llaves dentro de strings; leerlo con `json.loads`, después con
   `ast.literal_eval` (comillas simples, también con apóstrofos dentro de los valores) y después poniendo comillas a
   las claves; cerrar un objeto cortado tras su último valor; mapear sinónimos de claves sin distinguir mayúsculas y
   descartar las desconocidas; normalizar el tipo (`mail`, `correo` → email; `phone` → sms). Sin ningún JSON es un
   rechazo, clasificado como *de política* o *falta información*.
2. **Fallback** ([`fallback_extractor.py`](../../app/services/fallback_extractor.py)): si faltan destinatario o canal,
   se recuperan de la petición original con expresiones regulares (primer email, si no primer teléfono; canal según la
   forma del destinatario y después por palabras clave).
3. **Validación** (`Notification`, Pydantic): el destinatario tiene que cuadrar con el canal (un email para email, un
   teléfono para SMS) y el mensaje no puede estar vacío; los teléfonos se envían como dígitos.

El fallback nunca rellena el mensaje. Si la IA no da mensaje, la petición se reintenta una vez (ADR 4) y después falla
con `missing_message`.

## Consecuencias

- Se cubren las 16 formas de respuesta del mock; los tests ejecutan el propio generador del proveedor por cada rama,
  así que siguen el código del mock y no una copia.
- Enviar una notificación con contenido inventado es peor que no enviarla, así que algunas peticiones fallan a
  propósito, con su motivo.
- La reparación de claves sin comillas es una expresión regular que solo se aplica si falla la lectura estricta; un
  mensaje que contuviera `, palabra:` podría, en teoría, alterarse.
