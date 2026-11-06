from cryptography.fernet import Fernet
import pytest

from backend.app.core.secrets import SecretBox, SecretError


def test_secret_box_encrypts_and_fingerprints_without_plaintext() -> None:
    box = SecretBox.from_key(Fernet.generate_key().decode("ascii"))

    ciphertext, fingerprint = box.encrypt_bearer("token-for-alice")

    assert "token-for-alice" not in ciphertext
    assert box.decrypt_bearer(ciphertext) == "token-for-alice"
    assert fingerprint == box.fingerprint("token-for-alice")


def test_secret_box_rejects_header_injection() -> None:
    box = SecretBox.from_key(Fernet.generate_key().decode("ascii"))

    with pytest.raises(SecretError):
        box.encrypt_bearer("token\r\nX-Injected: true")
