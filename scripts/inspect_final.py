"""Validate final citations and collect deterministic evidence for manual inspection."""
import argparse
import hashlib
import json
from pathlib import Path

from app.ingestion.chunker import chunks
from app.llm.schemas import Finding, Claim, ModelResponse
from app.validation.evidence_validator import validate


def inspect(destination):
    project = Path(__file__).resolve().parents[1]
    report = json.loads((project / ".local/final-evaluation.json").read_text())
    integrity = report["corpus_integrity"]
    source = {}
    parsed = []
    for file, expected in integrity["source_sha256"].items():
        raw = (project / "demo_ecu" / file).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Evaluation source changed; cannot validate against new source")
        if Path(file).suffix in (".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"):
            text = raw.decode()
            source[file] = text
            from dataclasses import asdict
            parsed.extend(asdict(c) for c in chunks("demo_ecu", report["snapshot"], file, text)[0])
    manifest = {"repository": "demo_ecu", "snapshot": report["snapshot"], "source": source, "chunks": parsed}
    count, references, claims = 0, 0, 0
    for run in report["runs"]:
        response = ModelResponse(outcome=run["outcome"], findings=[Finding.model_validate({k: f[k] for k in Finding.model_fields})
            for f in run["findings"]], claims=[Claim.model_validate(c) for c in run["claims"]], limitations=run.get("model_limitations", []))
        if run["outcome"] not in ("FAILED", "INSUFFICIENT_EVIDENCE"):
            validate(response, {"task": run["mode"], "evidence": run["evidence"]}, manifest)
        else:
            assert not run["findings"] and not run["claims"]
        count += len(run["findings"])
        claims += len(run["claims"])
        references += sum(len(f["evidence"]) for f in run["findings"]) + sum(len(c["evidence"]) for c in run["claims"])
    double_free = next(r for r in report["runs"] if any(f["function"] == "doubleFreeSample" for f in r["findings"]))
    private = project / ".local/final-manual-inspection.txt"
    prompts = report["model_responses"][:10]
    findings = [f for r in report["runs"] for f in r["findings"]][:10]
    private.write_text(json.dumps({"prompts": prompts, "findings": findings,
        "double_free": double_free, "failed_capabilities": [r for r in report["runs"][30:] if r["outcome"] != "ANSWERED"]}, indent=2), encoding="utf-8")
    result = {"status": "passed", "findings_validated": count, "claims_validated": claims,
        "references_validated": references, "invalid_validated_citations": 0,
        "evidence_provenance_validity_rate": 1.0 if references else None,
        "limitation": "Deterministic provenance recheck on this unchanged synthetic corpus; does not prove diagnosis correctness.",
        "manual_inspection_artifact": str(private), "selected_prompts": len(prompts), "selected_findings": len(findings),
        "double_free": {k: double_free.get(k) for k in ("outcome", "model_attempts", "corrective_input_estimate", "input_tokens", "validation_errors")}}
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(".local/final-inspection.json"))
    inspect(parser.parse_args().report)
