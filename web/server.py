"""Portal CEMEX: estáticos + relay CORS hacia api.samsara.com. El token no se guarda."""
from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

WEB = Path(__file__).resolve().parent
if str(WEB) not in sys.path:
    sys.path.insert(0, str(WEB))

from service import load_portal_config

SAMSARA_API = "https://api.samsara.com"
ALLOW_HEADERS = "Authorization, Content-Type, Accept, X-Api-Key"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, format: str, *args) -> None:
        message = format % args
        if "samsara_api_" in message or "Authorization" in message:
            return
        super().log_message("%s", message.split("Authorization")[0])

    def _cors(self) -> None:
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", ALLOW_HEADERS)
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Cache-Control", "no-store")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/config":
            self._json(200, load_portal_config())
            return
        if path.startswith("/samsara"):
            self._proxy()
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        if urlparse(self.path).path.startswith("/samsara"):
            self._proxy()
            return
        self._json(404, {"ok": False, "error": "not found"})

    def _proxy(self) -> None:
        parsed = urlparse(self.path)
        suffix = parsed.path[len("/samsara") :] or "/"
        if ".." in suffix:
            self._json(400, {"ok": False, "error": "bad path"})
            return
        target = f"{SAMSARA_API}{suffix}"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else None
        authorization = self.headers.get("Authorization") or ""
        api_key = self.headers.get("X-Api-Key") or ""
        if not authorization and api_key:
            authorization = f"Bearer {api_key}"
        headers = {"Accept": "application/json"}
        if authorization:
            headers["Authorization"] = authorization
        if raw:
            headers["Content-Type"] = self.headers.get("Content-Type") or "application/json"
        request = Request(target, data=raw, headers=headers, method=self.command)
        try:
            with urlopen(request, timeout=60) as upstream:
                body = upstream.read()
                content_type = upstream.headers.get("Content-Type") or "application/json"
                self._send(upstream.status, body, content_type)
        except HTTPError as exc:
            self._send(exc.code, exc.read() or str(exc).encode("utf-8"), "application/json")
        except URLError as exc:
            self._json(502, {"ok": False, "error": str(exc.reason)})


def main() -> None:
    port = int(os.environ.get("PORT") or "8787")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Portal CEMEX en http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
