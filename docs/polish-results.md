# Guided engineering polish — delivery record

Recorded 4 October 2026. This is a usability and workflow revision under the
frozen Case Study 4 scope. It does not tune model accuracy. AGENTS.md remains
unchanged; PROJECT_PLAN.md only clarifies the authorized Q&A routing correction.

## Delivered behavior

- Masked, explicit Sign in/Sign out; credentials and selected forms/reports stay
  session-local. Credential, access, stale-selection, conflict and dependency
  errors have readable messages and expandable technical details. Writes are
  never automatically retried after an ambiguous timeout.
- Six dark pages, a consistent repository indicator, guided overview cards and
  next actions. Captured index status does not claim dependency health.
- Repository progress with elapsed time, completed/total functions, current
  function and outcomes; duplicate starts disabled during an existing run.
  Completed, interrupted and historical runs remain distinguishable.
- Review / Explain / Ask a Question groups. Exact captured previews precede
  analysis; signatures resolve overloads. Whole-file previews page at 200 lines.
  Q&A now uses `/qa`; analysis prompts, budgets and inference behavior are unchanged.
- Paste or local UTF-8 `.txt`, `.log`, `.xml` diagnostics. Required declared
  origin, optional tool/version, malformed XML and the 6,000-character limit are
  checked before submission. Oversized input is rejected without truncation.
- Pending-first findings with search, category/severity/status filters,
  All statuses, stable selection and lazy loading of the selected detailed report.
- Issue/location/remediation first, nearby citations/rules, plain-language support
  labels and visible coverage warnings. Identical root-cause and explanation
  text is not repeated.
- Readable Edit fields retain location/citations; advanced JSON remains available.
  Accept/Edit/Reject preserve immutable originals, authenticated history,
  backend evidence validation and revision-conflict checks. Original-versus-edited
  comparisons show changed fields and reviewer notes with IST timestamps.
- Self-contained printable HTML for individual/repository reports, plus complete
  JSON. HTML escapes untrusted text, includes citations, coverage, limitations,
  decisions, originals/history and provenance, and loads no scripts or external
  resources. Open locally and use the browser's Print command.

Only original/demo rules are used. The existing MISRA notice is retained exactly;
no licensed MISRA text was downloaded, embedded or reproduced, and no compliance
claim is made. Source remains read-only to the application.

## Verification

The complete unittest suite passed **106 tests in 24.812 seconds**: the 89
pre-existing regressions plus 17 polish tests. These deterministic tests use
controlled model responses and disposable repositories/catalogs; they do not
establish live-model accuracy.

Coverage includes authentication/session clearing, task routing, authorization
before captured-preview storage access, exact paths, overload conflicts,
pagination, changed/deleted historical source, legacy findings compatibility,
lazy details and selection stability, duplicate review prevention, readable
Accept/Edit/Reject, unsupported evidence rejection, revision conflicts and history,
UTF-8/size/XML/adversarial diagnostic input, HTTP error status/no retry, HTML
escaping/content/credential exclusion and historical report compatibility.
Earlier authorization, path-escape, prompt-injection, fabricated-citation, stale
evidence, context-limit and dependency-failure regressions also passed.

Actual authenticated Streamlit AppTest opened all six pages against the local API
and verified sign-out clearing. After rebuilding the Docker deployment, captured
`clampPressure` preview returned original lines 12–14; invalid credentials returned
401. Repository, Q&A and diagnostic reports persisted through container replacement.
API, UI and PostgreSQL were healthy. No operational reviewer decisions were
submitted; all 21 new candidates remain PENDING.

Seventeen protected files passed SHA-256 comparison, including prompts/context,
original guidance, labels, demo source and previous public evaluation artifacts.
No previous metrics or unsuccessful cases were overwritten. The before/after
diff was inspected; there is no Git checkout in this workspace.

Machine-readable results: [polish-verification.json](evaluation/polish-verification.json).

## Live capability demonstrations

| Demonstration | Recorded outcome |
|---|---|
| Repository review `2d2280dd-9cfd-4f2a-b48d-4ac004e2220b` | 7 indexed source/header files; 31/31 functions; 21 candidates across 18 functions; 13 no-supported-finding outcomes; 0 failed/insufficient outcomes; 142.598 seconds. |
| `/qa`, `clampPressure`, `3da9969d-ebbd-4d4f-bedf-eaebda99774d` | ANSWERED, two source-cited observations, 4.766 seconds; persisted report checked. |
| Imported synthetic build log, `e704349b-fb04-4692-82ad-8dcfada2cdaa` | ANSWERED, three log-cited hypotheses, 8.616 seconds; persisted report checked. No build or CI execution. |

