"""Preserve the approved Checkpoint 2 baseline beside an unchanged-corpus rerun."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.evaluate_review import evaluate


def main(destination):
    project = Path(__file__).resolve().parents[1]
    baseline_path = project / ".local/review-evaluation.json"
    if not baseline_path.exists():
        baseline_path = project / "docs/evaluation/checkpoint2-baseline.json"
    baseline_bytes = baseline_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    misses = [c["function"] for c in baseline["cases"] if c["expected"]["expected_defect"] and not c["correct_defect_found"]]
    positives = [c["function"] for c in baseline["cases"] if c["false_positive"]]
    if set(misses) != {"calculatePressure", "readActivePressure", "activateSession", "doubleFreeSample"} or positives != ["readSensor"]:
        raise ValueError("Approved baseline changed; investigate rather than relabel it")
    if destination.resolve() == baseline_path.resolve():
        raise ValueError("Final evaluation must not overwrite the approved baseline")
    report = evaluate(destination)
    # Keep the historical results even if the new run detects a previous miss.
    report["checkpoint2_baseline"] = {"artifact": str(baseline_path),
        "sha256": hashlib.sha256(baseline_bytes).hexdigest(), "prompt_version": baseline["prompt_version"],
        "metrics": baseline["metrics"], "recorded_misses": misses, "safe_false_positives": positives,
        "limitation": "94.12% precision and 80% recall apply only to this fixed synthetic corpus; not universal model accuracy"}
    report["corpus_integrity"] = {"labels_sha256": hashlib.sha256((project / "tests/fixtures/expected_defects.json").read_bytes()).hexdigest(),
        "source_sha256": {p.relative_to(project / "demo_ecu").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((project / "demo_ecu").rglob("*")) if p.is_file()},
        "demo_rules_sha256": hashlib.sha256((project / "rules/coding_rules.md").read_bytes()).hexdigest()}
    report["settings"] = {"context": 8192, "input_budget": 6144, "output_reserve": 1536, "uncertainty_reserve": 512,
        "temperature": 0, "cpu_embeddings": True, "cppcheck": report["analyzer_baseline"]["version"]}
    report["productivity"] = {"selected_defect_resolution_time": "NOT_MEASURED", "review_throughput": "NOT_MEASURED", "downstream_defect_leakage": "NOT_MEASURED"}
    report["metric_limitations"] = ["Precision is per labeled function, not an exhaustively adjudicated finding-level measure.",
        "Additional diagnoses on already defective functions are not fully labeled.",
        "Citation validity establishes provenance, not semantic correctness or automotive safety certification.",
        "All reviews use demo source without the real project build configuration; analyzer limitations remain visible."]
    metrics = report["metrics"]
    metrics["model_failed_runs"] = sum(r["model_status"] == "failed" for r in report["runs"][:30])
    metrics["analyzer_degraded_runs"] = sum(r["analyzer"]["status"] == "degraded" for r in report["runs"][:30])
    metrics["validated_candidate_count"] = sum(len(r["findings"]) for r in report["runs"][:30])
    metrics["model_failure_rate"] = metrics["model_failed_runs"] / 30
    metrics["malformed_output_rate"] = metrics["malformed_output_runs"] / 30
    metrics["analyzer_failure_rate"] = metrics["analyzer_failed_runs"] / 30
    report["remaining_misses"] = [c["function"] for c in report["cases"] if c["expected"]["expected_defect"] and not c["correct_defect_found"]]
    report["safe_false_positives"] = [c["function"] for c in report["cases"] if c["false_positive"]]
    if baseline_path.read_bytes() != baseline_bytes:
        raise ValueError("Baseline was modified during final evaluation")
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"baseline_preserved": True, "remaining_misses": report["remaining_misses"],
                      "safe_false_positives": report["safe_false_positives"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(".local/final-evaluation.json"))
    args = parser.parse_args()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    main(args.report)
