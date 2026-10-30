import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.cache import cache


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_text(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("No se pudo descifrar el secreto") from exc


def new_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(encrypted_secret: str, token: str) -> bool:
    if not encrypted_secret or not token or not token.isdigit() or len(token) != 6:
        return False
    return pyotp.TOTP(decrypt_text(encrypted_secret)).verify(token, valid_window=1)


def _throttle_key(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()
    return f"login-failures:{kind}:{digest}"


def login_is_throttled(national_id: str, ip_address: str) -> bool:
    return any(cache.get(_throttle_key(kind, value), 0) >= 5 for kind, value in (("id", national_id), ("ip", ip_address)))


def register_login_failure(national_id: str, ip_address: str) -> None:
    for kind, value in (("id", national_id), ("ip", ip_address)):
        key = _throttle_key(kind, value)
        cache.set(key, cache.get(key, 0) + 1, timeout=300)


def clear_login_failures(national_id: str, ip_address: str) -> None:
    for kind, value in (("id", national_id), ("ip", ip_address)):
        cache.delete(_throttle_key(kind, value))


@dataclass(frozen=True)
class SafeAuditPayload:
    actor_id: int | None
    subject_id: int | None
    action: str
    resource: str
    result: str
    correlation_id: str

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items()}


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

