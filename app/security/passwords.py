import re

from werkzeug.security import check_password_hash, generate_password_hash


def validate_password(password: str) -> None:
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError("Password must contain 12 to 256 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise ValueError("Password must include at least one letter and one number.")


def hash_password(password: str) -> str:
    validate_password(password)
    return generate_password_hash(password, method="scrypt")


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)