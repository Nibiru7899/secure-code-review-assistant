"""Bounded, loopback-only JSON transport. Never downloads models."""

import ipaddress
import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class OllamaError(RuntimeError):
    """An explicit local inference failure, without response-body logging."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaClient:
    def __init__(self, base_url="http://127.0.0.1:11434", timeout=60, allow_container_host=False):
        try:
            url = urlsplit(base_url)
            host = url.hostname
            local = host == "localhost" or (allow_container_host and host == "host.docker.internal") or ipaddress.ip_address(host).is_loopback
            port = url.port
        except (ValueError, TypeError):
            raise ValueError("Ollama URL must use a loopback address") from None
        if (not local or url.scheme != "http" or url.username or url.password
                or url.path not in ("", "/") or url.query or url.fragment):
            raise ValueError("Ollama URL must be a plain loopback HTTP origin")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be finite and positive")
        # Canonicalize localhost to an IP rather than depending on DNS.
        host = "127.0.0.1" if host == "localhost" else host
        host = f"[{host}]" if ":" in host else host
        self.base_url = f"http://{host}:{port or 11434}"
        self.timeout = timeout
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def request(self, endpoint, payload=None):
        if endpoint not in ("tags", "show", "generate", "ps", "version"):
            raise ValueError("Unsupported Ollama endpoint")
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(self.base_url + "/api/" + endpoint, data=body,
                          headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(1_048_577)
        except HTTPError as exc:
            code = exc.code
            exc.close()
            raise OllamaError(f"Ollama {endpoint}: HTTP {code}") from None
        except (URLError, OSError, TimeoutError):
            raise OllamaError(f"Ollama {endpoint}: unavailable or timed out") from None
        if len(raw) > 1_048_576:
            raise OllamaError(f"Ollama {endpoint}: response exceeds size limit")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise OllamaError(f"Ollama {endpoint}: invalid JSON") from None
        if not isinstance(result, dict) or result.get("error"):
            raise OllamaError(f"Ollama {endpoint}: invalid or error response")
        return result
