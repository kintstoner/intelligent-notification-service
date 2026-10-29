import pytest
from pydantic import ValidationError

from domain.models import Notification


def test_an_email_notification_needs_an_email_address():
    with pytest.raises(ValidationError):
        Notification(to="600111222", message="hola", type="email")


def test_an_sms_notification_needs_a_phone_number():
    with pytest.raises(ValidationError):
        Notification(to="ana@test.com", message="hola", type="sms")


def test_phone_numbers_are_sent_as_digits():
    assert Notification(to="600-111-222", message="hola", type="sms").to == "600111222"


def test_the_message_cannot_be_blank():
    with pytest.raises(ValidationError):
        Notification(to="ana@test.com", message="  ", type="email")


def test_a_valid_email_notification():
    notification = Notification(to="ana@test.com", message="hola", type="email")

    assert notification.model_dump() == {"to": "ana@test.com", "message": "hola", "type": "email"}
