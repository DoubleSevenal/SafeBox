from __future__ import annotations

import json
import secrets
import socket
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

from safebox.core.services import VaultService
from safebox.core.transfer import (
    TransferConversationStatus,
    TransferMessageKind,
    TransferMessageSender,
)


def lan_ip_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            return probe.getsockname()[0]
    except OSError:
        return ""


MOBILE_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>传输助手</title>
  <style>
    body {
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      background: #f3f6fb;
      color: #172033;
    }
    main { max-width: 720px; margin: 0 auto; padding: 24px; }
    h1 { font-size: 28px; margin: 0 0 16px; }
    .tools { margin-top: 18px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .messages { margin-top: 18px; display: grid; gap: 10px; }
    .message {
      padding: 10px 12px;
      border: 1px solid #d4deeb;
      border-radius: 12px;
      background: #ffffff;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .message.desktop { border-color: #bfdbfe; background: #eff6ff; }
    .message.phone { border-color: #d1fae5; background: #f0fdf4; }
    .meta { margin-bottom: 4px; color: #64748b; font-size: 13px; }
    .message button {
      min-height: 32px;
      margin-top: 8px;
      padding: 0 12px;
      background: #e2e8f0;
      color: #172033;
    }
    textarea {
      box-sizing: border-box;
      width: 100%;
      min-height: 160px;
      border: 1px solid #d4deeb;
      border-radius: 14px;
      padding: 12px;
      font-size: 16px;
    }
    button {
      margin-top: 12px;
      min-height: 42px;
      padding: 0 18px;
      border: 0;
      border-radius: 12px;
      background: #2563eb;
      color: white;
      font-weight: 700;
    }
    .pair {
      margin: 0 0 16px;
      padding: 14px;
      border: 1px solid #d4deeb;
      border-radius: 14px;
      background: #ffffff;
    }
    .hidden { display: none; }
    input[type="text"] {
      box-sizing: border-box;
      width: 160px;
      min-height: 42px;
      border: 1px solid #d4deeb;
      border-radius: 12px;
      padding: 0 12px;
      font-size: 16px;
    }
    #status { margin-top: 12px; color: #475569; }
  </style>
</head>
<body>
  <main>
    <h1>传输助手</h1>
    <div id="pairBox" class="pair">
      <input id="code" type="text" inputmode="numeric" placeholder="验证码">
      <button onclick="pairDevice()">验证</button>
    </div>
    <textarea id="text" placeholder="输入要发送到电脑的文字"></textarea>
    <button onclick="sendText()">发送</button>
    <div class="tools">
      <label>
        选择文件
        <input id="file" type="file">
      </label>
      <button onclick="uploadFile()">上传附件</button>
      <button onclick="closeConversation()">结束会话</button>
    </div>
    <div id="messages" class="messages"></div>
    <div id="status"></div>
  </main>
  <script>
    let paired = false;

    function setPaired(nextPaired) {
      paired = nextPaired;
      document.getElementById('pairBox').className = paired ? 'pair hidden' : 'pair';
    }

    async function initSession() {
      const response = await fetch('/api/session');
      if (!response.ok) return;
      const session = await response.json();
      setPaired(session.paired);
      if (paired) loadMessages();
    }

    async function pairDevice() {
      const code = document.getElementById('code').value;
      const response = await fetch('/api/pair', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({code})
      });
      document.getElementById('status').textContent = response.ok ? '验证成功' : '验证码错误';
      if (response.ok) {
        setPaired(true);
        loadMessages();
      }
    }
    function refreshAfterWrite() {
      loadMessages();
      initSession();
    }
    async function sendText() {
      const text = document.getElementById('text').value;
      const response = await fetch('/api/messages', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
      });
      document.getElementById('status').textContent = response.ok ? '已发送' : '发送失败';
      if (response.ok) {
        document.getElementById('text').value = '';
        refreshAfterWrite();
      }
    }
    async function uploadFile() {
      const file = document.getElementById('file').files[0];
      if (!file) {
        document.getElementById('status').textContent = '请选择文件';
        return;
      }
      const data = new FormData();
      data.append('file', file);
      const response = await fetch('/api/uploads', { method: 'POST', body: data });
      document.getElementById('status').textContent = response.ok ? '已上传' : '上传失败';
      if (response.ok) {
        document.getElementById('file').value = '';
        refreshAfterWrite();
      }
    }
    async function closeConversation() {
      const response = await fetch('/api/close', { method: 'POST' });
      document.getElementById('status').textContent = response.ok ? '会话已结束' : '结束失败';
      if (response.ok) refreshAfterWrite();
    }
    async function editMessage(id, currentText) {
      const text = prompt('编辑消息', currentText || '');
      if (text === null) return;
      const response = await fetch('/api/messages/' + encodeURIComponent(id), {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
      });
      document.getElementById('status').textContent = response.ok ? '已编辑' : '编辑失败';
      if (response.ok) loadMessages();
    }
    async function loadMessages() {
      const response = await fetch('/api/messages');
      if (!response.ok) return;
      const payload = await response.json();
      const messages = document.getElementById('messages');
      messages.innerHTML = '';
      for (const item of payload.messages) {
        const row = document.createElement('div');
        row.className = 'message ' + item.sender;
        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.textContent = (item.sender === 'desktop' ? '电脑' : '手机') +
          (item.edited_at ? ' · 已编辑' : '');
        const body = document.createElement('div');
        body.textContent = item.text || item.filename || '[附件]';
        row.appendChild(meta);
        row.appendChild(body);
        if (item.kind === 'text') {
          const edit = document.createElement('button');
          edit.textContent = '编辑';
          edit.onclick = () => editMessage(item.id, item.text);
          row.appendChild(edit);
        }
        messages.appendChild(row);
      }
    }
    initSession();
    setInterval(loadMessages, 1500);
  </script>
</body>
</html>
"""


class TransferHttpServer:
    def __init__(
        self,
        service: VaultService,
        *,
        host: str = "0.0.0.0",
        port: int = 0,
        device_name: str = "手机浏览器",
        lan_ip_provider=lan_ip_address,
        verification_code: str = "",
    ) -> None:
        self.service = service
        self.host = host
        self.port = port
        self.device_name = device_name
        self.lan_ip_provider = lan_ip_provider
        self.verification_code = verification_code or f"{secrets.randbelow(1_000_000):06d}"
        self.paired = False
        self.conversation_id = ""
        self.upload_dir = service.store.path.parent / "attachments"
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        if self._server is None:
            return ""
        host, port = self._server.server_address
        if host == "0.0.0.0":
            host = "127.0.0.1"
        return f"http://{host}:{port}"

    @property
    def display_url(self) -> str:
        if self._server is None:
            return ""
        lan_ip = self.lan_ip_provider()
        if not lan_ip:
            return self.url
        _, port = self._server.server_address
        return f"http://{lan_ip}:{port}"

    def start(self) -> None:
        if self._server is not None:
            return
        conversation = self.service.create_transfer_conversation(
            title="手机对话",
            device_name=self.device_name,
        )
        self.conversation_id = conversation.id
        handler = self._make_handler()
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None
        self._server = None

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/":
                    self._send_text(HTTPStatus.OK, MOBILE_PAGE, "text/html; charset=utf-8")
                    return
                if self.path == "/api/session":
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "conversation_id": owner.conversation_id,
                            "device_name": owner.device_name,
                            "paired": owner.paired,
                        },
                    )
                    return
                if self.path == "/api/messages":
                    self._handle_messages_get()
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_POST(self) -> None:
                if self.path == "/api/pair":
                    self._handle_pair_post()
                    return
                if self.path == "/api/messages":
                    self._handle_message_post()
                    return
                if self.path == "/api/uploads":
                    self._handle_upload_post()
                    return
                if self.path == "/api/close":
                    self._handle_close_post()
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_PATCH(self) -> None:
                message_id = _message_id_from_path(self.path)
                if message_id:
                    self._handle_message_patch(message_id)
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def _handle_pair_post(self) -> None:
                payload = self._read_json()
                code = str(payload.get("code", "")).strip()
                if code != owner.verification_code:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid_code"})
                    return
                owner.paired = True
                self._send_json(HTTPStatus.OK, {"ok": True, "paired": True})

            def _handle_messages_get(self) -> None:
                if not owner.paired:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "pair_required"})
                    return
                attachments = {
                    attachment.id: attachment
                    for attachment in owner.service.list_transfer_attachments(
                        owner.conversation_id
                    )
                }
                messages = []
                for message in owner.service.list_transfer_messages(owner.conversation_id):
                    attachment = attachments.get(message.attachment_id)
                    messages.append(
                        {
                            "id": message.id,
                            "sender": message.sender.value,
                            "kind": message.kind.value,
                            "text": message.text,
                            "attachment_id": message.attachment_id,
                            "filename": attachment.filename if attachment else "",
                            "created_at": message.created_at,
                            "updated_at": message.updated_at,
                            "edited_at": message.edited_at,
                        }
                    )
                self._send_json(HTTPStatus.OK, {"ok": True, "messages": messages})

            def _handle_close_post(self) -> None:
                if not owner.paired:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "pair_required"})
                    return
                conversation = owner.service.close_transfer_conversation(
                    owner.conversation_id
                )
                self._send_json(
                    HTTPStatus.OK,
                    {"ok": True, "status": conversation.status.value},
                )

            def _handle_message_post(self) -> None:
                if not owner.paired:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "pair_required"})
                    return
                payload = self._read_json()
                text = str(payload.get("text", "")).strip()
                if not text:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "text_required"})
                    return
                try:
                    message = owner.service.add_transfer_text_message(
                        owner.conversation_id,
                        sender=TransferMessageSender.PHONE,
                        text=text,
                    )
                except ValueError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                self._send_json(HTTPStatus.OK, {"ok": True, "message_id": message.id})

            def _handle_message_patch(self, message_id: str) -> None:
                if not owner.paired:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "pair_required"})
                    return
                payload = self._read_json()
                text = str(payload.get("text", "")).strip()
                try:
                    message = owner.service.edit_transfer_text_message(
                        owner.conversation_id,
                        message_id,
                        text=text,
                    )
                except KeyError:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "message_not_found"})
                    return
                except ValueError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                self._send_json(HTTPStatus.OK, {"ok": True, "message_id": message.id})

            def _handle_upload_post(self) -> None:
                if not owner.paired:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "pair_required"})
                    return
                content_type = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in content_type:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "multipart_required"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                file_part = _parse_multipart_file(content_type, body)
                if file_part is None:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "file_required"})
                    return
                filename, mime_type, content = file_part
                conversation = owner.service.get_transfer_conversation(
                    owner.conversation_id
                )
                if conversation.status != TransferConversationStatus.ACTIVE:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"error": "Transfer conversation is closed"},
                    )
                    return
                target_dir = owner.upload_dir / owner.conversation_id
                target_dir.mkdir(parents=True, exist_ok=True)
                target = _unique_path(target_dir / filename)
                target.write_bytes(content)
                kind = (
                    TransferMessageKind.IMAGE
                    if mime_type.startswith("image/")
                    else TransferMessageKind.FILE
                )
                try:
                    message, attachment = owner.service.add_transfer_attachment_message(
                        owner.conversation_id,
                        sender=TransferMessageSender.PHONE,
                        kind=kind,
                        filename=filename,
                        mime_type=mime_type,
                        size_bytes=len(content),
                        storage_path=str(target),
                    )
                except ValueError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "message_id": message.id,
                        "attachment_id": attachment.id,
                    },
                )

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                if not raw:
                    return {}
                try:
                    data = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    return {}
                return data if isinstance(data, dict) else {}

            def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_text(self, status: HTTPStatus, text: str, content_type: str) -> None:
                body = text.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


def _parse_multipart_file(
    content_type: str,
    body: bytes,
) -> tuple[str, str, bytes] | None:
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + body
    )
    if not message.is_multipart():
        return None
    for part in message.iter_parts():
        if part.get_param("name", header="content-disposition") != "file":
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        return Path(filename).name, part.get_content_type(), payload
    return None


def _message_id_from_path(path: str) -> str:
    prefix = "/api/messages/"
    if not path.startswith(prefix):
        return ""
    message_id = path[len(prefix) :].strip()
    return message_id if message_id and "/" not in message_id else ""


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1
