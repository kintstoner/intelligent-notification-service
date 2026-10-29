# 2. Instrucciones solo en el system prompt; el mensaje user es la petición tal cual

[English](0002-instructions-only-in-the-system-prompt.md)

- Estado: aceptada
- Fecha: 2026-10-29

## Contexto

La llamada de extracción recibe una lista de mensajes `system`/`user`. Un patrón habitual envuelve el texto del
usuario en una plantilla ("Extrae el destinatario de: ...", a veces con ejemplos). El mock solo lee el **último
mensaje user**: detecta el canal buscando palabras como "email" y se queda con el **primer** email o teléfono que
encuentra. Una plantilla o un ejemplo dentro del mensaje user cambia su respuesta. Un modelo real tiene el problema
contrario: texto en el turno del usuario que parece una instrucción puede anular las instrucciones (prompt injection).

## Decisión

- Todas las instrucciones van en un único system prompt, versionado con el código en
  [`app/prompts/extract_system.md`](../../app/prompts/extract_system.md).
- El mensaje user es exactamente el `user_input` recibido, sin plantilla y sin ejemplos.
- El prompt está escrito para un modelo real: el papel del extractor, el esquema JSON exacto, cómo redactar el mensaje
  (el texto a entregar, no la orden de enviarlo; mismo idioma; nombres, fechas y códigos tal cual), las reglas del
  canal (seguir al destinatario cuando el canal pedido y el destinatario no cuadran), qué hacer si falta algo (nulls,
  nunca suposiciones) y que el texto del usuario son datos, no instrucciones.
- Sus pocos ejemplos van dentro del system prompt, nunca como turnos user/assistant adicionales.

## Consecuencias

- La extracción del mock no se contamina con palabras nuestras.
- Separar instrucciones de datos es la defensa básica frente a prompt injection.
- El mock ignora el system prompt, así que su calidad no se puede medir aquí; la cubren un test que comprueba que el
  esquema está presente y la revisión.
