"""Minimal HTTP transport for AirTrajectory counterfactual forks.

Run:
    python -m airtrajectory.http_server --port 8765
"""
from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .api import fork_request

MAX_BODY_BYTES = 1_048_576


class Handler(BaseHTTPRequestHandler):
    server_version = "AirTrajectoryHTTP/0.2"

    def _cors_origin(self) -> str:
        return os.getenv("AIRTRAJECTORY_CORS_ORIGIN", "*")

    def _send_json(self, status: int, payload: dict | None = None) -> None:
        body = b"" if status == 204 else json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        if status != 204:
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Keep embedders/tests quiet; production can wrap the server with its own logging.
        return

    def do_OPTIONS(self):
        self._send_json(204)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "airtrajectory", "transport": "http"})
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/fork":
            self._send_json(404, {"error": "not_found"})
            return
        try:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ValueError("Content-Length required")
            length = int(raw_length)
            if length < 0 or length > MAX_BODY_BYTES:
                self._send_json(413, {"error": "payload_too_large", "max_bytes": MAX_BODY_BYTES})
                return
            raw = self.rfile.read(length)
            payload = json.loads(raw or b"{}")
            self._send_json(200, fork_request(payload))
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": "invalid_request", "detail": str(exc)})
        except Exception as exc:
            self._send_json(500, {"error": "internal_error", "detail": type(exc).__name__})


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = make_server(host, port)
    print(f"AirTrajectory HTTP listening on http://{host}:{server.server_address[1]}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.host, args.port)
