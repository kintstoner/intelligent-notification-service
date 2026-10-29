# Intelligent Notification Service

[Español](README.es.md)

FastAPI service that turns a natural-language request ("Send an email to ana@test.com saying hello") into a
notification: an AI engine extracts `{to, message, type}`, guardrails clean and validate its answer, and the
notification provider sends it. Solution to the challenge described in [CHALLENGE.md](CHALLENGE.md).

## Run

Requirements: Docker. From the repository root, exactly as the challenge describes:

```bash
docker-compose up -d provider influxdb grafana
docker-compose up -d --build app
docker-compose run --rm load-test
```

Scorecard: <http://localhost:3000/d/ia-performance-scorecard/>.

Local development (Python 3.12):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r app/requirements-dev.txt
.venv/Scripts/python -m pytest        # Windows; .venv/bin/python on Linux/macOS
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check app
```

Configuration is read from environment variables; see [.env.example](.env.example) and `app/config.py`.

## Repository layout

The challenge files are kept as provided (`provider/`, `platform/`, `docker-compose.yaml`, `CHALLENGE.md`): the
reviewer runs the official load test unchanged. The solution lives in `app/`.
