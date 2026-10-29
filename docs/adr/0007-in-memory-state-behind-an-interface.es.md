# 7. Estado en memoria detrás de una interfaz de repositorio

[English](0007-in-memory-state-behind-an-interface.md)

- Estado: aceptada
- Fecha: 2026-10-29

## Contexto

El reto ejecuta un único contenedor con el Dockerfile dado (`uvicorn main:app`, un proceso) y sin base de datos.

## Decisión

Las peticiones se guardan en un dict detrás de un protocolo `RequestRepository`. Sin lock: todos los accesos ocurren
en el único event loop y ninguno hace `await`, así que un lock sería código muerto. Las colas son `asyncio.Queue` en el
mismo proceso.

## Consecuencias

- Sencillo y rápido; no hay nada que instalar.
- Un reinicio pierde las peticiones, también las encoladas o pendientes de entrega. Con varios workers de uvicorn cada
  uno tendría su propio estado.
- El siguiente paso para producción: un almacén compartido (Postgres o Redis) que implemente el mismo protocolo y una
  cola duradera (Redis streams, SQS, Kafka) en lugar de las colas en proceso. Los pasos del procesamiento no
  cambiarían.
