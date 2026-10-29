import json

import httpx
import pytest
import respx

from services.extractor import SYSTEM_PROMPT, ExtractionError, Extractor

BASE_URL = "http://provider.test"
USER_INPUT = "Enviar email a juan@example.com diciendo que su paquete está en camino."


def completion(content: str) -> dict:
    return {"choices": [{"index": 0, "message": {"role": "assistant", "content": content}}]}


@pytest.fixture
async def extractor():
    async with httpx.AsyncClient(base_url=BASE_URL, headers={"X-API-Key": "key"}) as client:
        yield Extractor(client, timeout_s=1.0)


@respx.mock
async def test_returns_the_assistant_content(extractor):
    respx.post(f"{BASE_URL}/v1/ai/extract").respond(json=completion('{"to": "a@b.com"}'))

    assert await extractor.extract(USER_INPUT) == '{"to": "a@b.com"}'


@respx.mock
async def test_sends_instructions_as_system_and_the_raw_user_input_as_the_only_user_message(extractor):
    route = respx.post(f"{BASE_URL}/v1/ai/extract").respond(json=completion("{}"))

    await extractor.extract(USER_INPUT)

    sent = route.calls.last.request
    assert sent.headers["X-API-Key"] == "key"
    assert json.loads(sent.content)["messages"] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_INPUT},
    ]


def test_the_system_prompt_defines_the_output_schema():
    for key in ('"to"', '"message"', '"type"', '"email"', '"sms"'):
        assert key in SYSTEM_PROMPT


@respx.mock
async def test_a_timeout_is_a_retryable_error(extractor):
    respx.post(f"{BASE_URL}/v1/ai/extract").mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(ExtractionError) as error:
        await extractor.extract(USER_INPUT)
    assert error.value.retryable is True


@respx.mock
async def test_a_server_error_is_retryable(extractor):
    respx.post(f"{BASE_URL}/v1/ai/extract").respond(500)

    with pytest.raises(ExtractionError) as error:
        await extractor.extract(USER_INPUT)
    assert error.value.retryable is True


@respx.mock
async def test_a_rejected_api_key_is_not_retryable(extractor):
    respx.post(f"{BASE_URL}/v1/ai/extract").respond(403)

    with pytest.raises(ExtractionError) as error:
        await extractor.extract(USER_INPUT)
    assert error.value.retryable is False


@respx.mock
async def test_a_response_without_choices_is_not_retryable(extractor):
    respx.post(f"{BASE_URL}/v1/ai/extract").respond(json={"error": "nope"})

    with pytest.raises(ExtractionError) as error:
        await extractor.extract(USER_INPUT)
    assert error.value.retryable is False


@respx.mock
async def test_a_null_content_is_an_empty_answer(extractor):
    respx.post(f"{BASE_URL}/v1/ai/extract").respond(
        json={"choices": [{"message": {"role": "assistant", "content": None}}]}
    )

    assert await extractor.extract(USER_INPUT) == ""
