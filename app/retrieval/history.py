"""Optional approved precedent, authorized and kept separate from current source."""
import hashlib
import json


def approved_evidence(indexer, token, repository, manifest, targets):
    scope = indexer.permissions.authorize(token, repository)
    with indexer.lock:
        indexer.open_storage(scope)
    from app.reviewer import report
    selected = {(c["file"], c["symbol"]) for c in targets}
    result = []
    for original in indexer.catalog.approved_findings(scope):
        if (original["file"], original["function"]) not in selected:
            continue
        document = report(indexer, token, repository, original["run_id"])
        entry = next(f for f in document["reviewed_findings"] if f["original"]["id"] == original["id"])
        if entry["disposition"] not in ("ACCEPTED", "EDITED") or entry["current_validation_status"] != "VALID_PROVENANCE":
            continue
        latest = entry["history"][-1]
        old = indexer.catalog.snapshot(scope, original["snapshot"])
        finding = entry["effective_finding"]
        text = json.dumps({"issue": finding["issue"], "explanation": finding["explanation"],
                           "suggested_fix": finding["suggested_fix"], "reviewer_note": latest["note"]}, ensure_ascii=False)
        # The excerpt is bounded and explicitly historical; never relabel an old
        # source quote or analyzer warning as current source/analyzer evidence.
        excerpt = text.encode()[:1000].decode("utf-8", errors="ignore")
        result.append({"id": "H" + hashlib.sha256((original["id"] + str(latest["revision"])).encode()).hexdigest()[:16],
            "kind": "historical", "repository": repository, "snapshot": original["snapshot"],
            "review_snapshot": manifest["snapshot"], "historical_snapshot": original["snapshot"], "file": finding["file"], "function": finding["function"],
            "finding_id": original["id"], "revision": latest["revision"], "disposition": latest["action"],
            "reviewer": latest["user"], "reviewed_at": latest["created"], "start_line": 1, "end_line": 1,
            "source_changed": old["source"].get(finding["file"]) != manifest["source"].get(finding["file"]),
            "text": excerpt, "excerpted": len(excerpt.encode()) < len(text.encode())})
        if len(result) == 2:
            break
    return result
