"""
Deterministic recovery of the recipient and the channel from the request itself, for when the AI answer lacks them.
It never produces a message: delivering text nobody wrote is worse than not delivering at all.
"""

import re
from dataclasses import replace

from domain.contacts import EMAIL, PHONE, is_email, is_phone, normalise_phone
from services.guardrails import Extraction

_EMAIL_WORDS = re.compile(r"\b(?:e-?mail|mail|correo)\b", re.IGNORECASE)
_SMS_WORDS = re.compile(r"\b(?:sms|mensaje de texto|tel[eé]fono|m[oó]vil)\b", re.IGNORECASE)


def complete(extraction: Extraction, user_input: str) -> Extraction:
    to = extraction.to or _first_contact(user_input)
    notification_type = extraction.type or _type_of(to) or _type_from_words(user_input)
    return replace(extraction, to=to, type=notification_type)


def _first_contact(text: str) -> str | None:
    if email := EMAIL.search(text):
        return email.group(0)
    if phone := PHONE.search(text):
        return normalise_phone(phone.group(0))
    return None


def _type_of(recipient: str | None) -> str | None:
    if recipient is None:
        return None
    if is_email(recipient):
        return "email"
    if is_phone(recipient):
        return "sms"
    return None


def _type_from_words(text: str) -> str | None:
    if _EMAIL_WORDS.search(text):
        return "email"
    if _SMS_WORDS.search(text):
        return "sms"
    return None
