"""Shared evidence, review and export controls for the guided interface."""
import json
import hashlib
from urllib.parse import urlencode, quote
import streamlit as st
import pandas as pd
from app.llm.schemas import Finding
from ui.client import APIError
from ui.presentation import local_time, OUTCOMES, SUPPORT
from ui.reports import html_report

STANDARD_NOTICE = "This review demonstrates MISRA-oriented and internal coding-standard assistance. Formal MISRA compliance requires approved/licensed standards, qualified tools, and engineering review."


def request_error(exc, write=False):
    messages = {401: "Sign-in was not accepted. Check your local access credential.",
                403: "You do not have access to this repository or source selection.",
                404: "This item is not available in your authorized selection.",
                409: "The request conflicts with captured evidence, source selection or reviewer history. Check the details before submitting again.",
                422: "Some fields are invalid. Check your selection and the details below.",
                503: "A local dependency is unavailable. Check the local services before trying again."}
    st.error(messages.get(getattr(exc, "status", None), "The local request could not complete. Check the local API connection."))
    if write and getattr(exc, "status", None) is None:
        st.warning("The request may have reached the server. Check review history before submitting again; it was not retried.")
    with st.expander("Technical details"):
        st.text(str(exc))


def downloads(document, key):
    repository_report = "repository_review" in document
    identifier = document["repository_review" if repository_report else "run"]["id"]
    prefix = "repository" if repository_report else "analysis"
    st.caption("Downloads contain authorized captured source and reviewer history. Keep them private.")
    a, b = st.columns(2)
    a.download_button("Download readable report", html_report(document), file_name=prefix + "-" + identifier + ".html",
                      mime="text/html", key=key + "-html", help="Open locally in a browser. Use its Print command for a paper or PDF copy.")
    b.download_button("Download complete JSON", json.dumps(document, indent=2), file_name=prefix + "-" + identifier + ".json",
                      mime="application/json", key=key + "-json")


def source_preview(api, repository, snapshot, file, unit=None):
    identity = (repository, snapshot, file, (unit or {}).get("symbol"), (unit or {}).get("signature"))
    if st.session_state.get("preview_identity") != identity:
        st.session_state.preview_identity = identity
        st.session_state.preview_start = None
    query = {"snapshot": snapshot, "file": file}
    if unit:
        query.update(function=unit["symbol"], signature=unit["signature"])
    if st.session_state.preview_start is not None:
        query["start_line"] = st.session_state.preview_start
    preview = api.request("/repositories/" + quote(repository, safe="") + "/source?" + urlencode(query))
    with st.expander("Captured source preview", expanded=True):
        st.caption(f'{file} · original lines {preview["start_line"]}–{preview["end_line"]} · read-only')
        st.code("\n".join(f'{preview["start_line"] + i:4} │ {line}' for i, line in enumerate(preview["text"].splitlines())), language="cpp")
        if preview["parser_status"] == "failed":
            st.warning("Parsing was incomplete. Function boundaries are unavailable; file evidence is still captured.")
        if preview["selection_end"] - preview["selection_start"] + 1 > 200:
            left, right = st.columns(2)
            if left.button("Previous lines", disabled=preview["start_line"] <= preview["selection_start"], key="preview-prev"):
                st.session_state.preview_start = max(preview["selection_start"], preview["start_line"] - 200)
                st.rerun()
            if right.button("Next lines", disabled=not preview["has_more"], key="preview-next"):
                st.session_state.preview_start = preview["next_start_line"]
                st.rerun()
        st.caption("This is indexed source, not a live filesystem view. Re-index after editing source outside this application.")


def evidence_panel(run):
    groups = ("Source", "Static analysis", "Engineering rules", "Imported diagnostics", "Approved history")
    for tab, kind in zip(st.tabs(groups), ("source", "analyzer", "rule", "diagnostic", "historical")):
        with tab:
            items = [e for e in run["evidence"] if e["kind"] == kind]
            if not items:
                st.caption("No evidence of this type was supplied.")
            for item in items:
                st.text(f'{item.get("file", item.get("origin", "Demo guidance"))} · lines {item["start_line"]}–{item["end_line"]}')
                st.code(item["text"], language="cpp" if kind == "source" else "text")
                if kind == "diagnostic":
                    st.caption("Declared origin; existence of a source mapping does not verify execution history.")
                    if item.get("source_mapping"):
                        st.dataframe(item["source_mapping"], hide_index=True, use_container_width=True)
                if kind == "historical":
                    st.caption("Approved precedent from " + local_time(item.get("reviewed_at")) + "; current source has priority.")
                st.json({k: v for k, v in item.items() if k != "text"}, expanded=False)


