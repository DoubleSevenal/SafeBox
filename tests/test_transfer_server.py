from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from safebox.core.services import VaultService
from safebox.core.transfer import TransferMessageKind, TransferMessageSender
from safebox.net.transfer_server import TransferHttpServer


def _request_json(url: str, payload: dict[str, str]) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _multipart_file(filename: str, content: bytes, mime_type: str) -> tuple[bytes, str]:
    boundary = "----safebox-test-boundary"
    body = b"\r\n".join(
        [
            f"--{boundary}".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{filename}"'
            ).encode(),
            f"Content-Type: {mime_type}".encode(),
            b"",
            content,
            f"--{boundary}--".encode(),
            b"",
        ]
    )
    return body, boundary


def test_transfer_server_serves_mobile_page_and_session(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = TransferHttpServer(service)

    server.start()
    try:
        with urlopen(server.url, timeout=5) as response:
            html = response.read().decode("utf-8")
        with urlopen(f"{server.url}/api/session", timeout=5) as response:
            session = json.loads(response.read().decode("utf-8"))
    finally:
        server.stop()

    assert "传输助手" in html
    assert "发送" in html
    assert "选择文件" in html
    assert "上传附件" in html
    assert session["conversation_id"] == server.conversation_id
    assert session["device_name"] == "手机浏览器"


def test_transfer_server_accepts_phone_text_message(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = TransferHttpServer(service)

    server.start()
    try:
        result = _request_json(f"{server.url}/api/messages", {"text": "手机发来的文字"})
    finally:
        server.stop()

    messages = service.list_transfer_messages(server.conversation_id)

    assert result["ok"] is True
    assert messages[0].sender == TransferMessageSender.PHONE
    assert messages[0].text == "手机发来的文字"


def test_transfer_server_rejects_empty_text_message(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = TransferHttpServer(service)

    server.start()
    try:
        request = Request(
            f"{server.url}/api/messages",
            data=json.dumps({"text": "   "}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            status = exc.code
        else:
            status = 200
    finally:
        server.stop()

    assert status == 400


def test_transfer_server_accepts_file_upload(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = TransferHttpServer(service)
    body, boundary = _multipart_file("invoice.pdf", b"pdf data", "application/pdf")

    server.start()
    try:
        request = Request(
            f"{server.url}/api/uploads",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
    finally:
        server.stop()

    messages = service.list_transfer_messages(server.conversation_id)
    attachments = service.list_transfer_attachments(server.conversation_id)

    assert result["ok"] is True
    assert result["attachment_id"] == attachments[0].id
    assert messages[0].kind == TransferMessageKind.FILE
    assert messages[0].attachment_id == attachments[0].id
    assert attachments[0].filename == "invoice.pdf"
    assert attachments[0].mime_type == "application/pdf"
    assert attachments[0].size_bytes == len(b"pdf data")
    assert attachments[0].storage_path.endswith("invoice.pdf")
    assert b"pdf data" in open(attachments[0].storage_path, "rb").read()


def test_transfer_server_treats_uploaded_image_as_image_message(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = TransferHttpServer(service)
    body, boundary = _multipart_file("invoice.png", b"png data", "image/png")

    server.start()
    try:
        request = Request(
            f"{server.url}/api/uploads",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urlopen(request, timeout=5):
            pass
    finally:
        server.stop()

    messages = service.list_transfer_messages(server.conversation_id)

    assert messages[0].kind == TransferMessageKind.IMAGE
