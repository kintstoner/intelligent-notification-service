# 5. Pipeline en dos etapas con límite de ritmo en cliente para las notificaciones

[English](0005-two-stage-pipeline-and-client-side-rate-limit.md)

- Estado: aceptada
- Fecha: 2026-10-29

## Contexto

Leído en `provider/app.py`: `/v1/notify` acepta **50 llamadas en cualquier ventana deslizante de 10 segundos** (5 por
segundo) y responde 429 por encima; además puede devolver 500 (probabilidad 0 en el código, pero documentado). La
prueba de carga crea unas 70 peticiones por segundo de media. Entregarlo todo durante la prueba es imposible: el
sistema tiene que degradar con orden.

Si los workers de IA llamaran ellos mismos al proveedor, cada uno esperaría su turno: en pocos segundos todos
estarían bloqueados detrás del límite y la extracción se pararía.

## Opciones para el ritmo

1. Enviar lo más rápido posible y reintentar ante 429: se rechazan la mayoría de llamadas y los reintentos se
   acumulan.
2. Un token bucket que permite ráfagas: una ráfaga más 4,5/s constantes todavía puede pasar de 50 en una ventana
   deslizante.
3. Llamadas espaciadas de forma uniforme a un ritmo por debajo del límite, sin ráfagas.

## Decisión

- **Dos etapas**: los workers de IA convierten las peticiones en notificaciones validadas y las pasan a una cola de
  entrega; unos pocos workers de entrega (`NOTIFY_CONCURRENCY`, 10 por defecto) las envían. La entrega fija el estado
  final.
- **Ritmo (opción 3)**: cada intento de envío espera un hueco de un limitador que espacia las llamadas de forma
  uniforme a `NOTIFY_RATE_PER_S` (4,5/s por defecto): como mucho 46 llamadas en cualquier ventana de 10 s, por debajo
  de las 50 del proveedor.
- **Reintentos**: 429, 5xx y timeouts se reintentan con backoff exponencial y jitter completo (0,5 s, doblando), hasta
  `NOTIFY_MAX_ATTEMPTS` (3) intentos, cada uno pasando por el limitador. Se respeta `Retry-After` si el proveedor
  llegara a enviarlo. Los demás 4xx no se reintentan (`provider_rejected`); agotados los reintentos se termina en
  `rate_limited` o `provider_error`.
- **Backlog**: las notificaciones esperan su turno y se entregan en orden; ninguna se descarta por llegar tarde. La
  cola de entrega también está acotada (`delivery_backlog_full` por encima de `QUEUE_MAX_SIZE`).

## Consecuencias

- Se entregó toda notificación que pasó la validación (2.721). El proveedor respondió 429 a 5 de 2.726 llamadas, todas
  justo después de la prueba mientras los workers de IA vaciaban su backlog: el limitador espacia las llamadas cuando
  salen, y con esa carga en el event loop su llegada al proveedor varía lo suficiente como para que alguna ventana pase
  de 50. Los reintentos entregaron las 5; un ritmo menor da más margen.
- Tras una ráfaga, el backlog se vacía a 4,5/s: las ~2.200 notificaciones pendientes al acabar los 40 s de la prueba
  tardaron unos 8 minutos. Mientras tanto las peticiones aparecen como `processing`, y `/health` informa de los dos
  backlogs.
- Con varias instancias habría que compartir el límite (por ejemplo, un limitador sobre Redis), porque la cuota del
  proveedor es global.
- Para notificaciones que pierden su valor si llegan tarde (códigos de un solo uso), el siguiente paso sería una edad
  máxima por notificación.
