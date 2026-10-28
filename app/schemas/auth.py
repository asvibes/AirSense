import re


class AuthInputError(ValueError):
    pass


def validate_email(value: object) -> str:
    if not isinstance(value, str):
        raise AuthInputError("Enter a valid email address.")
    email = value.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AuthInputError("Enter a valid email address.")
    return email


def validate_display_name(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
        raise AuthInputError("Name must contain 1 to 120 characters.")
    return value.strip()