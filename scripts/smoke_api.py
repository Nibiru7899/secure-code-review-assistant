"""Exercise the actual loopback FastAPI server; no review model calls."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, ProxyHandler, Request


def smoke():
    project = Path(__file__).resolve().parents[1]
    token = (project / ".local/demo-token.txt").read_text().strip()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}))

    def request(path, authorized=True, body=None):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + token
        data = None if body is None else json.dumps(body).encode()
        try:
            with opener.open(Request(url + path, data=data, headers=headers), timeout=60) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    with (project / ".local/api-smoke.log").open("wb") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory",
            "--host", "127.0.0.1", "--port", str(port), "--workers", "1", "--no-access-log"],
            cwd=project, stdout=log, stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    code, health = request("/health", authorized=False)
                    break
                except URLError:
                    if time.monotonic() >= deadline or process.poll() is not None:
                        raise RuntimeError("Local API failed to start; inspect .local/api-smoke.log")
                    time.sleep(0.1)
            denied, _ = request("/repositories/demo_ecu/status", authorized=False)
            indexed, index = request("/repositories/index", body={"repository": "demo_ecu"})
            status_code, status = request("/repositories/demo_ecu/status")
            schema_code, schema = request("/openapi.json", authorized=False)
            forbidden, _ = request("/repositories/unknown/status")
            findings_code, findings = request("/findings?repository=demo_ecu")
            checks = {"health": code == 200 and health["status"] == "ok",
                      "missing_credential_denied": denied == 401,
                      "unknown_repository_denied": forbidden == 403,
                      "authorized_index": indexed == 200 and index["index_status"] in ("ok", "unchanged"),
                      "authorized_status": status_code == 200 and status["snapshot"] == index["snapshot"],
                      "local_schema": schema_code == 200 and "/review/function" in schema["paths"],
                      "authorized_history": findings_code == 200 and isinstance(findings, list)}
            return {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
                    "snapshot": status.get("snapshot"), "files": len(status.get("files", []))}
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(".local/api-smoke.json"))
    args = parser.parse_args()
    report = smoke()
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "passed" else 1)
