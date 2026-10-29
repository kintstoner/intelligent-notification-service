def create(client, user_input="Enviar email a juan@example.com diciendo hola"):
    return client.post("/v1/requests", json={"user_input": user_input})


def test_create_returns_201_with_an_id(client):
    response = create(client)

    assert response.status_code == 201
    assert isinstance(response.json()["id"], str)


def test_each_request_gets_its_own_id(client):
    assert create(client).json()["id"] != create(client).json()["id"]


def test_a_new_request_is_queued(client):
    request_id = create(client).json()["id"]

    response = client.get(f"/v1/requests/{request_id}")

    assert response.status_code == 200
    assert response.json() == {"id": request_id, "status": "queued"}


def test_unknown_request_is_404(client):
    assert client.get("/v1/requests/does-not-exist").status_code == 404


def test_create_without_user_input_is_422(client):
    assert client.post("/v1/requests", json={}).status_code == 422


def test_create_with_blank_user_input_is_422(client):
    assert create(client, "   ").status_code == 422


def wait_for_status(client, request_id, expected, timeout=2.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/v1/requests/{request_id}").json()
        if body["status"] == expected:
            return body
        time.sleep(0.01)
    raise AssertionError(f"request {request_id} never reached {expected}: {body}")


def test_process_without_body_returns_202_and_the_request_gets_processed(client, handler_calls):
    request_id = create(client).json()["id"]

    response = client.post(f"/v1/requests/{request_id}/process")

    assert response.status_code == 202
    assert response.json()["id"] == request_id
    wait_for_status(client, request_id, "sent")
    assert handler_calls == [request_id]


def test_processing_twice_enqueues_the_request_once(client, handler_calls):
    request_id = create(client).json()["id"]

    client.post(f"/v1/requests/{request_id}/process")
    wait_for_status(client, request_id, "sent")
    second = client.post(f"/v1/requests/{request_id}/process")

    assert second.status_code == 202
    assert second.json() == {"id": request_id, "status": "sent"}
    assert handler_calls == [request_id]


def test_process_unknown_request_is_404(client):
    assert client.post("/v1/requests/does-not-exist/process").status_code == 404


def test_a_full_queue_still_answers_202_and_leaves_the_request_queued(client, full_queue):
    request_id = create(client).json()["id"]

    response = client.post(f"/v1/requests/{request_id}/process")

    assert response.status_code == 202
    assert client.get(f"/v1/requests/{request_id}").json() == {
        "id": request_id,
        "status": "queued",
        "reason": "queue_full",
    }


def test_endpoints_run_on_the_event_loop():
    """
    Sync endpoints run in a thread pool: they would touch the asyncio queues and the lock-free repository from another
    thread. Every endpoint must be async.
    """
    import inspect

    from fastapi.routing import APIRoute

    from main import app

    sync_endpoints = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute) and not inspect.iscoroutinefunction(route.endpoint)
    ]

    assert sync_endpoints == []
