"""Self-contained, escaped, printable reports; no scripts or remote resources."""
from html import escape
import json
from app.llm.schemas import Finding
from ui.presentation import local_time, OUTCOMES


def text(value):
    return escape(str(value), quote=True)


def paragraph(value):
    return "<p>" + text(value) + "</p>"


def table(rows):
    body = "<table>"
    for key, value in rows:
        label = str(key).replace("_", " ") if "/" not in str(key) else str(key)
        label = label[:1].upper() + label[1:]
        rendered = table(value.items()) if isinstance(value, dict) else text(value)
        body += "<tr><th>" + text(label) + "</th><td>" + rendered + "</td></tr>"
    return body + "</table>"


def finding_body(entry):
    original = entry["original"]
    finding = entry["effective_finding"]
    body = "<article><h3>" + text(finding["issue"]) + "</h3>"
    body += table([(k, finding[k]) for k in ("category", "severity", "file", "function", "start_line", "end_line")])
    body += table([("Reviewer decision", entry["disposition"]), ("Revision", entry["revision"]),
                   ("Evidence support", entry.get("evidence_support", original.get("evidence_support", "AI-ONLY CANDIDATE"))),
                   ("Provenance check", entry.get("current_validation_status", "NOT_CHECKED")), ("Finding ID", original["id"])])
    body += "<h4>Explanation</h4>" + paragraph(finding["explanation"])
    if finding.get("root_cause") and finding["root_cause"] != finding["explanation"]:
        body += "<h4>Possible root cause — hypothesis</h4>" + paragraph(finding["root_cause"])
    if finding.get("security_implication"):
        body += "<h4>Security implication — candidate</h4>" + paragraph(finding["security_implication"])
    body += "<h4>Suggested remediation</h4>" + paragraph(finding["suggested_fix"])
    body += "<h4>Applicable original/demo rules</h4>" + paragraph(", ".join(finding["applicable_rules"]) or "None supplied")
    body += "<h4>Citations</h4>"
    for ref in finding["evidence"]:
        body += paragraph(f'{ref["id"]} · lines {ref["start_line"]}–{ref["end_line"]}') + "<pre>" + text(ref["quote"]) + "</pre>"
    if entry["history"]:
        body += "<h4>Immutable original</h4>" + paragraph(original["issue"]) + paragraph(original["explanation"]) + paragraph(original["suggested_fix"])
        body += "<pre>" + text(json.dumps({k: original[k] for k in Finding.model_fields if k in original}, indent=2, ensure_ascii=False)) + "</pre>"
        body += "<h4>Reviewer history</h4>"
        for revision in entry["history"]:
            body += table([("Action", revision["action"]), ("Reviewer", revision.get("user", "Not recorded")),
                           ("Time", local_time(revision.get("created"))), ("Revision", revision.get("revision", "Not recorded")),
                           ("Changed fields", ", ".join(revision.get("changed_fields", []))),
                           ("Snapshot", revision.get("snapshot", original.get("snapshot", "Not recorded")))])
            body += paragraph(revision.get("note", ""))
            if revision.get("finding"):
                body += "<pre>" + text(json.dumps(revision["finding"], indent=2, ensure_ascii=False)) + "</pre>"
    return body + "</article>"


