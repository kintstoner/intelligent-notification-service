import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Nine to fifteen digits, optionally with a leading "+" and spaces, dots or dashes between groups
PHONE = re.compile(r"\+?\d(?:[\s.-]?\d){8,14}")


def is_email(value: str) -> bool:
    return EMAIL.fullmatch(value) is not None


def is_phone(value: str) -> bool:
    return PHONE.fullmatch(value) is not None


def normalise_phone(value: str) -> str:
    return ("+" if value.startswith("+") else "") + re.sub(r"\D", "", value)
