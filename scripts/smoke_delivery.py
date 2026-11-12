"""Live local API delivery checks. Reviewer actions use disposable deterministic fixtures."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock

from app.db.database import Catalog
from app.llm.schemas import Finding, ReviewDecision
from app.reviewer import decide, report
from app.security.permissions import Permissions
from ui.client import API


def smoke(origin, destination):
    project = Path(__file__).resolve().parents[1]
    os.environ["REVIEW_API_URL"] = origin
    api = API((project / ".local/demo-token.txt").read_text().strip())
    result = {"origin": origin, "checks": {}}
    result["checks"]["health"] = api.request("/health")["status"] == "ok"
    result["checks"]["authorized_repositories"] = "demo_ecu" in api.request("/repositories")
    indexed = api.request("/repositories/index", {"repository": "demo_ecu"})
    status = api.request("/repositories/demo_ecu/status")
    result["checks"]["index_and_status"] = indexed["snapshot"] == status["snapshot"]
    unit = next(f for f in status["functions"] if f["symbol"] == "doubleFreeSample")
    run = api.request("/review/function", {"repository": "demo_ecu", "snapshot": status["snapshot"],
                      "file": unit["file"], "function": unit["symbol"], "signature": unit["signature"]})
    result["checks"]["live_review_and_provenance"] = run["outcome"] == "CANDIDATES" and bool(run["findings"])
    document = api.request("/analysis-runs/" + run["id"] + "/report?repository=demo_ecu")
    result["checks"]["report_originals"] = [f["original"] for f in document["reviewed_findings"]] == run["findings"]
    result["checks"]["report_citations"] = all(f["current_validation_status"] == "VALID_PROVENANCE" for f in document["reviewed_findings"])
    # Copy the captured run and manifest into a disposable workflow catalog. Tests
    # must not substitute automatic approval for a human's operational decisions.
    config = json.loads((project / ".local/access.json").read_text())
    permissions = Permissions(config)
    token = (project / ".local/demo-token.txt").read_text().strip()
    scope = permissions.authorize(token, "demo_ecu")
    # For Docker the run uses Linux paths/snapshot identity. Evidence source alone
    # is sufficient for a captured workflow fixture, preserving the original IDs.
    source = {}
    for evidence in run["evidence"]:
        if evidence["kind"] == "source":
            lines = source.setdefault(evidence["file"], [])
            while len(lines) < evidence["end_line"]:
                lines.append("")
            lines[evidence["start_line"] - 1:evidence["end_line"]] = evidence["text"].splitlines()
    manifest = {"repository": "demo_ecu", "snapshot": run["snapshot"],
                "source": {file: "\n".join(lines) for file, lines in source.items()}, "chunks": []}
    with tempfile.TemporaryDirectory(prefix="delivery-test-", dir=project / ".local") as directory:
        catalog = Catalog(Path(directory) / "catalog.sqlite3")
        catalog.publish(scope, manifest)
        catalog.save_run(scope, run)
        from threading import Lock
        indexer = Mock(permissions=permissions, catalog=catalog, lock=Lock())
        for original in run["findings"]:
            editable = Finding.model_validate({k: original[k] for k in Finding.model_fields})
            for revision, action in enumerate(("ACCEPTED", "EDITED", "REJECTED")):
                if action == "EDITED":
                    editable.explanation += " Reviewer confirms this remains a candidate diagnosis."
                decide(indexer, token, original["id"], ReviewDecision(repository="demo_ecu", action=action,
                       expected_revision=revision, edited_finding=editable if action == "EDITED" else None, note="Disposable workflow fixture"))
        indexer.catalog = Catalog(catalog.path)
        persisted = report(indexer, token, "demo_ecu", run["id"])
        result["checks"]["persisted_reviewer_decisions"] = all(len(f["history"]) == 3 and f["disposition"] == "REJECTED" for f in persisted["reviewed_findings"])
        result["checks"]["immutable_originals"] = persisted["run"] == run
    result["run_id"] = run["id"]
    result["snapshot"] = status["snapshot"]
    result["model_attempts"] = run.get("model_attempts")
    result["status"] = "passed" if all(result["checks"].values()) else "failed"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--report", type=Path, default=Path(".local/delivery-smoke.json"))
    args = parser.parse_args()
    smoke(args.origin, args.report)
