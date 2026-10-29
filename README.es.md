# Intelligent Notification Service

[English](README.md)

Servicio FastAPI que convierte una petición en lenguaje natural ("Manda un email a ana@test.com diciendo hola") en una
notificación: un motor de IA extrae `{to, message, type}`, unos guardrails limpian y validan su respuesta y el
proveedor de notificaciones la envía. Solución al reto descrito en [CHALLENGE.md](CHALLENGE.md).

## Ejecutar

Requisitos: Docker. Desde la raíz del repositorio, exactamente como lo describe el reto:

```bash
docker-compose up -d provider influxdb grafana
docker-compose up -d --build app
docker-compose run --rm load-test
```

Scorecard: <http://localhost:3000/d/ia-performance-scorecard/>.

Desarrollo local (Python 3.12):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r app/requirements-dev.txt
.venv/Scripts/python -m pytest        # Windows; .venv/bin/python en Linux/macOS
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check app
```

La configuración se lee de variables de entorno; ver [.env.example](.env.example) y `app/config.py`.

## Estructura del repositorio

Los ficheros del reto se mantienen tal cual (`provider/`, `platform/`, `docker-compose.yaml`, `CHALLENGE.md`): el
revisor lanza la prueba de carga oficial sin cambios. La solución está en `app/`.