def reviewer_form(api, document, entry, repository):
    finding = entry["effective_finding"]
    identifier = entry["original"]["id"]
    revision = entry["revision"]
    action = st.radio("Decision", ["Accept", "Edit", "Reject"], index=None, horizontal=True, key="action-" + identifier,
                      help="Accept or Edit records your assessment. Reject dismisses the candidate. None of these changes source.")
    advanced = action == "Edit" and st.checkbox("Edit evidence as JSON (advanced)", key="advanced-" + identifier)
    if action == "Edit":
        st.caption("Save your decision before changing pages or editor mode; unsaved form drafts are not retained.")
    current = Finding.model_validate({k: finding[k] for k in Finding.model_fields if k in finding}).model_dump()
    with st.form("decision-" + identifier + "-" + str(revision)):
        edited = dict(current)
        if action == "Edit":
            if advanced:
                raw = st.text_area("Finding JSON", json.dumps(current, indent=2), height=300, key="edit-" + identifier + "-" + str(revision))
                st.caption("Evidence edits must pass the same backend checks. Invented locations or citations are rejected.")
            else:
                prefix = "edit-" + identifier + "-" + str(revision) + "-"
                categories = list(Finding.model_fields["category"].annotation.__args__)
                severities = list(Finding.model_fields["severity"].annotation.__args__)
                a, b = st.columns(2)
                edited["category"] = a.selectbox("Issue category", categories, index=categories.index(current["category"]), key=prefix + "category")
                edited["severity"] = b.selectbox("Severity", severities, index=severities.index(current["severity"]), key=prefix + "severity")
                for field, label, maximum in (("issue", "Issue", 500), ("explanation", "Explanation", 1800),
                    ("root_cause", "Possible root cause (hypothesis)", 1200), ("security_implication", "Security implication, if supported", 1200),
                    ("suggested_fix", "Suggested remediation", 1200)):
                    edited[field] = st.text_area(label, current[field], max_chars=maximum, key=prefix + field)
                rules = sorted({e["id"] for e in document["run"]["evidence"] if e["kind"] == "rule"} | set(current["applicable_rules"]))
                edited["applicable_rules"] = st.multiselect("Applicable supplied rules", rules, default=current["applicable_rules"], key=prefix + "rules")
                st.caption("File, function, lines and citations are retained. Category/rule/analyzer consistency is checked when saved.")
        note = st.text_area("Reviewer note", max_chars=1800, key="note-" + identifier + "-" + str(revision))
        save = st.form_submit_button("Save reviewer decision", disabled=action is None, type="primary")
    if save:
        try:
            body = {"repository": repository, "action": {"Accept": "ACCEPTED", "Edit": "EDITED", "Reject": "REJECTED"}[action],
                    "expected_revision": revision, "note": note}
            if action == "Edit":
                body["edited_finding"] = json.loads(raw) if advanced else edited
            api.request("/findings/" + identifier + "/review", body)
            st.session_state.report = api.request("/analysis-runs/" + document["run"]["id"] + "/report?" + urlencode({"repository": repository}))
            st.session_state.saved_decision = "Reviewer decision saved. Source was not changed."
            st.rerun()
        except APIError as exc:
            request_error(exc, write=True)
        except ValueError as exc:
            st.error("The edited finding was not submitted. Check its JSON.")
            st.text(str(exc))