def analysis_body(document):
    run = document["run"]
    body = "<section><h2>" + text(OUTCOMES.get(run["outcome"], run["outcome"])) + "</h2>"
    body += table([(k, run.get(k, "Not recorded")) for k in ("repository", "snapshot", "mode", "model", "model_digest", "prompt_version", "id")])
    body += table([("Review time", local_time(run["created"])), ("Duration (seconds)", run.get("seconds", "Not recorded")),
                   ("Analyzer", run["analyzer"]["status"]), ("Analyzer version", run["analyzer"].get("version"))])
    body += "<h3>Coverage</h3><pre>" + text(json.dumps(run.get("coverage", {}), indent=2)) + "</pre>"
    body += "<h3>Limitations</h3>" + "".join(paragraph(s) for s in run["limitations"])
    if run.get('code_facts'):
        body += '<h3>Syntax observations — not defect proof</h3>'
        body += ''.join('<pre>' + text(f) + '</pre>' for f in run['code_facts'])
    if run.get('candidate_verifications'):
        body += '<h3>Candidate verification audit</h3>'
        body += paragraph('The original generated allegation is preserved. Verification is another local-model assessment, not certification.')
        body += '<pre>' + text(json.dumps(run['candidate_verifications'], indent=2, ensure_ascii=False)) + '</pre>'
    if run.get('ast_guards'):
        body += '<h3>Deterministic code checks</h3>'
        body += paragraph('Local syntax observations only. Original candidates and effective states are preserved; human review remains required.')
        body += '<pre>' + text(json.dumps(run['ast_guards'], indent=2, ensure_ascii=False)) + '</pre>'
    body += "".join(paragraph("Model interpretation, unverified: " + s) for s in run.get("model_limitations", []))
    for claim in run["claims"]:
        body += "<h3>" + text(claim["kind"]) + "</h3>" + paragraph(claim["text"])
        for ref in claim["evidence"]:
            body += paragraph(f'{ref["id"]} · lines {ref["start_line"]}–{ref["end_line"]}') + "<pre>" + text(ref["quote"]) + "</pre>"
    for entry in document["reviewed_findings"]:
        body += finding_body(entry)
    body += "<h3>Captured evidence</h3>"
    for item in run["evidence"]:
        body += "<h4>" + text(item["kind"] + " · " + item["id"]) + "</h4>"
        fields = ("file", "function", "start_line", "end_line", "origin", "tool", "tool_version", "snapshot", "historical_snapshot",
                  "reviewer", "reviewed_at", "disposition", "source_changed", "source_mapping", "association_verified")
        body += table([(k, item[k]) for k in fields if k in item])
        body += "<pre>" + text(item["text"]) + "</pre>"
    return body + "</section>"


def html_report(document):
    body = "<h1>Secure Code Debugging &amp; Review</h1>"
    body += paragraph("Local/private report. Candidate findings require human review. Evidence support is not a probability of correctness. Citation checks establish provenance, not diagnosis correctness.")
    body += paragraph("Original/demo engineering guidance only; no formal MISRA compliance. Performance observations are static/source-level, not runtime profiling.")
    body += paragraph("This review demonstrates MISRA-oriented and internal coding-standard assistance. Formal MISRA compliance requires approved/licensed standards, qualified tools, and engineering review.")
    body += paragraph("This report describes its recorded source snapshot, which may be historical. Compare it with the active index before applying conclusions to current source.")
    if "repository_review" in document:
        run = document["repository_review"]
        body += "<h2>Repository review</h2>" + table([(k, run[k]) for k in ("repository", "snapshot", "id", "status")])
        body += paragraph(local_time(run["created"])) + "<h3>Summary and coverage</h3>"
        body += table(document["summary"].items()) + table(document["coverage"].items())
        body += "<h3>Limitations</h3>" + "".join(paragraph(s) for s in document["limitations"])
        body += "<h3>Function outcomes</h3>"
        body += table([(r["file"] + " · " + r["function"], r["outcome"]) for r in run["results"]])
        body += "".join(analysis_body(d) for d in document["function_reports"])
    else:
        body += analysis_body(document)
    style = "body{font:15px system-ui,sans-serif;max-width:1050px;margin:30px auto;padding:0 20px;color:#17202a}h1,h2,h3{color:#163c66}table{border-collapse:collapse;width:100%;margin:12px 0}th,td{border:1px solid #c9d2dc;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{width:28%;background:#edf2f7}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f8;padding:12px}article,section{border-top:2px solid #c9d2dc;margin-top:25px;padding-top:12px}@media print{body{margin:0;max-width:none;font-size:11px}h2,h3,h4{break-after:avoid}tr{break-inside:avoid}}"
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>Secure code review report</title><style>' + style + "</style></head><body>" + body + "</body></html>"
