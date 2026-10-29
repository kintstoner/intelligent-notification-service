# 1. Aceptar con 202 y procesar en workers en segundo plano

[English](0001-accept-and-process-in-background.md)

- Estado: aceptada
- Fecha: 2026-10-29

## Contexto

Procesar una petición supone una o dos llamadas a la IA de 1,5 a 3 s cada una y después una llamada de notificación.
El scorecard pide una latencia media de `/process` por debajo de 400 ms y cuenta como indisponibilidad cualquier
4xx/5xx devuelto a k6. Con carga, k6 llega a enviar ~130 llamadas a `/process` por segundo.

## Opciones

1. Procesar dentro de la petición HTTP: `/process` tarda segundos, y más con carga.
2. Aceptar la petición, meterla en una cola y procesarla en workers en segundo plano.

## Decisión

Opción 2. `/process` comprueba que la petición existe, la encola y responde `202 Accepted` con su estado actual. Un
número fijo de workers asyncio (`WORKERS`, 100 por defecto) vacían la cola; arrancan y paran con el lifespan de la
aplicación.

- Idempotente: una petición ya encolada, en proceso o terminada no se vuelve a encolar; la llamada solo devuelve su
  estado. Un id desconocido es un 404 (error del cliente, no saturación).
- La cola está acotada (`QUEUE_MAX_SIZE`, 10.000 por defecto) para proteger la memoria. Si está llena, `/process`
  sigue respondiendo 202, la petición se queda `queued` con `reason: queue_full` y volver a llamar a `/process` la
  reintenta. La saturación interna nunca se convierte en un error para quien llama.
- Un fallo inesperado al procesar una petición la marca `failed` con `reason: internal_error`; el worker sigue.

## Consecuencias

- `/process` responde en menos de un milisegundo hagan lo que hagan la IA o el proveedor (media en k6: 0,62 ms).
- Todos los endpoints son `async`: uno síncrono se ejecutaría en el pool de hilos de FastAPI y tocaría las colas de
  asyncio desde otro hilo.
- El endpoint de estado es como se conoce el resultado; `reason` (campo extra y opcional) dice por qué una petición
  falló o sigue esperando.
- El estado vive en memoria: ver ADR 7.
