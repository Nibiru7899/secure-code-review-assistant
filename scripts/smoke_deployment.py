"""Check this Compose project's persistence, local mounts and real database-down behavior."""
import argparse
import json
from pathlib import Path
import subprocess
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler


def compose(*args):
    return subprocess.check_output(["docker", "compose", *args], text=True, stderr=subprocess.STDOUT)


def smoke(destination):
    project = Path(__file__).resolve().parents[1]
    token = (project / ".local/demo-token.txt").read_text().strip()
    opener = build_opener(ProxyHandler({}))
    def request(path, authenticated=True):
        headers = {"Authorization": "Bearer " + token} if authenticated else {}
        try:
            with opener.open(Request("http://127.0.0.1:8000" + path, headers=headers), timeout=15) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())
    def ready():
        for attempt in range(60):
            try:
                code, body = request("/repositories/demo_ecu/status")
                if code == 200:
                    return body
            except (URLError, TimeoutError, OSError):
                pass
            sleep(0.5)
        raise RuntimeError("Application did not recover")
    result = {"checks": {}}
    before = ready()
    runs = request("/analysis-runs?repository=demo_ecu")[1]
    run_id = runs[0]["id"]
    report_path = f"/analysis-runs/{run_id}/report?repository=demo_ecu"
    original = request(report_path)[1]
    api_id = compose("ps", "-q", "api").strip()
    metadata = json.loads(subprocess.check_output(["docker", "inspect", api_id], text=True))[0]
    mount_flags = {m["Destination"]: m["RW"] for m in metadata["Mounts"]}
    result["checks"]["read_only_source_and_model_mounts"] = mount_flags["/repositories/demo_ecu"] is False and mount_flags["/data/models"] is False
    result["checks"]["application_data_writable_mount"] = mount_flags["/data"] is True
    result["checks"]["unprivileged_api"] = compose("exec", "-T", "api", "id", "-u").strip() == "10001"
    result["analyzer_version"] = compose("exec", "-T", "api", "cppcheck", "--version").strip()
    result["checks"]["loopback_api_port"] = metadata["HostConfig"]["PortBindings"]["8000/tcp"][0]["HostIp"] == "127.0.0.1"
    try:
        compose("stop", "postgres")
        code, body = request("/repositories/demo_ecu/status")
        result["checks"]["database_down_explicit_failure"] = code == 503 and body.get("outcome") == "FAILED"
        result["checks"]["denied_request_before_database"] = request("/repositories/demo_ecu/status", False)[0] == 401
    finally:
        compose("start", "postgres")
    ready()
    compose("restart", "api", "ui")
    after = ready()
    result["checks"]["snapshot_survives_restart"] = before["snapshot"] == after["snapshot"]
    result["checks"]["run_report_survives_restart"] = request(report_path)[1] == original
    logs = compose("logs", "--no-color", "api", "ui", "postgres")
    password = (project / ".local/docker/postgres-password.txt").read_text().strip()
    result["checks"]["credentials_absent_from_logs"] = token not in logs and password not in logs
    result["checks"]["source_body_absent_from_logs"] = "std::free(sample)" not in logs and "AUTHORIZED TASK:" not in logs
    result["checks"]["schema_and_dependencies_consistent"] = "No broken requirements found" in compose("exec", "-T", "api", "python", "-m", "pip", "check")
    result["snapshot"] = before["snapshot"]
    result["run_id"] = run_id
    result["status"] = "passed" if all(result["checks"].values()) else "failed"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(".local/deployment-smoke.json"))
    smoke(parser.parse_args().report)
