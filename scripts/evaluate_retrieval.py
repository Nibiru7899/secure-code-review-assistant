"""Evaluate actual CPU embeddings on a disposable copy of the fixed corpus."""

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import socket
import tempfile
from time import perf_counter
from unittest.mock import patch

from app.ingestion.indexer import Indexer
from app.retrieval.embedder import JinaEmbedder
from app.retrieval.retriever import Retriever
from app.security.permissions import AccessDenied, Permissions


def evaluate():
    project = Path(__file__).resolve().parents[1]
    model = JinaEmbedder(project / ".local/models/jina-code")
    cases = json.loads((project / "tests/fixtures/retrieval_questions.json").read_text())
    report = {"embedding": model.identity, "corpus": "demo_ecu-v1", "top_k": 3,
              "cases": [], "contexts": [], "checks": {}}
    with tempfile.TemporaryDirectory(prefix="secure-review-eval-", dir=project / ".local") as temporary, ExitStack() as cleanup:
        base = Path(temporary)
        root = base / "demo_ecu"
        shutil.copytree(project / "demo_ecu", root)
        token = "evaluation-only-token"
        permissions = Permissions({"credentials": {hashlib.sha256(token.encode()).hexdigest(): "evaluator"},
                                   "repositories": {"demo_ecu": {"root": str(root), "users": {"evaluator": ["."]}}}})
        indexer = Indexer(permissions, base / "data", model, project / "rules/coding_rules.md")
        # Any runtime network attempt fails the evaluation. No cloud embedding
        # fallback or telemetry is allowed during indexing or retrieval.
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Runtime network forbidden")), \
             patch("socket.create_connection", side_effect=AssertionError("Runtime network forbidden")):
            started = perf_counter()
            first = indexer.index(token, "demo_ecu")
            cleanup.callback(indexer.store.close)
            report["index_seconds"] = round(perf_counter() - started, 3)
            retriever = Retriever(indexer)
            for case in cases:
                started = perf_counter()
                result = retriever.retrieve(token, "demo_ecu", case["query"], symbol=case.get("symbol"), k=3)
                items = result.get("target", []) + result.get("related_code", [])
                if "expect_status" in case:
                    success = result["retrieval_status"] == case["expect_status"]
                elif "expect_symbol" in case:
                    success = case["expect_symbol"] in [item["symbol"] for item in items]
                else:
                    success = case["expect_rule"] in [item["rule_id"] for item in result["rules"]]
                report["cases"].append(dict(case, passed=success, seconds=round(perf_counter() - started, 3),
                                             retrieved_symbols=[item["symbol"] for item in items],
                                             retrieved_rules=[item["rule_id"] for item in result.get("rules", [])]))
                if len(report["contexts"]) < 5:
                    report["contexts"].append(result)
            initial = indexer.catalog.current(permissions.authorize(token, "demo_ecu"))
            second = indexer.index(token, "demo_ecu")
            report["checks"]["idempotency"] = second["snapshot"] == first["snapshot"] and second["index_status"] == "unchanged"
            report["duplicate_rate"] = 1 - len({c["chunk_id"] for c in initial["chunks"]}) / len(initial["chunks"])
            (root / "src/brake_control.cpp").write_text((root / "src/brake_control.cpp").read_text().replace("value < 0 ? 0 : value", "value < 0 ? 0 : value + 1"))
            changed = indexer.index(token, "demo_ecu")
            changed_target = retriever.retrieve(token, "demo_ecu", "clampPressure", symbol="clampPressure")
            report["checks"]["changed_source_replaced"] = changed["snapshot"] != first["snapshot"] and "value + 1" in changed_target["target"][0]["text"]
            (root / "src/diagnostics.cpp").unlink()
            deleted = indexer.index(token, "demo_ecu")
            report["checks"]["deleted_source_removed"] = retriever.retrieve(token, "demo_ecu", "safeDiagnostic", symbol="safeDiagnostic")["retrieval_status"] == "not_found"
            report["stale_active_chunk_rate"] = (indexer.store.code.count() - deleted["chunks"]) / max(1, deleted["chunks"])
            restarted = Indexer(permissions, base / "data", model, project / "rules/coding_rules.md")
            report["checks"]["persistence_reopen"] = Retriever(restarted).retrieve(token, "demo_ecu", "clampPressure", symbol="clampPressure")["snapshot"] == deleted["snapshot"]
            try:
                retriever.retrieve("unknown", "demo_ecu", "private source")
                report["checks"]["unauthorized_denied"] = False
            except AccessDenied:
                report["checks"]["unauthorized_denied"] = True
            report["checks"]["offline_runtime"] = True
    exact = [c for c in report["cases"] if "symbol" in c]
    semantic = [c for c in report["cases"] if "symbol" not in c]
    report["exact_lookup_accuracy"] = sum(c["passed"] for c in exact) / len(exact)
    report["relevant_top_k"] = sum(c["passed"] for c in semantic) / len(semantic)
    report["status"] = "passed" if all(report["checks"].values()) and report["exact_lookup_accuracy"] == 1 else "failed"
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(".local/retrieval-evaluation.json"))
    args = parser.parse_args()
    result = evaluate()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in ("contexts", "cases")}, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
