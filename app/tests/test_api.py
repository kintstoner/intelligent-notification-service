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
