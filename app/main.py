import os
import sqlite3
import psycopg
from chromadb.errors import ChromaError
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from app.analysis.cppcheck import Cppcheck
from app.ingestion.indexer import Indexer
from app.llm.ollama_client import OllamaClient
from app.llm.schemas import DiagnosticRequest, TargetRequest, ReviewDecision
from app.reviewer import decide, report
from app.support import evidence_support
from app.repository_review import RepositoryReview, functions
from app.retrieval.embedder import JinaEmbedder
from app.review_service import ReviewService, TargetNotFound
from app.security.permissions import AccessDenied, Permissions


def create_app(service=None):
    if service is None:
        root = Path(__file__).resolve().parent.parent
        data = Path(os.environ.get("LOCAL_DATA_DIR", str(root / ".local")))
        permissions = Permissions.load(os.environ.get("ACCESS_CONFIG", str(data / "access.json")))
        database_url = os.environ.get("DATABASE_URL")
        if os.environ.get("DATABASE_URL_FILE"):
            database_url = Path(os.environ["DATABASE_URL_FILE"]).read_text().strip()
        quality = os.environ.get('ANALYSIS_QUALITY', 'baseline')
        indexer = Indexer(permissions, data / "data", JinaEmbedder(data / "models" / "jina-code", data / "module-cache"),
                          root / "rules" / "coding_rules.md", database_url, code_aware=quality in ('ast', 'hybrid', 'verified'))
        executable = os.environ.get("CPPCHECK_EXE", str(data / "tools/cppcheck/PFiles/Cppcheck/cppcheck.exe"))
        service = ReviewService(indexer, Cppcheck(executable, data / "analysis"),
            OllamaClient(os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), timeout=120,
                         allow_container_host=os.environ.get("CONTAINER_LOCAL_NETWORK") == "1"), quality=quality,
            guard_policy=os.environ.get('AST_GUARD_POLICY', 'annotation'))
    @asynccontextmanager
    async def lifespan(app):
        yield
        if service.indexer.store:
            service.indexer.store.close()

    app = FastAPI(title="Case Study 4: Secure Code Debugging & Review Assistant", lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.service = service
    repository_review = RepositoryReview(service)

    def credential(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Local bearer credential required")
        return authorization[7:]

    @app.exception_handler(AccessDenied)
    def denied(request, exc):
        return JSONResponse(status_code=401 if str(exc) == "Unknown credential" else 403, content={"detail": str(exc)})

    @app.exception_handler(TargetNotFound)
    def absent(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    def invalid(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    def dependency_failed(request, exc):
        return JSONResponse(status_code=503, content={"outcome": "FAILED", "detail": "Local storage/embedding dependency failed"})

    for exception in (RuntimeError, OSError, sqlite3.Error, psycopg.Error, ChromaError):
        app.add_exception_handler(exception, dependency_failed)

    @app.get("/health")
    def health():
        return {"status": "ok", "scope": "Case Study 4", "dependencies": "checked when requested"}

    @app.post("/repositories/index")
    def index(body: dict, authorization: str | None = Header(default=None)):
        repository = body.get("repository")
        if not isinstance(repository, str):
            raise HTTPException(422, "repository identifier required")
        return service.indexer.index(credential(authorization), repository, body.get('analysis_configuration'))

    @app.get("/repositories")
    def repositories(authorization: str | None = Header(default=None)):
        token = credential(authorization)
        # Authenticate even when no repository registrations exist.
        service.indexer.permissions.identity(token)
        permitted = []
        for repository in service.indexer.permissions.config.get("repositories", {}):
            try:
                service.indexer.permissions.authorize(token, repository)
                permitted.append(repository)
            except AccessDenied:
                continue
        return permitted

    @app.get("/repositories/{repository}/status")
    def status(repository: str, authorization: str | None = Header(default=None)):
        scope = service.indexer.permissions.authorize(credential(authorization), repository)
        with service.indexer.lock:
            service.indexer.open_storage(scope)
            manifest = service.indexer.catalog.current(scope)
            event = service.indexer.catalog.last_index(scope)
        if manifest is None:
            return {"status": "not_indexed"}
        return {"status": "indexed", "snapshot": manifest["snapshot"], "parser_status": manifest["parser_status"],
                "indexed_at": (event or manifest).get("indexed_at"), "scan_seconds": (event or manifest).get("scan_seconds"),
                "function_count": len(functions(manifest)), "scan": manifest["scan"],
                "files": sorted(manifest["source"]), "functions": [
                    {k: c[k] for k in ("file", "symbol", "signature", "start_line", "end_line")}
                    for c in manifest["chunks"] if c["symbol"]]}

    @app.get("/repositories/{repository}/source")
    def source(repository: str, snapshot: str, file: str, function: str | None = None,
               signature: str | None = None, start_line: int | None = Query(default=None, ge=1),
               limit: int = Query(default=200, ge=1, le=200), authorization: str | None = Header(default=None)):
        scope = service.indexer.permissions.authorize(credential(authorization), repository)
        with service.indexer.lock:
            service.indexer.open_storage(scope)
            manifest = service.indexer.catalog.snapshot(scope, snapshot)
        # Exact captured paths only; no filesystem reads or model/retrieval calls.
        if file not in manifest["source"] or not scope.allows(file):
            raise TargetNotFound("Source unavailable in authorized captured snapshot")
        lines = manifest["source"][file].splitlines()
        lower, upper = 1, len(lines)
        if function:
            matches = [f for f in functions(manifest) if f["file"] == file and f["function"] == function
                       and (signature is None or f["signature"] == signature)]
            if len(matches) != 1:
                raise ValueError("Select an unambiguous captured function/signature")
            lower, upper = matches[0]["start_line"], matches[0]["end_line"]
        first = start_line if start_line is not None else lower
        if lines and not lower <= first <= upper:
            raise ValueError("Preview page is outside selected source boundaries")
        last = min(first + limit - 1, upper)
        return {"repository": repository, "snapshot": snapshot, "file": file, "function": function,
                "selection_start": lower if lines else 0, "selection_end": upper, "total_lines": len(lines),
                "start_line": first if lines else 0, "end_line": last if lines else 0,
                "text": "\n".join(lines[first - 1:last]), "has_more": last < upper,
                "next_start_line": last + 1 if last < upper else None,
                "parser_status": manifest["parser_status"].get(file, "unknown")}

    def analysis(body, authorization, mode):
        run = service.analyze(credential(authorization), body, mode)
        return JSONResponse(status_code=503 if run["outcome"] == "FAILED" else 200, content=run)

    @app.post("/review/function")
    def review_function(body: TargetRequest, authorization: str | None = Header(default=None)):
        if not body.function:
            raise HTTPException(422, "function selection required")
        return analysis(body, authorization, "review_function")

    @app.post("/review/file")
    def review_file(body: TargetRequest, authorization: str | None = Header(default=None)):
        if not body.file:
            raise HTTPException(422, "file selection required")
        return analysis(body, authorization, "review_file")

    @app.post("/explain/function")
    def explain_function(body: TargetRequest, authorization: str | None = Header(default=None)):
        if not body.function:
            raise HTTPException(422, "function selection required")
        return analysis(body, authorization, "explain_function")

    @app.post("/explain/module")
    def explain_module(body: TargetRequest, authorization: str | None = Header(default=None)):
        if not body.file:
            raise HTTPException(422, "file selection required")
        return analysis(body, authorization, "explain_module")

    @app.post("/qa")
    def qa(body: TargetRequest, authorization: str | None = Header(default=None)):
        if not body.question.strip():
            raise HTTPException(422, "question required")
        return analysis(body, authorization, "qa")

    @app.post("/diagnostics/interpret")
    def diagnostics(body: DiagnosticRequest, authorization: str | None = Header(default=None)):
        return analysis(body, authorization, "diagnostics")

    @app.post("/review/repository", status_code=202)
    def review_repository(body: TargetRequest, authorization: str | None = Header(default=None)):
        return repository_review.start(credential(authorization), body)

    @app.get("/repository-reviews")
    def repository_reviews(repository: str, authorization: str | None = Header(default=None)):
        token = credential(authorization)
        scope = repository_review.scope(token, repository)
        return [repository_review.get(token, repository, r["id"]) for r in service.indexer.catalog.repository_runs(scope)]

    @app.get("/repository-reviews/{run_id}")
    def repository_progress(run_id: str, repository: str, authorization: str | None = Header(default=None)):
        return repository_review.get(credential(authorization), repository, run_id)

    @app.get("/repository-reviews/{run_id}/report")
    def repository_report(run_id: str, repository: str, authorization: str | None = Header(default=None)):
        return repository_review.document(credential(authorization), repository, run_id)

    @app.get("/findings")
    def findings(repository: str, include_review_state: bool = False, authorization: str | None = Header(default=None)):
        scope = service.indexer.permissions.authorize(credential(authorization), repository)
        with service.indexer.lock:
            service.indexer.open_storage(scope)
        originals = service.indexer.catalog.findings(scope)
        if not include_review_state:
            return originals
        result = []
        for original in originals:
            history = service.indexer.catalog.history(scope, original["id"])
            latest = history[-1] if history else None
            effective = latest["finding"] if latest else original
            result.append({k: effective[k] for k in ("severity", "category", "file", "function", "issue", "applicable_rules")} |
                {"id": original["id"], "run_id": original["run_id"], "snapshot": original["snapshot"],
                 "disposition": latest["action"] if latest else "PENDING", "revision": latest["revision"] if latest else 0,
                 "evidence_support": evidence_support(effective), "validation_status": "NOT_CHECKED"})
        return result

    @app.get("/findings/{finding_id}")
    def finding(finding_id: str, repository: str, authorization: str | None = Header(default=None)):
        scope = service.indexer.permissions.authorize(credential(authorization), repository)
        with service.indexer.lock:
            service.indexer.open_storage(scope)
        rows = service.indexer.catalog.findings(scope, finding_id)
        result = rows[0] if rows else None
        if result is None:
            raise HTTPException(404, "Finding unavailable in authorized scope")
        return result

    @app.get("/analysis-runs")
    def runs(repository: str, authorization: str | None = Header(default=None)):
        scope = service.indexer.permissions.authorize(credential(authorization), repository)
        with service.indexer.lock:
            service.indexer.open_storage(scope)
        return [{k: r[k] for k in ("id", "created", "snapshot", "mode", "outcome")}
                for r in service.indexer.catalog.runs(scope)]

    @app.get("/analysis-runs/{run_id}/report")
    def run_report(run_id: str, repository: str, authorization: str | None = Header(default=None)):
        return report(service.indexer, credential(authorization), repository, run_id)

    @app.post("/findings/{finding_id}/review")
    def review_decision(finding_id: str, body: ReviewDecision, authorization: str | None = Header(default=None)):
        return decide(service.indexer, credential(authorization), finding_id, body)

    @app.get("/approved-findings")
    def approved(repository: str, authorization: str | None = Header(default=None)):
        scope = service.indexer.permissions.authorize(credential(authorization), repository)
        with service.indexer.lock:
            service.indexer.open_storage(scope)
        result = []
        documents = {}
        for original in service.indexer.catalog.approved_findings(scope):
            history = service.indexer.catalog.history(scope, original["id"])
            if history and history[-1]["action"] in ("ACCEPTED", "EDITED"):
                run_id = original["run_id"]
                if run_id not in documents:
                    documents[run_id] = report(service.indexer, credential(authorization), repository, run_id)
                entry = next(f for f in documents[run_id]["reviewed_findings"] if f["original"]["id"] == original["id"])
                result.append({"original": original, "history": history, "latest_review": history[-1],
                               "current_validation_status": entry["current_validation_status"]})
        return result

    return app
