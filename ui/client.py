"""Private API transport. Credentials never enter URLs, logs, or exports."""
import ipaddress
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

from app.llm.ollama_client import _NoRedirect


class APIError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class API:
    def __init__(self, token):
        self.token = token
        self.origin = os.environ.get("REVIEW_API_URL", "http://127.0.0.1:8000")
        try:
            url = urlsplit(self.origin)
            local = url.hostname == "localhost" or ipaddress.ip_address(url.hostname).is_loopback
        except (ValueError, TypeError):
            local = self.origin == "http://api:8000" and os.environ.get("CONTAINER_LOCAL_NETWORK") == "1"
            url = urlsplit("http://api:8000") if local else urlsplit("http://invalid")
        if not local or url.scheme != "http" or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
            raise APIError("API must use the local configured origin")
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def request(self, endpoint, body=None):
        request = Request(self.origin.rstrip("/") + endpoint,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=300) as response:
                result = json.loads(response.read(16_777_217))
        except HTTPError as exc:
            try:
                result = json.loads(exc.read(16_777_217))
            except (ValueError, UnicodeError):
                raise APIError("API returned an unreadable error", status=exc.code) from None
            finally:
                exc.close()
            if result.get("outcome") == "FAILED" and result.get("id"):
                return result
            detail = result.get("detail", "Local API request failed")
            raise APIError(detail if isinstance(detail, str) else "Request validation failed; check selected fields and evidence", status=exc.code) from None
        except (URLError, OSError, ValueError):
            raise APIError("Local API unavailable or response unreadable") from None
        return result
