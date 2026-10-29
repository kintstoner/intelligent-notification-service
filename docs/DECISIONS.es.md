# Decisiones de diseño

[English](DECISIONS.md)

Una línea por decisión; el razonamiento completo está en cada Architecture Decision Record.

| # | Decisión | Por qué, en una línea |
|---|---|---|
| [1](adr/0001-accept-and-process-in-background.es.md) | `/process` encola y responde 202; el trabajo lo hacen workers asyncio; una cola llena nunca es un error | La IA tarda segundos; quien llama no debe esperarla ni ver la saturación interna |
| [2](adr/0002-instructions-only-in-the-system-prompt.es.md) | Instrucciones solo en un system prompt versionado; el mensaje user es la petición cruda | Nuestras palabras contaminarían la extracción del mock, y mezclar instrucciones con datos facilita el prompt injection |
| [3](adr/0003-guardrails-and-deterministic-fallback.es.md) | Los guardrails reparan la salida de la IA; un fallback con regex recupera destinatario y canal; el mensaje nunca se inventa | Toda respuesta ruidosa se aprovecha sin otra llamada y no se envía nada que nadie haya escrito |
| [4](adr/0004-at-most-one-ai-retry.es.md) | Como mucho un reintento de IA, solo por rechazos, respuestas cortadas, falta de mensaje o errores de red | El JSON sucio se arregla, no se reintenta; ratio 1,10 |
| [5](adr/0005-two-stage-pipeline-and-client-side-rate-limit.es.md) | La entrega es una segunda cola a 4,5/s, espaciada de forma uniforme, con reintentos acotados | El proveedor admite 50 cada 10 s; los workers de IA nunca esperan detrás de ese límite y los 429 son raros (5 de 2.726) y se reintentan |
| [6](adr/0006-extraction-cache-off-by-default.es.md) | Caché de extracciones tras un flag, desactivada | Con cuatro frases repetidas ocultaría el coste real de la extracción |
| [7](adr/0007-in-memory-state-behind-an-interface.es.md) | Estado en memoria detrás de un protocolo de repositorio | Un proceso y sin base de datos en el reto; un almacén compartido encaja detrás del mismo protocolo |
