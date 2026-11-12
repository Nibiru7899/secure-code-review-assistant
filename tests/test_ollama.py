import json
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import sleep
from unittest.mock import Mock

from app.llm.ollama_client import OllamaClient, OllamaError
from scripts.smoke_ollama import MODEL, smoke


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        mode = self.server.mode
        code = 302 if mode == "redirect" else 500 if mode == "http_error" else 200
        self.send_response(code)
        if mode == "redirect":
            self.send_header("Location", "http://example.com/source-upload")
        self.end_headers()
        if mode == "timeout":
            sleep(0.2)
            return
        data = {"ok": b'{"version":"test"}', "bad_json": b"not-json",
                "list": b"[]", "error": b'{"error":"private source must not be logged"}',
                "oversize": b"x" * 1_048_577}.get(mode, b"secret diagnostic")
        self.wfile.write(data)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.mode = "ok"
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = OllamaClient(f"http://127.0.0.1:{self.server.server_port}", timeout=1)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_local_api_success(self):
        self.assertEqual(self.client.request("version"), {"version": "test"})

    def test_invalid_json_error_array_and_size_are_explicit(self):
        for mode in ("bad_json", "list", "error", "oversize", "http_error"):
            with self.subTest(mode=mode):
                self.server.mode = mode
                with self.assertRaises(OllamaError) as caught:
                    self.client.request("version")
                self.assertNotIn("private source", str(caught.exception))
                self.assertNotIn("secret diagnostic", str(caught.exception))

    def test_remote_redirect_is_not_followed(self):
        self.server.mode = "redirect"
        with self.assertRaisesRegex(OllamaError, "HTTP 302"):
            self.client.request("version")

    def test_unavailable_api(self):
        self.server.shutdown()
        self.server.server_close()
        with self.assertRaisesRegex(OllamaError, "unavailable or timed out"):
            self.client.request("version")

    def test_no_arbitrary_endpoint(self):
        with self.assertRaises(ValueError):
            self.client.request("pull")

    def test_timeout_is_explicit(self):
        self.server.mode = "timeout"
        self.client.timeout = 0.05
        with self.assertRaisesRegex(OllamaError, "unavailable or timed out"):
            self.client.request("version")


class OriginTests(unittest.TestCase):
    def test_remote_and_ambiguous_origins_denied(self):
        for origin in ("https://127.0.0.1", "http://example.com", "http://192.168.1.1",
                       "http://user:password@localhost", "http://localhost/api",
                       "http://localhost?destination=external", "http://localhost#x",
                       "http://localhost:invalid", "file:///tmp/socket"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                OllamaClient(origin)

    def test_loopback_and_dns_free_localhost(self):
        self.assertEqual(OllamaClient("http://localhost").base_url, "http://127.0.0.1:11434")
        self.assertEqual(OllamaClient("http://[::1]:11434").base_url, "http://[::1]:11434")

    def test_timeout_validation(self):
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                OllamaClient(timeout=timeout)


class SmokeTests(unittest.TestCase):
    def client(self, failure=None):
        def request(endpoint, payload=None):
            if failure == "offline":
                raise OllamaError("Ollama version: unavailable or timed out")
            if endpoint == "version":
                return {"version": "test"}
            if endpoint == "tags":
                return {"models": [] if failure == "missing" else [{"name": MODEL, "digest": "sha-test"}]}
            if endpoint == "show":
                return {"details": {"quantization_level": "Q8_0" if failure == "quant" else "Q4_K_M"}}
            if endpoint == "generate":
                large = len(payload["prompt"]) > 1000
                return {"model": "other" if failure == "identity" else MODEL,
                        "done": failure != "incomplete", "response": "" if failure == "empty" else "Clamps negative input to zero.",
                        "prompt_eval_count": 7000 if failure == "overflow" else 4500 if large else 40,
                        "eval_count": 10}
            if endpoint == "ps":
                return {"models": [{"name": MODEL, "digest": "wrong" if failure == "digest" else "sha-test",
                                    "context_length": 4096 if failure == "context" else 8192,
                                    "size_vram": 0 if failure == "cpu" else 5_000_000_000}]}
            raise AssertionError(endpoint)
        return Mock(request=Mock(side_effect=request))

    def test_three_success_checks_and_explicit_context(self):
        client = self.client()
        result = smoke(client)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["checks"]), 3)
        requests = [c.args[1] for c in client.request.call_args_list if c.args[0] == "generate"]
        self.assertTrue(all(p["options"]["num_ctx"] == 8192 and p["stream"] is False for p in requests))
        self.assertNotIn("pull", [c.args[0] for c in client.request.call_args_list])

    def test_failures_never_pass(self):
        for failure in ("offline", "missing", "quant", "identity", "incomplete", "empty",
                        "overflow", "digest", "context", "cpu"):
            with self.subTest(failure=failure):
                result = smoke(self.client(failure))
                self.assertEqual(result["status"], "failed")
                self.assertIn("error", result)
                if failure == "overflow":
                    self.assertEqual(result["last_request"]["input_tokens"], 7000)

    def test_malformed_metadata(self):
        client = Mock()
        client.request.return_value = {"models": "invalid"}
        self.assertEqual(smoke(client)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
