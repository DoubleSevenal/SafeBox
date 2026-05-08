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
from urllib.parse import quote, unquote

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
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      background: #e9edf3;
      color: #182033;
    }
    main { min-height: 100vh; display: grid; grid-template-rows: auto 1fr auto; }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      background: #ffffff;
      border-bottom: 1px solid #d8dee9;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    h1 { flex: 1; font-size: 18px; margin: 0; font-weight: 700; }
    .session-state {
      font-size: 13px;
      color: #64748b;
      white-space: nowrap;
    }
    .messages {
      padding: 16px 12px 120px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      overflow: auto;
    }
    .message-row { display: flex; }
    .message-row.desktop { justify-content: flex-start; }
    .message-row.phone { justify-content: flex-end; }
    .bubble {
      max-width: 78%;
      padding: 9px 11px;
      border-radius: 8px;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 16px;
      line-height: 1.45;
    }
    .desktop .bubble { background: #ffffff; }
    .phone .bubble { background: #95ec69; }
    .meta { margin-bottom: 4px; color: #738094; font-size: 12px; }
    .file-card {
      display: block;
      min-width: 210px;
      color: inherit;
      text-decoration: none;
    }
    .file-name { font-weight: 700; margin-bottom: 4px; }
    .file-meta { color: #617086; font-size: 12px; }
    .bubble button {
      min-height: 30px;
      margin-top: 8px;
      padding: 0 12px;
      border-radius: 8px;
      border: 1px solid #c9d3df;
      background: rgba(255,255,255,.75);
      color: #172033;
    }
    footer {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      background: #f7f8fb;
      border-top: 1px solid #d8dee9;
      padding: 10px 12px 12px;
      display: grid;
      gap: 8px;
    }
    .compose { display: flex; gap: 8px; align-items: flex-end; }
    textarea {
      flex: 1;
      width: 100%;
      min-height: 44px;
      max-height: 110px;
      border: 1px solid #d4deeb;
      border-radius: 8px;
      padding: 10px;
      font-size: 16px;
      resize: vertical;
      background: #ffffff;
    }
    button {
      min-height: 42px;
      padding: 0 14px;
      border: 0;
      border-radius: 8px;
      background: #16a34a;
      color: white;
      font-weight: 700;
    }
    button.secondary { background: #e2e8f0; color: #172033; }
    button.danger { background: #dc2626; }
    .pair {
      margin: 12px;
      padding: 14px;
      border: 1px solid #d4deeb;
      border-radius: 14px;
      background: #ffffff;
    }
    .hidden { display: none; }
    .readonly {
      margin: 12px;
      padding: 12px;
      border-radius: 12px;
      background: #fff7ed;
      color: #9a3412;
      border: 1px solid #fed7aa;
    }
    input[type="text"] {
      width: 160px;
      min-height: 42px;
      border: 1px solid #d4deeb;
      border-radius: 12px;
      padding: 0 12px;
      font-size: 16px;
    }
    .tools { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .file-label {
      min-height: 42px;
      padding: 10px 14px;
      border-radius: 8px;
      background: #e2e8f0;
      color: #172033;
      font-weight: 700;
    }
    .file-label input { display: none; }
    #status { color: #475569; font-size: 13px; min-height: 18px; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>传输助手</h1>
      <div id="sessionState" class="session-state">待验证</div>
      <button class="danger" onclick="closeConversation()">结束</button>
    </header>
    <div id="pairBox" class="pair">
      <input id="code" type="text" inputmode="numeric" placeholder="验证码">
      <button onclick="pairDevice()">验证</button>
    </div>
    <div id="readonlyNotice" class="readonly hidden">
      此次对话已结束，只能查看历史消息和下载附件。
    </div>
    <div id="messages" class="messages"></div>
    <footer>
      <div class="compose">
        <textarea id="text" placeholder="输入要发送到电脑的文字"></textarea>
        <button onclick="sendText()">发送</button>
      </div>
      <div class="tools">
        <label class="file-label">
          选择文件
          <input id="file" type="file" onchange="uploadFile()">
        </label>
        <button class="secondary" onclick="uploadFile()">上传附件</button>
        <div id="status"></div>
      </div>
    </footer>
  </main>
  <script>
    let paired = false;

    function setPaired(nextPaired) {
      paired = nextPaired;
      document.getElementById('pairBox').className = paired ? 'pair hidden' : 'pair';
    }

    function setWritable(writable) {
      document.getElementById('text').disabled = !writable;
      document.getElementById('file').disabled = !writable;
      for (const button of document.querySelectorAll('button')) {
        if (button.textContent !== '验证') button.disabled = !writable;
      }
    }

    function setSessionState(session) {
      const state = document.getElementById('sessionState');
      const closed = session.status === 'closed' || session.closed_at;
      state.textContent = closed ? '已结束' : (session.paired ? '已连接' : '待验证');
      document.getElementById('readonlyNotice').className = closed ? 'readonly' : 'readonly hidden';
    }

    function statusText(payload, fallback) {
      if (!payload || !payload.error) return fallback;
      const errors = {
        pair_required: '请先输入验证码',
        invalid_code: '验证码错误',
        text_required: '请输入内容',
        multipart_required: '上传格式不正确',
        file_required: '请选择文件',
        closed: '此次对话已结束'
      };
      return errors[payload.error] || payload.error || fallback;
    }

    async function initSession() {
      const response = await fetch('/api/session');
      if (!response.ok) return;
      const session = await response.json();
      setPaired(session.paired);
      setSessionState(session);
      setWritable(session.paired && session.status !== 'closed' && !session.closed_at);
      if (paired) loadMessages();
    }

    async function pairDevice() {
      const code = document.getElementById('code').value;
      const response = await fetch('/api/pair', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({code})
      });
      const payload = await response.json().catch(() => ({}));
      document.getElementById('status').textContent = response.ok
        ? '验证成功'
        : statusText(payload, '验证码错误');
      if (response.ok) {
        setPaired(true);
        setWritable(true);
        initSession();
        loadMessages();
      }
    }
    function refreshAfterWrite() {
      loadMessages();
      initSession();
    }
    async function sendText() {
      const text = document.getElementById('text').value;
      if (!text.trim()) {
        document.getElementById('status').textContent = '请输入内容';
        return;
      }
      const response = await fetch('/api/messages', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
      });
      const payload = await response.json().catch(() => ({}));
      document.getElementById('status').textContent = response.ok
        ? '已发送'
        : statusText(payload, '发送失败');
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
      const payload = await response.json().catch(() => ({}));
      document.getElementById('status').textContent = response.ok
        ? '已上传'
        : statusText(payload, '上传失败');
      if (response.ok) {
        document.getElementById('file').value = '';
        refreshAfterWrite();
      }
    }
    async function closeConversation() {
      const response = await fetch('/api/close', { method: 'POST' });
      const payload = await response.json().catch(() => ({}));
      document.getElementById('status').textContent = response.ok
        ? '会话已结束'
        : statusText(payload, '结束失败');
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
      const payload = await response.json().catch(() => ({}));
      document.getElementById('status').textContent = response.ok
        ? '已编辑'
        : statusText(payload, '编辑失败');
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
        row.className = 'message-row ' + item.sender;
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        const meta = document.createElement('div');
        meta.className = 'meta';
        meta.textContent = (item.sender === 'desktop' ? '电脑' : '手机') +
          (item.edited_at ? ' · 已编辑' : '');
        bubble.appendChild(meta);
        if (item.kind === 'text') {
          const body = document.createElement('div');
          body.textContent = item.text;
          bubble.appendChild(body);
        } else {
          const link = document.createElement('a');
          link.className = 'file-card';
          link.href = '/api/attachments/' + encodeURIComponent(item.attachment_id);
          link.target = '_blank';
          link.download = item.filename || 'attachment';
          const name = document.createElement('div');
          name.className = 'file-name';
          name.textContent = item.kind === 'image' ? '图片 · ' + item.filename : item.filename;
          const fileMeta = document.createElement('div');
          fileMeta.className = 'file-meta';
          fileMeta.textContent = '点击下载附件';
          link.appendChild(name);
          link.appendChild(fileMeta);
          bubble.appendChild(link);
        }
        if (item.kind === 'text') {
          const edit = document.createElement('button');
          edit.textContent = '编辑';
          edit.onclick = () => editMessage(item.id, item.text);
          bubble.appendChild(edit);
        }
        row.appendChild(bubble);
        messages.appendChild(row);
      }
      messages.scrollTop = messages.scrollHeight;
    }
    initSession();
    setWritable(false);
    setInterval(initSession, 1500);
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
                    conversation = owner.service.get_transfer_conversation(
                        owner.conversation_id
                    )
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "conversation_id": owner.conversation_id,
                            "device_name": owner.device_name,
                            "paired": owner.paired,
                            "status": conversation.status.value,
                            "closed_at": conversation.closed_at,
                        },
                    )
                    return
                if self.path == "/api/messages":
                    self._handle_messages_get()
                    return
                attachment_id = _attachment_id_from_path(self.path)
                if attachment_id:
                    self._handle_attachment_get(attachment_id)
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
                            "mime_type": attachment.mime_type if attachment else "",
                            "size_bytes": attachment.size_bytes if attachment else 0,
                            "created_at": message.created_at,
                            "updated_at": message.updated_at,
                            "edited_at": message.edited_at,
                        }
                    )
                self._send_json(HTTPStatus.OK, {"ok": True, "messages": messages})

            def _handle_attachment_get(self, attachment_id: str) -> None:
                if not owner.paired:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "pair_required"})
                    return
                attachment = next(
                    (
                        item
                        for item in owner.service.list_transfer_attachments(
                            owner.conversation_id
                        )
                        if item.id == attachment_id
                    ),
                    None,
                )
                if attachment is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "attachment_not_found"})
                    return
                source = Path(attachment.storage_path)
                if not source.exists():
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "file_not_found"})
                    return
                body = source.read_bytes()
                content_type = attachment.mime_type or "application/octet-stream"
                encoded_filename = quote(attachment.filename)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header(
                    "Content-Disposition",
                    f"attachment; filename*=UTF-8''{encoded_filename}",
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _handle_close_post(self) -> None:
                if not owner.paired:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "pair_required"})
                    return
                conversation = owner.service.close_transfer_conversation(
                    owner.conversation_id
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "status": conversation.status.value,
                        "closed_at": conversation.closed_at,
                    },
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
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {
                            "error": "closed"
                            if str(exc) == "Transfer conversation is closed"
                            else str(exc)
                        },
                    )
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
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {
                            "error": "closed"
                            if str(exc) == "Transfer conversation is closed"
                            else str(exc)
                        },
                    )
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
                if (
                    conversation.status
                    not in {
                        TransferConversationStatus.ACTIVE,
                        TransferConversationStatus.TRANSFERRED,
                    }
                    or conversation.closed_at
                ):
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"error": "closed"},
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
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {
                            "error": "closed"
                            if str(exc) == "Transfer conversation is closed"
                            else str(exc)
                        },
                    )
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
    message_id = unquote(path[len(prefix) :].strip())
    return message_id if message_id and "/" not in message_id else ""


def _attachment_id_from_path(path: str) -> str:
    prefix = "/api/attachments/"
    if not path.startswith(prefix):
        return ""
    attachment_id = unquote(path[len(prefix) :].strip())
    return attachment_id if attachment_id and "/" not in attachment_id else ""


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
