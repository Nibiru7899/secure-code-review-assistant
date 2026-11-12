"""Demonstrate real local dependency/authorization/context failures without stopping Ollama."""
import json
import argparse
import os
from pathlib import Path
import socket

from app.analysis.cppcheck import Cppcheck
from app.llm.ollama_client import OllamaClient
from app.llm.schemas import TargetRequest
from app.main import create_app
from app.security.permissions import AccessDenied


def main(report_path=None):
    root = Path(__file__).resolve().parents[1]
    service = create_app().state.service
    token = os.environ.get("REVIEW_TOKEN", "")
    report = {"checks": {}}
    try:
        request = TargetRequest(repository="demo_ecu", snapshot="unknown", file="src/sensor.cpp", function="readSensorValue")
        try:
            service.analyze("unknown-test-credential", request, "review_function")
            raise AssertionError("Unknown identity was accepted")
        except AccessDenied:
            report["checks"]["unknown_identity_denied_before_storage"] = service.indexer.catalog is None
        scope = service.indexer.permissions.authorize(token, "demo_ecu")
        service.indexer.open_storage(scope)
        manifest = service.indexer.catalog.current(scope)
        request.snapshot = manifest["snapshot"]
        missing = Cppcheck(root / ".local/nonexistent-cppcheck.exe", root / ".local/analysis")
        report["analyzer_missing"] = missing.run(manifest)
        report["checks"]["analyzer_missing_not_clean"] = report["analyzer_missing"]["status"] == "unavailable"
        # Hold an unused loopback port without listening so no external service
        # or running Ollama instance needs to be changed.
        with socket.socket() as unavailable:
            unavailable.bind(("127.0.0.1", 0))
            service.client = OllamaClient(base_url="http://127.0.0.1:" + str(unavailable.getsockname()[1]), timeout=1)
            report["model_unavailable"] = service.analyze(token, request, "review_function")
        report["checks"]["model_failure_visible"] = report["model_unavailable"]["outcome"] == "FAILED" and not report["model_unavailable"]["findings"]
        service.input_budget = 100
        report["context_overflow"] = service.analyze(token, request, "review_function")
        report["checks"]["overflow_before_model"] = report["context_overflow"]["outcome"] == "INSUFFICIENT_EVIDENCE" and report["context_overflow"]["model_status"] == "not_requested"
        report["status"] = "passed" if all(report["checks"].values()) else "failed"
        (report_path or root / ".local/review-failure-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"status": report["status"], "checks": report["checks"]}, indent=2))
        return 0 if report["status"] == "passed" else 1
    finally:
        if service.indexer.store:
            service.indexer.store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    raise SystemExit(main(parser.parse_args().report))
