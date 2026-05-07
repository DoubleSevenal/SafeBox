import pytest

from safebox.core.crypto import CryptoBox, InvalidPasswordError


def test_encrypt_decrypt_round_trip() -> None:
    box = CryptoBox.create("correct horse battery staple")
    token = box.encrypt_json({"name": "学校二课平台", "password": "secret"})

    assert isinstance(token, str)
    assert "secret" not in token
    assert box.decrypt_json(token)["name"] == "学校二课平台"


def test_wrong_password_cannot_open_payload() -> None:
    box = CryptoBox.create("first password")

    with pytest.raises(InvalidPasswordError):
        CryptoBox.from_existing("wrong password", box.salt, box.verify_token)


def test_existing_password_verification() -> None:
    box = CryptoBox.create("first password")
    reopened = CryptoBox.from_existing("first password", box.salt, box.verify_token)

    assert reopened.decrypt_json(box.encrypt_json({"ok": True})) == {"ok": True}
