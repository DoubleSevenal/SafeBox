from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class InvalidPasswordError(ValueError):
    """Raised when the master password cannot decrypt the vault."""


def _derive_key(master_password: str, salt: bytes) -> bytes:
    if not master_password:
        raise ValueError("Master password cannot be empty")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8")))


@dataclass(slots=True)
class CryptoBox:
    salt: str
    verify_token: str
    _fernet: Fernet

    @classmethod
    def create(cls, master_password: str) -> CryptoBox:
        salt_bytes = os.urandom(16)
        key = _derive_key(master_password, salt_bytes)
        fernet = Fernet(key)
        verify_token = fernet.encrypt(b"safebox-vault").decode("utf-8")
        return cls(
            salt=base64.urlsafe_b64encode(salt_bytes).decode("utf-8"),
            verify_token=verify_token,
            _fernet=fernet,
        )

    @classmethod
    def from_existing(cls, master_password: str, salt: str, verify_token: str) -> CryptoBox:
        salt_bytes = base64.urlsafe_b64decode(salt.encode("utf-8"))
        key = _derive_key(master_password, salt_bytes)
        fernet = Fernet(key)
        try:
            fernet.decrypt(verify_token.encode("utf-8"))
        except InvalidToken as exc:
            raise InvalidPasswordError("Master password is incorrect") from exc
        return cls(salt=salt, verify_token=verify_token, _fernet=fernet)

    def encrypt_json(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(raw).decode("utf-8")

    def decrypt_json(self, token: str) -> dict[str, Any]:
        try:
            raw = self._fernet.decrypt(token.encode("utf-8"))
        except InvalidToken as exc:
            raise InvalidPasswordError("Encrypted payload cannot be opened") from exc
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Encrypted payload is not an object")
        return data

