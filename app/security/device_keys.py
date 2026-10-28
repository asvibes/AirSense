import hashlib
import hmac
import secrets


def issue_device_key() -> str:
    return secrets.token_urlsafe(32)


def hash_device_key(key: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), key.encode(), hashlib.sha256).hexdigest()


def verify_device_key(key: str, stored_hash: str, pepper: str) -> bool:
    return hmac.compare_digest(hash_device_key(key, pepper), stored_hash)