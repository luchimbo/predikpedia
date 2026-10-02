import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import TestCase
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.ollama_relay import create_server


class UpstreamHandler(BaseHTTPRequestHandler):
    received_body = b""
    def do_POST(self):
        type(self).received_body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        payload = b'{"choices":[{"message":{"content":"ok"}}]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, format, *args):
        pass


class RelayTests(TestCase):
    def setUp(self):
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        self.relay = create_server("127.0.0.1", 0, "secret", f"http://127.0.0.1:{self.upstream.server_port}/v1/chat/completions")
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.relay_thread = threading.Thread(target=self.relay.serve_forever, daemon=True)
        self.upstream_thread.start()
        self.relay_thread.start()
        self.url = f"http://127.0.0.1:{self.relay.server_port}/v1/chat/completions"

    def tearDown(self):
        self.relay.shutdown(); self.relay.server_close()
        self.upstream.shutdown(); self.upstream.server_close()

    def request(self, token=None, path=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return Request(path or self.url, data=b'{"model":"qwen"}', headers=headers, method="POST")

    def test_requires_authentication(self):
        with self.assertRaises(HTTPError) as result:
            urlopen(self.request())
        self.assertEqual(401, result.exception.code)
        with self.assertRaises(HTTPError) as result:
            urlopen(self.request("wrong"))
        self.assertEqual(403, result.exception.code)

    def test_rejects_other_paths(self):
        with self.assertRaises(HTTPError) as result:
            urlopen(self.request("secret", self.url.replace("/v1/chat/completions", "/other")))
        self.assertEqual(404, result.exception.code)

    def test_rejects_non_post_methods(self):
        with self.assertRaises(HTTPError) as result:
            urlopen(Request(self.url, headers={"Authorization": "Bearer secret"}, method="GET"))
        self.assertEqual(405, result.exception.code)

    def test_forwards_authenticated_request(self):
        with urlopen(self.request("secret")) as response:
            self.assertEqual(200, response.status)
            self.assertEqual("ok", json.loads(response.read())["choices"][0]["message"]["content"])
        self.assertEqual(b'{"model":"qwen"}', UpstreamHandler.received_body)
