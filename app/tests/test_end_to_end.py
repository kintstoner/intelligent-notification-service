import time

import respx

from config import settings

CLEAN = '{"to": "juan@example.com", "message": "Tu paquete está en camino", "type": "email"}'


def wait_for_final_status(client, request_id, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/v1/requests/{request_id}").json()
        if body["status"] in ("sent", "failed"):
            return body
        time.sleep(0.02)
    raise AssertionError(f"request {request_id} did not finish: {body}")


def test_a_request_goes_from_intake_to_sent_through_the_real_pipeline(client):
    with respx.mock(base_url=settings.provider_base_url, assert_all_called=True) as provider:
        extract = provider.post("/v1/ai/extract").respond(
            json={"choices": [{"message": {"role": "assistant", "content": f"```json\n{CLEAN}\n```"}}]}
        )
        notify = provider.post("/v1/notify").respond(json={"status": "delivered", "provider_id": "p-1"})

        request_id = client.post("/v1/requests", json={"user_input": "Enviar email a juan@example.com"}).json()["id"]
        assert client.post(f"/v1/requests/{request_id}/process").status_code == 202

        assert wait_for_final_status(client, request_id) == {"id": request_id, "status": "sent"}
        assert extract.call_count == 1
        assert notify.call_count == 1


def test_a_request_without_destination_fails_with_a_reason(client):
    with respx.mock(base_url=settings.provider_base_url) as provider:
        provider.post("/v1/ai/extract").respond(
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I cannot process the request. I was unable to identify the both destination "
                            "and type in your prompt.",
                        }
                    }
                ]
            }
        )

        request_id = client.post("/v1/requests", json={"user_input": "manda un mensaje diciendo hola"}).json()["id"]
        client.post(f"/v1/requests/{request_id}/process")

        assert wait_for_final_status(client, request_id) == {
            "id": request_id,
            "status": "failed",
            "reason": "missing_information",
        }
