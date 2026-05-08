from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from safebox.core.services import VaultService
from safebox.core.transfer import TransferMessageKind, TransferMessageSender
from safebox.net.transfer_server import TransferHttpServer, lan_ip_address


def _test_server(
    service: VaultService,
    *,
    verification_code: str = "",
    lan_ip_provider=lan_ip_address,
) -> TransferHttpServer:
    return TransferHttpServer(
        service,
        host="127.0.0.1",
        verification_code=verification_code,
        lan_ip_provider=lan_ip_provider,
    )


def _request_json(url: str, payload: dict[str, str]) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_json_method(url: str, payload: dict[str, str], method: str) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_error_code(url: str, payload: dict[str, str]) -> int:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urlopen(request, timeout=5)
    except HTTPError as exc:
        return exc.code
    return 200


def _request_error_code_method(url: str, payload: dict[str, str], method: str) -> int:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        urlopen(request, timeout=5)
    except HTTPError as exc:
        return exc.code
    return 200


def _upload_file(url: str, filename: str, content: bytes, mime_type: str) -> dict:
    body, boundary = _multipart_file(filename, content, mime_type)
    request = Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _upload_error_code(url: str, filename: str, content: bytes, mime_type: str) -> int:
    body, boundary = _multipart_file(filename, content, mime_type)
    request = Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        urlopen(request, timeout=5)
    except HTTPError as exc:
        return exc.code
    return 200


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
    server = _test_server(service, verification_code="123456")

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
    assert "验证码" in html
    assert "验证" in html
    assert "initSession()" in html
    assert "refreshAfterWrite()" in html
    assert "editMessage(" in html
    assert session["conversation_id"] == server.conversation_id
    assert session["device_name"] == "手机浏览器"
    assert session["paired"] is False


def test_transfer_server_exposes_display_url_with_lan_ip(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, lan_ip_provider=lambda: "192.168.1.8")

    server.start()
    try:
        display_url = server.display_url
    finally:
        server.stop()

    assert display_url.startswith("http://192.168.1.8:")
    assert display_url != server.url


def test_transfer_server_display_url_falls_back_to_local_url(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, lan_ip_provider=lambda: "")

    server.start()
    try:
        assert server.display_url == server.url
    finally:
        server.stop()


def test_lan_ip_address_returns_empty_when_probe_fails(monkeypatch) -> None:
    class BrokenSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def connect(self, address) -> None:
            raise OSError("offline")

    monkeypatch.setattr("safebox.net.transfer_server.socket.socket", lambda *args: BrokenSocket())

    assert lan_ip_address() == ""


