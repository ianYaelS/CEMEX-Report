"""Portal CEMEX: misma lógica que la Function V2 + descarga y enlace a Storage."""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

WEB = Path(__file__).resolve().parent
if str(WEB) not in sys.path:
    sys.path.insert(0, str(WEB))

from service import build_report, list_fleet, load_portal_config, report_payload


def _token(handler: SimpleHTTPRequestHandler) -> str:
    header = handler.headers.get("X-Api-Key") or handler.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        header = header[7:]
    return (header or os.environ.get("api_key") or os.environ.get("SAMSARA_API_TOKEN") or "").strip()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, format: str, *args) -> None:
        if "/api/" in str(args[0] if args else ""):
            message = format % args
            if "api_key" in message or "samsara_api_" in message:
                return
        super().log_message(format, *args)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/config":
            self._json(200, load_portal_config())
            return
        if path == "/api/vehicles":
            token = _token(self)
            if not token:
                self._json(401, {"ok": False, "error": "Falta api_key en el servidor o en la sesión."})
                return
            try:
                self._json(200, {"ok": True, "vehicles": list_fleet(token)})
            except Exception as exc:
                self._json(502, {"ok": False, "error": str(exc)})
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/report":
            self._json(404, {"ok": False, "error": "not found"})
            return
        token = _token(self)
        if not token:
            self._json(401, {"ok": False, "error": "Falta api_key en el servidor o en la sesión."})
            return
        data = self._read_json()
        vehicle_id = str(data.get("vehicle_id") or "").strip()
        start_raw = str(data.get("start_time") or "").strip()
        end_raw = str(data.get("end_time") or "").strip()
        if not vehicle_id or not start_raw or not end_raw:
            self._json(400, {"ok": False, "error": "Selecciona unidad, start_time y end_time."})
            return
        try:
            result = build_report(
                token,
                vehicle_id=vehicle_id,
                start_time=date.fromisoformat(start_raw[:10]),
                end_time=date.fromisoformat(end_raw[:10]),
            )
            self._json(200, report_payload(result))
        except Exception as exc:
            self._json(502, {"ok": False, "error": str(exc)})


def main() -> None:
    port = int(os.environ.get("PORT") or "8787")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Portal CEMEX en http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