The repository demonstration used the unchanged 20-defect/10-safe labeled corpus
and the extra `sensorConnected` function. It recorded 15 true positives, five
misses and one safe-function false positive: **93.75% per-labeled-function
precision and 75% recall on this fixed synthetic corpus only**, matching the
previous corrected v16 demonstration. This is not an accuracy improvement.
Six of the 21 findings have analyzer support; 15 are AI-only candidates under
the analyzer distinction. Rule-based evidence support is a separate measure.

The misses are `calculatePressure`, `readActivePressure`, `activateSession`,
`useFreedSample`, `doubleFreeSample`; `readSensor` remains the safe false positive.
The latter two resource defects produced candidates under the wrong category,
so they remain category-matched evaluation misses. Earlier Checkpoint 2's four
misses, 94.12% precision/80% recall, the Checkpoint 3 result and the failed v15
case remain preserved. The double-free corrective-budget history is not hidden
or reclassified. Citation validity proves provenance, not diagnosis correctness.
Cppcheck 2.10 still reports `missingIncludeSystem` and degraded coverage.
Performance findings, productivity gains and downstream defect leakage are not
demonstrated by this polish pass.

See [live repository results](evaluation/polish-live-results.json),
[Q&A result](demonstrations/polish-qa-result.json), and
[imported-log result](demonstrations/polish-diagnostics-result.json).

Reproduce with a **new** output path, preserving the recorded baseline:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.demo_repository_review --report .local\polish-repeat.json --summary docs\evaluation\polish-repeat.json
```

For Q&A choose Analyze Source > Ask a Question, `src/brake_control.cpp`,
`clampPressure`, then ask: “Explain what clampPressure returns for a negative
value and for a nonnegative value. Cite its captured source.” For diagnostics
choose Build log, `src/diagnostics.cpp`, `uninitializedCounter`, paste/import
`docs/demonstrations/imported-build.log`, declare a synthetic local origin, and
ask: “Explain the reported warning and warnings-as-errors failure with log
citations. Qualify possible causes.” New outcomes/timing may differ; record failures.

## Visual inspection and limits

Desktop 1280×720 and narrow 760×900 views were inspected using a controlled
synthetic visual fixture disconnected from operational writes. Screenshots are
**not** evidence of live inference or a real reviewer decision. Actual
authenticated API/UI checks were performed separately. Navigation, overview,
captured source, completed repository coverage, finding detail, readable editing,
local log upload and printable HTML were inspected. Running progress and duplicate
prevention were exercised through controlled AppTest responses. Temporary
viewport overrides were reset. Physical printing was not performed; print
pagination depends on the browser. The printable report screenshot uses the
actual synthetic demonstration report.

- [Overview](screenshots/polish-overview.jpg)
- [Source preview](screenshots/polish-source.jpg)
- [Repository coverage](screenshots/polish-repository-review.jpg)
- [Finding/editor](screenshots/polish-finding-edit.jpg)
- [Narrow editor](screenshots/polish-narrow.jpg)
- [Imported local log](screenshots/polish-diagnostics.jpg)
- [Printable report](screenshots/polish-report.jpg)

The import screenshot predates the final added help caption clarifying that the
application's 6,000-character limit overrides Streamlit's larger upload-picker
limit. Some source screenshots predate removal of disabled short-preview pagers.
Final code passed the complete regression suite after these small refinements.

Pilot findings/history lists remain bounded to the latest 100 and are labeled.
Summary provenance is NOT_CHECKED until the selected report validates it. Save
reviewer forms before switching pages/editor modes; unsubmitted drafts are not
retained. Diagnostics keeps the existing claim schema: there is no independent
structured-remediation field, and the UI states this explicitly rather than
inventing remediation. No new model, guidance, IAM, profiling, or automation was added.

## Changed files

Modified: `app/main.py`, `ui/client.py`, `ui/streamlit_app.py`,
`scripts/demo_repository_review.py`, `tests/test_delivery.py`,
`tests/test_repository_review.py`, `README.md`, `PROJECT_PLAN.md`,
`docs/case-study4-presentation.md`.

Added: `ui/components.py`, `ui/presentation.py`, `ui/reports.py`,
`tests/test_polish.py`, this record, `docs/evaluation/polish-verification.json`,
`docs/evaluation/polish-live-results.json`,
`docs/demonstrations/polish-qa-result.json`,
`docs/demonstrations/polish-diagnostics-result.json`, and the seven screenshots above.

Private before-copies, diff, full source-bearing reports, generated HTML and
test/service logs remain ignored under `.local`; no credentials were added to
public exports. Operating instructions are in README.md; the updated timed flow
is in [case-study4-presentation.md](case-study4-presentation.md).