def show_report(api, document, repository, active_snapshot=None, detail_id=None):
    run = document["run"]
    if active_snapshot and run["snapshot"] != active_snapshot:
        st.warning("Historical source version: this result does not describe the active index. Review decisions retain original evidence.")
    st.subheader(OUTCOMES.get(run["outcome"], run["outcome"]))
    st.caption(local_time(run["created"]) + " · " + run["mode"].replace("_", " "))
    if run["outcome"] in ("FAILED", "INSUFFICIENT_EVIDENCE"):
        st.warning("No supported conclusion was established. Check coverage and limitations before trying again.")
    elif run["outcome"] == "NO_SUPPORTED_FINDING":
        st.info("No supported candidate was returned for this evidence. This does not establish that the code is safe.")
    analyzer = run["analyzer"]
    if analyzer["status"] in ("unavailable", "failed", "degraded"):
        st.warning("Static-analysis coverage is limited (" + analyzer["status"] + "). Human assessment is still required.")
    if any("omitted" in limitation.casefold() or "parser fallback" in limitation.casefold() for limitation in run["limitations"]):
        st.warning("Some evidence coverage is limited. Review Coverage and limitations before making a decision.")
    entries = [e for e in document["reviewed_findings"] if detail_id is None or e["original"]["id"] == detail_id]
    for entry in entries:
        f = entry["effective_finding"]
        with st.container(border=True):
            st.badge(f["severity"].upper(), color={"critical":"red", "high":"red", "medium":"orange", "low":"blue", "information":"gray"}[f["severity"]])
            st.subheader(f["issue"])
            st.text(f'{f["file"]}:{f["start_line"]}–{f["end_line"]} · {f["function"]}')
            st.caption(f["category"].replace("-", " ").title() + " · " + entry["disposition"].replace("PENDING", "Awaiting decision").title())
            st.markdown("**Suggested remediation**")
            st.text(f["suggested_fix"])
            st.markdown("**Why this was raised**")
            st.text(f["explanation"])
            if f.get("root_cause") and f["root_cause"] != f["explanation"]:
                st.caption("Possible root cause · hypothesis")
                st.text(f["root_cause"])
            if f.get("security_implication") and f["security_implication"] != f["explanation"]:
                st.caption("Security implication · candidate")
                st.text(f["security_implication"])
            support = entry.get("evidence_support", entry["original"].get("evidence_support", "AI-ONLY CANDIDATE"))
            st.caption(SUPPORT.get(support, support) + ". Support is not a probability of correctness.")
            if entry.get("current_validation_status") == "REJECTED_BY_CURRENT_VALIDATION":
                st.error("This candidate fails current citation checks. Accept is blocked by the backend; correct the evidence or reject it.")
            st.caption("Cited evidence")
            for ref in f["evidence"]:
                st.text(f'{ref["id"]} · lines {ref["start_line"]}–{ref["end_line"]}')
                st.code(ref["quote"], language="cpp" if ref["id"].startswith(("S", "R")) else "text")
            if f["category"] == "performance":
                st.info("Static/source-level observation. No runtime profiling or measured speedup.")
            for rule in run["evidence"]:
                if rule["kind"] == "rule" and rule["id"] in f["applicable_rules"]:
                    title = next((line.removeprefix("Title: ") for line in rule["text"].splitlines() if line.startswith("Title: ")), "Internal guidance")
                    with st.expander(rule["id"] + " · " + title):
                        st.code(rule["text"], language="text")
                        st.text("Candidate relevance: " + f["explanation"])
            with st.expander("Original finding and decision history"):
                if not entry["history"]:
                    st.caption("No reviewer decision yet.")
                for action in entry["history"]:
                    st.text(action["action"].title() + " · " + action.get("user", "Reviewer") + " · " + local_time(action.get("created")))
                    st.text(action.get("note", ""))
                    changed = action.get("changed_fields", [])
                    if changed:
                        st.dataframe([{"field": k, "original": str(entry["original"].get(k, "")), "revision": str(action["finding"].get(k, ""))} for k in changed], hide_index=True)
                st.json({"original": entry["original"], "history": entry["history"]}, expanded=False)
            st.markdown("**Your review decision**")
            reviewer_form(api, document, entry, repository)
    if run["claims"]:
        st.markdown("**Interpretation and possible causes**" if run["mode"] == "diagnostics" else "**Cited explanation**")
        for claim in run["claims"]:
            st.caption("Hypothesis" if claim["kind"] == "hypothesis" else "Observed in supplied evidence")
            st.text(claim["text"])
            for ref in claim["evidence"]:
                with st.expander("Citation · " + ref["id"] + " · line " + str(ref["start_line"])):
                    st.code(ref["quote"], language="text")
        if run["mode"] == "diagnostics":
            st.caption("No separate structured remediation is returned by the diagnostic schema. Assess any recommendations within the cited interpretation.")
    with st.expander("Coverage and limitations", expanded=run["outcome"] in ("FAILED", "INSUFFICIENT_EVIDENCE")):
        for limitation in run["limitations"]:
            st.text(limitation)
        for limitation in run.get("model_limitations", []):
            st.text("Model interpretation (unverified): " + limitation)
        st.json(run.get("coverage", {}))
    with st.expander("All supplied evidence"):
        evidence_panel(run)
    if run.get('candidate_verifications'):
        with st.expander('Candidate verification audit'):
            st.caption('Local-model support, contradiction and category checks. Original allegations are preserved; these decisions are not certification.')
            for record in run['candidate_verifications']:
                st.text(record['result'])
                st.text(record['verifier_result'].get('reason', 'No supported explanation'))
                st.json(record)
    if run.get('ast_guards'):
        with st.expander('Deterministic code checks'):
            st.caption('Local syntax checks, not proof of safety or defect correctness. Original candidates are retained.')
            for record in run['ast_guards']:
                st.text(record['original_candidate']['issue'])
                st.caption(record['ast_guard_result']['guard_status'].replace('_', ' ').title() + ' · ' + record['effective_status'].replace('_', ' ').title())
                for check in record['ast_guard_result']['checks']:
                    st.text(check['observation'])
                    for ref in check['source_lines']:
                        st.caption('Captured lines ' + str(ref['start_line']) + '–' + str(ref['end_line']))
                        st.code(ref['quote'], language='cpp')
    with st.expander("Technical run details"):
        st.json({k: run.get(k) for k in ("id", "repository", "snapshot", "created", "model", "model_digest", "prompt_version", "seconds", "input_tokens", "output_tokens")})
        st.json(analyzer)
        if run.get('ast_guards'):
            st.caption('Technical AST check metadata')
            st.json(run['ast_guards'])
        if run.get('code_facts'):
            st.caption('Syntax observations, not defect proof')
            for facts in run['code_facts']: st.code(facts, language='text')
            st.json({k: run.get(k) for k in ('quality_pipeline', 'code_context_version', 'retrieval_ranking', 'retrieval_seconds', 'primary_model_calls', 'primary_generation_seconds', 'verifier_metrics')})
    downloads(document, "run-" + run["id"] + (detail_id or ""))


