"""Server-side bearer-token encryption and safe token fingerprints."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


class SecretError(ValueError):
    """Raised when encrypted credential data cannot be used safely."""


@dataclass(frozen=True)
class SecretBox:
    _fernet: Fernet
    _fingerprint_key: bytes

    @classmethod
    def from_key(cls, key: str) -> "SecretBox":
        try:
            return cls(Fernet(key.encode("ascii")), hashlib.sha256(key.encode("ascii")).digest())
        except (ValueError, TypeError) as error:
            raise SecretError("AUTHZ_SECRET_ENCRYPTION_KEY must be a Fernet key.") from error

    def encrypt_bearer(self, token: str) -> tuple[str, str]:
        if not token or any(character in token for character in "\r\n"):
            raise SecretError("Bearer token is invalid.")
        return self._fernet.encrypt(token.encode("utf-8")).decode("ascii"), self.fingerprint(token)

    def decrypt_bearer(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise SecretError("Stored bearer token cannot be decrypted.") from error

    def fingerprint(self, token: str) -> str:
        return hmac.new(self._fingerprint_key, token.encode("utf-8"), hashlib.sha256).hexdigest()
