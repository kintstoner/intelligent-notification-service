import importlib.util
from pathlib import Path

import pytest

from services.guardrails import AIRefusal, Extraction, MalformedOutput, RefusalKind, parse_ai_output


def load_provider_responses():
    """The mock's own response generator, so the tests follow the provider's code rather than a copy of it."""
    path = Path(__file__).parents[2] / "provider" / "responses.py"
    spec = importlib.util.spec_from_file_location("provider_responses", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provider = load_provider_responses()

# (dice, sub_dice) pairs that select every branch of generate_ai_response
CLEAN = [(0.10, 0.0)]
RENAMED_KEYS = [(0.55, 0.10), (0.55, 0.50), (0.55, 0.90)]
EXTRA_FIELDS = [(0.65, 0.10)]
MISSING_TYPE = [(0.65, 0.50)]
MISSING_TO = [(0.65, 0.90)]
WRAPPED = [(0.75, 0.10), (0.75, 0.50), (0.75, 0.90)]
MALFORMED = [(0.85, 0.10), (0.85, 0.50), (0.85, 0.90)]
REFUSED = [(0.95, 0.10), (0.95, 0.50), (0.95, 0.90)]

CASES = [
    ("juan@example.com", "su paquete está en camino", "email"),
    ("600-111-222", "la reserva ha sido confirmada", "sms"),
]


def mock_output(monkeypatch, dice, sub_dice, target, msg, notif_type):
    values = iter([dice, sub_dice])
    monkeypatch.setattr(provider.random, "random", lambda: next(values))
    return provider.generate_ai_response(target, msg, notif_type)


@pytest.mark.parametrize(("target", "msg", "notif_type"), CASES)
@pytest.mark.parametrize(("dice", "sub_dice"), CLEAN + RENAMED_KEYS + EXTRA_FIELDS + WRAPPED + MALFORMED)
def test_recovers_the_full_extraction_from_every_parseable_variant(
    monkeypatch, dice, sub_dice, target, msg, notif_type
):
    output = mock_output(monkeypatch, dice, sub_dice, target, msg, notif_type)

    assert parse_ai_output(output) == Extraction(to=target, message=msg, type=notif_type)


@pytest.mark.parametrize(("dice", "sub_dice"), MISSING_TYPE)
def test_a_missing_type_is_left_empty_for_the_fallback(monkeypatch, dice, sub_dice):
    output = mock_output(monkeypatch, dice, sub_dice, "juan@example.com", "hola", "email")

    assert parse_ai_output(output) == Extraction(to="juan@example.com", message="hola", type=None)


@pytest.mark.parametrize(("dice", "sub_dice"), MISSING_TO)
def test_a_missing_destination_is_left_empty_for_the_fallback(monkeypatch, dice, sub_dice):
    output = mock_output(monkeypatch, dice, sub_dice, "juan@example.com", "hola", "email")

    assert parse_ai_output(output) == Extraction(to=None, message="hola", type="email")


@pytest.mark.parametrize(("dice", "sub_dice"), REFUSED)
def test_a_policy_refusal_is_reported_as_such(monkeypatch, dice, sub_dice):
    output = mock_output(monkeypatch, dice, sub_dice, "juan@example.com", "hola", "email")

    with pytest.raises(AIRefusal) as refusal:
        parse_ai_output(output)
    assert refusal.value.kind == RefusalKind.POLICY


def test_the_provider_saying_information_is_missing_is_not_a_policy_refusal():
    output = "I cannot process the request. I was unable to identify the destination (email/phone) in your prompt."

    with pytest.raises(AIRefusal) as refusal:
        parse_ai_output(output)
    assert refusal.value.kind == RefusalKind.MISSING_INFORMATION


def test_braces_and_quotes_inside_the_message_do_not_confuse_the_object_search():
    output = 'Aquí está: {"to": "a@b.com", "message": "Usa el código {X-1} y \\"guárdalo\\"", "type": "email"} ¡Listo!'

    assert parse_ai_output(output) == Extraction(to="a@b.com", message='Usa el código {X-1} y "guárdalo"', type="email")


def test_a_json_null_from_the_model_means_missing():
    assert parse_ai_output('{"to": null, "message": "hola", "type": "sms"}') == Extraction(None, "hola", "sms")


def test_a_numeric_phone_number_is_kept_as_text():
    assert parse_ai_output('{"to": 600111222, "message": "hola", "type": "sms"}').to == "600111222"


@pytest.mark.parametrize(
    ("raw_type", "expected"),
    [("EMAIL", "email"), ("mail", "email"), ("correo", "email"), ("SMS", "sms"), ("phone", "sms"), ("whatsapp", None)],
)
def test_type_synonyms_are_normalised(raw_type, expected):
    assert parse_ai_output(f'{{"to": "a@b.com", "message": "hola", "type": "{raw_type}"}}').type == expected


def test_output_cut_inside_a_value_cannot_be_repaired():
    with pytest.raises(MalformedOutput):
        parse_ai_output('{"to": "a@b.com", "message": "tu paq')


def test_an_object_that_is_not_json_even_after_repairs_is_malformed():
    with pytest.raises(MalformedOutput):
        parse_ai_output('{"to" "a@b.com" "message"}')