def findings_table(api, rows, repository, key, active_snapshot=None):
    if not rows:
        st.info("No candidates have been recorded in this selection. Start a source or repository review; empty results do not establish safety.")
        return
    a, b = st.columns([2, 1])
    search = a.text_input("Search findings", placeholder="Issue, file or function", key=key + "-search").casefold()
    disposition = b.selectbox("Review status", ["Awaiting decision", "All statuses", "Accepted", "Edited", "Rejected"], key=key + "-status")
    c, d, e = st.columns(3)
    categories = c.multiselect("Category", sorted({r["category"] for r in rows}), key=key + "-categories")
    severity = d.multiselect("Severity", ["critical", "high", "medium", "low", "information"], key=key + "-severity")
    sort = e.selectbox("Sort by", ["severity", "category", "file", "function", "disposition"], key=key + "-sort")
    state = {"Awaiting decision":"PENDING", "Accepted":"ACCEPTED", "Edited":"EDITED", "Rejected":"REJECTED"}.get(disposition)
    filtered = [r for r in rows if (not state or r["disposition"] == state) and (not categories or r["category"] in categories)
        and (not severity or r["severity"] in severity) and search in " ".join(str(r[k]) for k in ("issue", "file", "function")).casefold()]
    order = {"critical":0, "high":1, "medium":2, "low":3, "information":4}
    filtered.sort(key=lambda r: order[r[sort]] if sort == "severity" else r[sort])
    st.caption(f"Showing {len(filtered)} of {len(rows)} candidates in this loaded selection. Choose All statuses to include reviewed findings.")
    if not filtered:
        st.info("No findings match. Clear search/filters or choose All statuses.")
        return
    display = [{"Severity":r["severity"], "Category":r["category"], "Function":r["function"], "File":r["file"], "Issue":r["issue"],
                "Evidence support":SUPPORT.get(r.get("evidence_support"), "Source-backed AI candidate"), "Decision":r["disposition"]} for r in filtered]
    colors = {"critical":"#F87171", "high":"#F87171", "medium":"#FBBF24", "low":"#60A5FA", "information":"#9CA3AF"}
    ids = [r["id"] for r in filtered]
    frame = pd.DataFrame(display).style.map(lambda v: "color:" + colors[v], subset=["Severity"])
    table_identity = hashlib.sha256("|".join(ids).encode()).hexdigest()[:12]
    event = st.dataframe(frame, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", key=key + "-table-" + table_identity)
    selected_key = key + "-detail"
    if st.session_state.get(selected_key) not in ids:
        st.session_state[selected_key] = ids[0]
    selection = event.selection.rows
    # React only to a new row selection, not an old dataframe event after sorting.
    marker = (tuple(ids), tuple(selection))
    if selection and selection[0] < len(ids) and st.session_state.get(key + "-selection") != marker:
        st.session_state[selected_key] = ids[selection[0]]
    st.session_state[key + "-selection"] = marker
    labels = {r["id"]: f'Result {i + 1} · {r["function"]} · {r["issue"]}' for i, r in enumerate(rows)}
    selected = st.selectbox("Open finding", ids, key=selected_key, format_func=labels.get)
    run_id = next(r["run_id"] for r in filtered if r["id"] == selected)
    document = api.request("/analysis-runs/" + run_id + "/report?" + urlencode({"repository": repository}))
    show_report(api, document, repository, active_snapshot, detail_id=selected)
