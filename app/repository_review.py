"""Sequential bounded reviews of every captured function, with persistent progress."""
from collections import Counter
from datetime import datetime, timezone
from time import perf_counter
import threading
import uuid

from app.llm.schemas import TargetRequest
from app.reviewer import report
from app.review_service import TargetNotFound, MODEL, DIGEST
from app.llm.prompts import TEMPLATE_VERSION


def functions(manifest):
    selected = {}
    for chunk in manifest["chunks"]:
        if chunk["symbol"]:
            key = (chunk["file"], chunk["symbol"], chunk["signature"])
            if key not in selected:
                selected[key] = {"file": key[0], "function": key[1], "signature": key[2],
                                 "start_line": chunk["start_line"], "end_line": chunk["end_line"]}
            else:
                selected[key]["end_line"] = max(selected[key]["end_line"], chunk["end_line"])
    return [selected[key] for key in sorted(selected)]


class RepositoryReview:
    def __init__(self, service):
        self.service = service
        self.indexer = service.indexer
        self.jobs = set()
        self.lock = threading.Lock()

    def scope(self, token, repository):
        scope = self.indexer.permissions.authorize(token, repository)
        with self.indexer.lock:
            self.indexer.open_storage(scope)
        return scope

    def start(self, token, request, background=True):
        scope = self.scope(token, request.repository)
        manifest = self.indexer.catalog.current(scope)
        if manifest is None or manifest["snapshot"] != request.snapshot:
            raise ValueError("Select the active captured snapshot before repository review")
        units = functions(manifest)
        if not units:
            raise ValueError("No analyzable captured functions; parser/file coverage is incomplete")
        with self.lock:
            existing = self.indexer.catalog.repository_runs(scope)
            if any(r["id"] in self.jobs for r in existing):
                raise ValueError("A repository review is already running in this scope")
            run = {"id": str(uuid.uuid4()), "repository": request.repository, "snapshot": request.snapshot,
                "user": scope.user, "created": datetime.now(timezone.utc).isoformat(), "status": "RUNNING",
                "current_function": None, "seconds": 0, "functions": units, "results": [],
                "files": sorted(manifest["source"]), "scan": manifest["scan"],
                "indexed_at": manifest.get("indexed_at"), "scan_seconds": manifest.get("scan_seconds"),
                "parser_status": manifest["parser_status"], "analyzer": None,
                "limitations": ["Function coverage only; declarations/global initialization and parser-fallback files are not reviewed as functions.",
                    "No complete call graph, runtime profiling, compliance certification or exhaustive defect detection.",
                    "Current source takes priority over optional untrusted approved historical precedent."]}
            event = self.indexer.catalog.last_index(scope) or {}
            run["indexed_at"] = event.get("indexed_at", run["indexed_at"])
            run["scan_seconds"] = event.get("scan_seconds", run["scan_seconds"])
            self.indexer.catalog.save_repository_run(scope, run)
            self.jobs.add(run["id"])
        if background:
            threading.Thread(target=self.execute, args=(token, scope, manifest, run), daemon=True).start()
        else:
            self.execute(token, scope, manifest, run)
        return {"id": run["id"], "status": run["status"], "functions_discovered": len(units), "snapshot": run["snapshot"]}

    def execute(self, token, scope, manifest, run):
        started = perf_counter()
        try:
            run["analyzer"] = self.service.analyzer.run(manifest)
            for unit in run["functions"]:
                run["current_function"] = unit["file"] + " :: " + unit["function"]
                self.indexer.catalog.save_repository_run(scope, run)
                step = perf_counter()
                try:
                    child = self.service.analyze(token, TargetRequest(repository=run["repository"], snapshot=run["snapshot"],
                        file=unit["file"], function=unit["function"], signature=unit["signature"]),
                        "review_function", captured_manifest=manifest, captured_analyzer=run["analyzer"])
                except Exception:
                    # Persist a failed unit without leaking exception bodies or
                    # treating failure as a clean review. Continue other units.
                    child = {"id": str(uuid.uuid4()), "created": datetime.now(timezone.utc).isoformat(),
                        "repository": run["repository"], "snapshot": run["snapshot"], "user": scope.user,
                        "mode": "review_function", "outcome": "FAILED", "findings": [], "claims": [], "evidence": [],
                        "model": MODEL, "model_digest": DIGEST, "prompt_version": TEMPLATE_VERSION,
                        "model_status": "failed", "validation_rejections": 0, "analyzer": run["analyzer"],
                        "seconds": round(perf_counter() - step, 3),
                        "limitations": ["Function review failed; no supported conclusion. Other captured functions continue."]}
                    self.indexer.catalog.save_run(scope, child)
                run["results"].append(dict(unit, run_id=child["id"], outcome=child["outcome"], seconds=child["seconds"]))
                run["seconds"] = round(perf_counter() - started, 3)
                self.indexer.catalog.save_repository_run(scope, run)
            run["status"] = "COMPLETED"
        except Exception:
            run["status"] = "INTERRUPTED"
            run["limitations"].append("Repository run interrupted; unprocessed functions are not claimed as reviewed.")
        finally:
            run["seconds"] = round(perf_counter() - started, 3)
            run["current_function"] = None
            try:
                self.indexer.catalog.save_repository_run(scope, run)
            finally:
                with self.lock:
                    self.jobs.discard(run["id"])

    def get(self, token, repository, run_id):
        scope = self.scope(token, repository)
        rows = self.indexer.catalog.repository_runs(scope, run_id)
        if not rows:
            raise TargetNotFound("Repository run unavailable in authorized scope")
        run = rows[0]
        with self.lock:
            live = run_id in self.jobs
        if run["status"] == "RUNNING" and not live:
            run["status"] = "INTERRUPTED"
            run["limitations"].append("Process restarted; remaining functions were not reviewed. Start a new explicit review.")
            self.indexer.catalog.save_repository_run(scope, run)
        return run

    def document(self, token, repository, run_id):
        run = self.get(token, repository, run_id)
        documents = [report(self.indexer, token, repository, r["run_id"]) for r in run["results"]]
        entries = [entry for d in documents for entry in d["reviewed_findings"]]
        findings = [e["effective_finding"] for e in entries]
        n = len(run["results"])
        counts = Counter(r["outcome"] for r in run["results"])
        summary = {"files_scanned": run["scan"]["files_discovered"], "files_indexed": len(run["files"]),
            "functions_discovered": len(run["functions"]), "functions_reviewed": n,
            "candidate_findings": len(findings), "functions_with_candidates": counts["CANDIDATES"],
            "severity": {s: sum(f["severity"] == s for f in findings) for s in ("critical", "high", "medium", "low", "information")},
            "category": {c: sum(f["category"] == c for f in findings) for c in ("null-pointer", "boundary", "resource", "state", "initialization", "unchecked-return", "security", "performance", "control-flow")},
            "outcomes": {s: counts[s] for s in ("CANDIDATES", "NO_SUPPORTED_FINDING", "INSUFFICIENT_EVIDENCE", "FAILED")},
            "analyzer_supported": sum(e["original"]["support"] == "ANALYZER-SUPPORTED" for e in entries),
            "ai_only_candidates": sum(e["original"]["support"] == "AI-ONLY CANDIDATE" for e in entries),
            "evidence_support": dict(Counter(e["evidence_support"] for e in entries)),
            "reviewer_dispositions": dict(Counter(e["disposition"] for e in entries)),
            "total_seconds": run["seconds"], "mean_function_seconds": sum(r["seconds"] for r in run["results"]) / n if n else None,
            "functions_per_minute": n * 60 / run["seconds"] if run["seconds"] else None,
            "insufficient_evidence_rate": counts["INSUFFICIENT_EVIDENCE"] / n if n else None,
            "failed_review_rate": counts["FAILED"] / n if n else None,
            "processed_inside_approved_scope_percent": 100 if n else None,
            "debug_resolution_time": "NOT MEASURED", "defect_leakage": "NOT MEASURED"}
        histories = [e for d in documents for e in d["run"]["evidence"] if e["kind"] == "historical"]
        return {"report_version": 2, "repository_review": run, "summary": summary,
            "coverage": {"reviewed": n, "unreviewed": len(run["functions"]) - n,
                "parser_failures": [f for f, s in run["parser_status"].items() if s == "failed"]},
            "function_reports": documents, "historical_evidence_used": histories,
            "security_observations": [f for f in findings if f["category"] == "security" or f.get("security_implication")],
            "performance_observations": [f for f in findings if f["category"] == "performance"],
            "coding_rule_findings": [f for f in findings if f["applicable_rules"]],
            "candidate_root_causes": [{"file": f["file"], "function": f["function"], "hypothesis": f.get("root_cause") or f["explanation"]} for f in findings],
            "limitations": list(dict.fromkeys(run["limitations"] + [l for d in documents for l in d["run"]["limitations"]])),
            "notice": "Evidence support is not a probability of correctness. Performance observations are static/source-level; no profiling. Human review is mandatory."}