def test_transfer_server_accepts_phone_text_message(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        _request_json(f"{server.url}/api/pair", {"code": "123456"})
        result = _request_json(f"{server.url}/api/messages", {"text": "手机发来的文字"})
    finally:
        server.stop()

    messages = service.list_transfer_messages(server.conversation_id)

    assert result["ok"] is True
    assert messages[0].sender == TransferMessageSender.PHONE
    assert messages[0].text == "手机发来的文字"


def test_transfer_server_rejects_message_before_pairing(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        status = _request_error_code(f"{server.url}/api/messages", {"text": "手机发来的文字"})
    finally:
        server.stop()

    assert status == 403
    assert service.list_transfer_messages(server.conversation_id) == []


def test_transfer_server_pairs_with_verification_code(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        wrong_status = _request_error_code(f"{server.url}/api/pair", {"code": "000000"})
        with urlopen(f"{server.url}/api/session", timeout=5) as response:
            unpaired_session = json.loads(response.read().decode("utf-8"))
        result = _request_json(f"{server.url}/api/pair", {"code": "123456"})
        with urlopen(f"{server.url}/api/session", timeout=5) as response:
            paired_session = json.loads(response.read().decode("utf-8"))
    finally:
        server.stop()

    assert wrong_status == 403
    assert unpaired_session["paired"] is False
    assert result == {"ok": True, "paired": True}
    assert paired_session["paired"] is True


def test_transfer_server_lists_messages_for_paired_phone(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        desktop_message = service.add_transfer_text_message(
            server.conversation_id,
            sender=TransferMessageSender.DESKTOP,
            text="电脑发来的消息",
        )
        _request_json(f"{server.url}/api/pair", {"code": "123456"})
        with urlopen(f"{server.url}/api/messages", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.stop()

    assert payload["ok"] is True
    assert payload["messages"] == [
        {
            "id": desktop_message.id,
            "sender": "desktop",
            "kind": "text",
            "text": "电脑发来的消息",
            "attachment_id": "",
            "filename": "",
            "created_at": desktop_message.created_at,
            "updated_at": desktop_message.updated_at,
        }
    ]


def test_transfer_server_edits_text_message_for_paired_phone(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        message = service.add_transfer_text_message(
            server.conversation_id,
            sender=TransferMessageSender.PHONE,
            text="旧内容",
        )
        _request_json(f"{server.url}/api/pair", {"code": "123456"})
        result = _request_json_method(
            f"{server.url}/api/messages/{message.id}",
            {"text": "新内容"},
            "PATCH",
        )
    finally:
        server.stop()

    messages = service.list_transfer_messages(server.conversation_id)

    assert result["ok"] is True
    assert result["message_id"] == message.id
    assert messages[0].text == "新内容"
    assert messages[0].edited_at


def test_transfer_server_rejects_text_edit_before_pairing(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        message = service.add_transfer_text_message(
            server.conversation_id,
            sender=TransferMessageSender.PHONE,
            text="旧内容",
        )
        status = _request_error_code_method(
            f"{server.url}/api/messages/{message.id}",
            {"text": "新内容"},
            "PATCH",
        )
    finally:
        server.stop()

    messages = service.list_transfer_messages(server.conversation_id)

    assert status == 403
    assert messages[0].text == "旧内容"


def test_transfer_server_rejects_message_list_before_pairing(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        try:
            urlopen(f"{server.url}/api/messages", timeout=5)
        except HTTPError as exc:
            status = exc.code
        else:
            status = 200
    finally:
        server.stop()

    assert status == 403


def test_transfer_server_closes_conversation_from_paired_phone(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        _request_json(f"{server.url}/api/pair", {"code": "123456"})
        result = _request_json(f"{server.url}/api/close", {})
        blocked_status = _request_error_code(
            f"{server.url}/api/messages",
            {"text": "关闭后不应该写入"},
        )
    finally:
        server.stop()

    conversation = service.get_transfer_conversation(server.conversation_id)

    assert result == {"ok": True, "status": "closed"}
    assert conversation.status.value == "closed"
    assert conversation.closed_at
    assert blocked_status == 400
    assert service.list_transfer_messages(server.conversation_id) == []


def test_transfer_server_rejects_close_before_pairing(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        status = _request_error_code(f"{server.url}/api/close", {})
    finally:
        server.stop()

    conversation = service.get_transfer_conversation(server.conversation_id)

    assert status == 403
    assert conversation.status.value == "active"


def test_transfer_server_rejects_empty_text_message(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        _request_json(f"{server.url}/api/pair", {"code": "123456"})
        status = _request_error_code(f"{server.url}/api/messages", {"text": "   "})
    finally:
        server.stop()

    assert status == 400


def test_transfer_server_accepts_file_upload(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        _request_json(f"{server.url}/api/pair", {"code": "123456"})
        result = _upload_file(
            f"{server.url}/api/uploads",
            "invoice.pdf",
            b"pdf data",
            "application/pdf",
        )
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


def test_transfer_server_rejects_upload_before_pairing(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        status = _upload_error_code(
            f"{server.url}/api/uploads",
            "invoice.pdf",
            b"pdf data",
            "application/pdf",
        )
    finally:
        server.stop()

    assert status == 403
    assert service.list_transfer_messages(server.conversation_id) == []
    assert service.list_transfer_attachments(server.conversation_id) == []


def test_transfer_server_rejects_upload_after_close_without_saving_file(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        _request_json(f"{server.url}/api/pair", {"code": "123456"})
        _request_json(f"{server.url}/api/close", {})
        status = _upload_error_code(
            f"{server.url}/api/uploads",
            "after-close.pdf",
            b"pdf data",
            "application/pdf",
        )
    finally:
        server.stop()

    upload_dir = server.upload_dir / server.conversation_id

    assert status == 400
    assert not upload_dir.exists()
    assert service.list_transfer_attachments(server.conversation_id) == []


def test_transfer_server_treats_uploaded_image_as_image_message(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    server = _test_server(service, verification_code="123456")

    server.start()
    try:
        _request_json(f"{server.url}/api/pair", {"code": "123456"})
        _upload_file(
            f"{server.url}/api/uploads",
            "invoice.png",
            b"png data",
            "image/png",
        )
    finally:
        server.stop()

    messages = service.list_transfer_messages(server.conversation_id)

    assert messages[0].kind == TransferMessageKind.IMAGE
