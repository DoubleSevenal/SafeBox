from __future__ import annotations

import json
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

from safebox.core.services import VaultService
from safebox.core.transfer import TransferMessageKind, TransferMessageSender

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
    #status { margin-top: 12px; color: #475569; }
  </style>
</head>
<body>
  <main>
    <h1>传输助手</h1>
    <textarea id="text" placeholder="输入要发送到电脑的文字"></textarea>
    <button onclick="sendText()">发送</button>
    <div class="tools">
      <label>
        选择文件
        <input id="file" type="file">
      </label>
      <button onclick="uploadFile()">上传附件</button>
    </div>
    <div id="status"></div>
  </main>
  <script>
    async function sendText() {
      const text = document.getElementById('text').value;
      const response = await fetch('/api/messages', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
      });
      document.getElementById('status').textContent = response.ok ? '已发送' : '发送失败';
      if (response.ok) document.getElementById('text').value = '';
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
      if (response.ok) document.getElementById('file').value = '';
    }
  </script>
</body>
</html>
"""


class TransferHttpServer:
    def __init__(
        self,
        service: VaultService,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        device_name: str = "手机浏览器",
    ) -> None:
        self.service = service
        self.host = host
        self.port = port
        self.device_name = device_name
        self.conversation_id = ""
        self.upload_dir = service.store.path.parent / "attachments"
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        if self._server is None:
            return ""
        host, port = self._server.server_address
        return f"http://{host}:{port}"

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
                        },
                    )
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_POST(self) -> None:
                if self.path == "/api/messages":
                    self._handle_message_post()
                    return
                if self.path == "/api/uploads":
                    self._handle_upload_post()
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def _handle_message_post(self) -> None:
                payload = self._read_json()
                text = str(payload.get("text", "")).strip()
                if not text:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "text_required"})
                    return
                message = owner.service.add_transfer_text_message(
                    owner.conversation_id,
                    sender=TransferMessageSender.PHONE,
                    text=text,
                )
                self._send_json(HTTPStatus.OK, {"ok": True, "message_id": message.id})

            def _handle_upload_post(self) -> None:
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
                target_dir = owner.upload_dir / owner.conversation_id
                target_dir.mkdir(parents=True, exist_ok=True)
                target = _unique_path(target_dir / filename)
                target.write_bytes(content)
                kind = (
                    TransferMessageKind.IMAGE
                    if mime_type.startswith("image/")
                    else TransferMessageKind.FILE
                )
                message, attachment = owner.service.add_transfer_attachment_message(
                    owner.conversation_id,
                    sender=TransferMessageSender.PHONE,
                    kind=kind,
                    filename=filename,
                    mime_type=mime_type,
                    size_bytes=len(content),
                    storage_path=str(target),
                )
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
