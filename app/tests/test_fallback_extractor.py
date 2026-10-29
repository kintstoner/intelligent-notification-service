import pytest

from services.fallback_extractor import complete
from services.guardrails import Extraction

K6_PROMPTS = [
    ("Enviar email a juan@example.com diciendo que su paquete está en camino.", "juan@example.com", "email"),
    ("Avisar por SMS al 600-111-222 que la reserva ha sido confirmada.", "600111222", "sms"),
    ("Manda un correo a marta@app.com: Tienes un nuevo mensaje.", "marta@app.com", "email"),
    ("Recordatorio por teléfono al 699888777: cita a las 10:00", "699888777", "sms"),
]


@pytest.mark.parametrize(("user_input", "to", "notification_type"), K6_PROMPTS)
def test_recovers_destination_and_type_from_the_request_when_the_ai_left_them_out(user_input, to, notification_type):
    completed = complete(Extraction(to=None, message="hola", type=None), user_input)

    assert completed == Extraction(to=to, message="hola", type=notification_type)


def test_never_makes_up_a_message():
    completed = complete(Extraction(to=None, message=None, type=None), K6_PROMPTS[0][0])

    assert completed.message is None


def test_keeps_what_the_ai_extracted():
    extraction = Extraction(to="ana@test.com", message="hola", type="email")

    assert complete(extraction, "Enviar SMS al 600111222") == extraction


def test_the_type_follows_the_recipient_the_ai_found():
    completed = complete(Extraction(to="600111222", message="hola", type=None), "Avisa a Pedro al 600111222")

    assert completed.type == "sms"


def test_a_request_without_a_destination_stays_without_one():
    completed = complete(Extraction(to=None, message="hola", type=None), "manda un mensaje diciendo hola")

    assert completed.to is None
    assert completed.type is None


def test_international_phone_numbers_keep_their_prefix():
    assert complete(Extraction(None, "hola", None), "SMS al +34 600 111 222: hola").to == "+34600111222"
