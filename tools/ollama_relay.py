"""Authenticated loopback-only relay for an OpenAI-compatible Ollama endpoint."""

from __future__ import annotations

import hmac
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_UPSTREAM = "http://192.168.1.104:11434/v1/chat/completions"


def make_handler(*, bearer_token: str, upstream_url: str):
    class RelayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args) -> None:  # avoid logging auth headers
            sys.stderr.write("relay %s\n" % (format % args))

        def _send(self, status: int, body: bytes = b"", content_type: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            # Rejecting before consuming a request body must not leave bytes on
            # a keep-alive connection for the next proxied request.
            self.send_header("Connection", "close")
            self.end_headers()
            if body:
                self.wfile.write(body)
            self.close_connection = True

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization")
            if not header:
                self._send(401, b'{"error":"missing authorization"}')
                return False
            expected = f"Bearer {bearer_token}"
            if not hmac.compare_digest(header, expected):
                self._send(403, b'{"error":"invalid authorization"}')
                return False
            return True

        def do_POST(self) -> None:
            if self.path != "/v1/chat/completions":
                self._send(404, b'{"error":"not found"}')
                return
            if not self._authorized():
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send(400, b'{"error":"invalid content length"}')
                return
            body = self.rfile.read(content_length)
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json"), "Accept": self.headers.get("Accept", "application/json")}
            try:
                request = Request(upstream_url, data=body, headers=headers, method="POST")
                with urlopen(request, timeout=180) as response:
                    payload = response.read()
                    self._send(response.status, payload, response.headers.get_content_type())
            except HTTPError as exc:
                self._send(exc.code, exc.read(), exc.headers.get_content_type() if exc.headers else "application/json")
            except (URLError, TimeoutError, OSError):
                self._send(502, b'{"error":"upstream unavailable"}')

        def do_GET(self) -> None:
            self._send(405, b'{"error":"method not allowed"}')

        do_PUT = do_GET
        do_PATCH = do_GET
        do_DELETE = do_GET

    return RelayHandler


def create_server(host: str, port: int, bearer_token: str, upstream_url: str) -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise ValueError("El relay sólo puede escuchar en 127.0.0.1.")
    if not bearer_token:
        raise ValueError("Falta LLM_RELAY_BEARER_TOKEN.")
    return ThreadingHTTPServer((host, port), make_handler(bearer_token=bearer_token, upstream_url=upstream_url))


def main() -> None:
    token = os.getenv("LLM_RELAY_BEARER_TOKEN", "")
    port = int(os.getenv("LLM_RELAY_PORT", "3100"))
    upstream = os.getenv("OLLAMA_RELAY_UPSTREAM", DEFAULT_UPSTREAM)
    server = create_server("127.0.0.1", port, token, upstream)
    print(f"Ollama relay listening on http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
