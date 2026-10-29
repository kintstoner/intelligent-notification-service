# 5. Pipeline en dos etapas con límite de ritmo en cliente para las notificaciones

[English](0005-two-stage-pipeline-and-client-side-rate-limit.md)

- Estado: aceptada (el ritmo se revisó el mismo día, ver "Historia")
- Fecha: 2026-10-29

## Contexto

Leído en `provider/app.py`: `/v1/notify` acepta **50 llamadas en cualquier ventana deslizante de 10 segundos** y
responde 429 por encima; además puede devolver 500 (probabilidad 0 en el código, pero documentado). La prueba de carga
crea unas 70 peticiones por segundo de media. Entregarlo todo durante la prueba es imposible: el sistema tiene que
degradar con orden.

Si los workers de IA llamaran ellos mismos al proveedor, cada uno esperaría su turno: en pocos segundos todos
estarían bloqueados detrás del límite y la extracción se pararía.

## Opciones para el ritmo

1. Enviar lo más rápido posible y reintentar ante 429: se rechazan la mayoría de llamadas y los reintentos se
   acumulan.
2. Espaciar las llamadas de forma uniforme a un ritmo por debajo del límite (una cada 0,22 s a 4,5/s).
3. Aplicar en nuestro lado la misma regla del proveedor: como mucho N llamadas en cualquier ventana deslizante de
   10 s, con N por debajo de 50.

## Decisión

- **Dos etapas**: los workers de IA convierten las peticiones en notificaciones validadas y las pasan a una cola de
  entrega; unos pocos workers de entrega (`NOTIFY_CONCURRENCY`, 10 por defecto) las envían. La entrega fija el estado
  final.
- **Ritmo (opción 3)**: cada intento de envío espera hueco en un limitador de ventana deslizante de
  `NOTIFY_WINDOW_MAX_CALLS` (45) llamadas cada `NOTIFY_WINDOW_S` (10 s). Mientras la ventana tiene hueco, la llamada
  sale al momento; cuando está llena, la siguiente espera a que la más antigua salga de la ventana. 45 en vez de 50
  deja margen para la variación entre que una llamada sale del servicio y llega al proveedor.
- **Reintentos**: 429, 5xx y timeouts se reintentan con backoff exponencial y jitter completo (0,5 s, doblando), hasta
  `NOTIFY_MAX_ATTEMPTS` (3) intentos, cada uno pasando por el limitador. Se respeta `Retry-After` si el proveedor
  llegara a enviarlo. Los demás 4xx no se reintentan (`provider_rejected`); agotados los reintentos se termina en
  `rate_limited` o `provider_error`.
- **Backlog**: las notificaciones esperan su turno y se entregan en orden; ninguna se descarta por llegar tarde. La
  cola de entrega también está acotada (`delivery_backlog_full` por encima de `QUEUE_MAX_SIZE`).

## Historia

La primera versión usaba la opción 2. Probándola a mano se vio su coste: 30 peticiones enviadas a la vez tenían una
mediana de 5,3 s y un máximo de 8,5 s hasta llegar a `sent`, casi todo esperando un hueco del espaciado uniforme,
aunque el proveedor habría aceptado las 30 de golpe. Con la ventana deslizante, las mismas 30 peticiones tienen una
mediana de 2,8 s, que es la latencia de la propia IA. Con carga sostenida las dos entregan al mismo ritmo medio.

## Consecuencias

- Prueba de carga oficial: se entregó toda notificación que pasó la validación (2.725), todas al primer intento y
  **sin ningún 429**. (Con la opción 2, una ejecución tuvo 5 respuestas 429, entregadas todas al reintentar.)
- Un servicio sin carga envía sin espera; una ráfaga de hasta 45 notificaciones sale de golpe.
- Tras una ráfaga larga, el backlog se vacía a 4,5/s de media: las ~2.300 notificaciones pendientes cuando la
  extracción se puso al día tardaron unos 9 minutos. Mientras tanto las peticiones aparecen como `processing`, y
  `/health` informa de los dos backlogs.
- Con varias instancias habría que compartir el límite (por ejemplo, un limitador sobre Redis), porque la cuota del
  proveedor es global.
- Para notificaciones que pierden su valor si llegan tarde (códigos de un solo uso), el siguiente paso sería una edad
  máxima por notificación.
