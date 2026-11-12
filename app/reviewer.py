"""Human decisions validate captured evidence, never newly changed source."""
from datetime import datetime, timezone

from app.llm.schemas import Finding, ModelResponse
from app.validation.evidence_validator import validate, InvalidEvidence
from pydantic import ValidationError
from app.review_service import TargetNotFound
from app.support import evidence_support


def report(indexer, token, repository, run_id):
    scope = indexer.permissions.authorize(token, repository)
    with indexer.lock:
        indexer.open_storage(scope)
    rows = indexer.catalog.runs(scope, run_id)
    if not rows:
        raise TargetNotFound("Analysis run unavailable in authorized scope")
    run = rows[0]
    manifest = indexer.catalog.snapshot(scope, run["snapshot"])
    findings = []
    for original in run["findings"]:
        history = indexer.catalog.history(scope, original["id"])
        latest = history[-1] if history else None
        effective = latest["finding"] if latest else original
        try:
            selected = Finding.model_validate({k: effective[k] for k in Finding.model_fields if k in effective})
            validate(ModelResponse(outcome="CANDIDATES", findings=[selected], claims=[], limitations=[]),
                     {"task": run["mode"], "evidence": run["evidence"]}, manifest)
            validity = "VALID_PROVENANCE"
        except (InvalidEvidence, ValidationError, KeyError):
            validity = "REJECTED_BY_CURRENT_VALIDATION"
        findings.append({"original": original, "history": history,
            "disposition": latest["action"] if latest else "PENDING",
            "revision": latest["revision"] if latest else 0,
            "effective_finding": effective, "evidence_support": evidence_support(effective), "current_validation_status": validity})
    return {"report_version": 1, "run": run, "reviewed_findings": findings,
            "notice": "Historical source and reviewer text are untrusted evidence. Citation validation proves provenance; reviewer decisions are not certification."}


def decide(indexer, token, finding_id, request):
    scope = indexer.permissions.authorize(token, request.repository)
    with indexer.lock:
        indexer.open_storage(scope)
    originals = indexer.catalog.findings(scope, finding_id)
    if not originals:
        raise TargetNotFound("Finding unavailable in authorized scope")
    original = originals[0]
    run = indexer.catalog.runs(scope, original["run_id"])[0]
    history = indexer.catalog.history(scope, finding_id)
    if request.action == "EDITED" and request.edited_finding is None:
        raise ValueError("Edit requires a complete finding with validated evidence")
    if request.action != "EDITED" and request.edited_finding is not None:
        raise ValueError("Only Edit may replace finding content")
    effective = request.edited_finding.model_dump() if request.edited_finding else (
        history[-1]["finding"] if history else {k: original[k] for k in Finding.model_fields if k in original})
    if request.action != "REJECTED":
        manifest = indexer.catalog.snapshot(scope, run["snapshot"])
        context = {"task": run["mode"], "evidence": run["evidence"]}
        response = ModelResponse(outcome="CANDIDATES", findings=[Finding.model_validate(effective)], claims=[], limitations=[])
        validate(response, context, manifest)
    decision = {"action": request.action, "user": scope.user,
        "created": datetime.now(timezone.utc).isoformat(), "note": request.note,
        "snapshot": run["snapshot"], "finding": effective, "evidence_support": evidence_support(effective),
        "changed_fields": [k for k in Finding.model_fields if effective.get(k) != (history[-1]["finding"] if history else original).get(k)] if request.action == "EDITED" else [],
        "support": "ANALYZER-SUPPORTED" if any(e["id"].startswith("A") for e in effective["evidence"]) else "AI-ONLY CANDIDATE"}
    return indexer.catalog.save_review(scope, finding_id, decision, request.expected_revision)
