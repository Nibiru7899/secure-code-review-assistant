# Case Study 4 implementation alignment — 4 October 2026

## Delivery status

Implemented the user-requested extension inside the frozen scope. The application
reads authorized C/C++ source and imported engineering evidence; it does not
operate repository development lifecycles. AGENTS.md and PROJECT_PLAN.md already
follow that boundary and remain unchanged. No new framework, inference provider,
model download, official MISRA text, Git workflow, CI execution or automatic fix
was added. This report supplements the preserved checkpoint reports.

The local stack remains FastAPI, Streamlit, Ollama/Qwen2.5-Coder 7b Q4_K_M,
CPU Jina embeddings, embedded persistent Chroma, Tree-sitter, Cppcheck, Pydantic,
PostgreSQL and Docker. Source and model artifacts are mounted read-only. Services
are local; no proprietary source is sent to an external inference service.

## Implemented capability mapping

| Requirement | Implemented behavior and visible workflow |
|---|---|
| Repository integration | Overview → Index/re-index → Review Entire Repository. Deduplicate split function chunks, pin content snapshot, run Cppcheck once and sequentially use the existing per-function pipeline. Persist every outcome and progress; isolate function failures. |
| Debugging and root causes | Detailed finding shows file/function/lines, source/analyzer/rules, explanation reused as a qualified root-cause hypothesis, remediation and limitations. It is not an independent causal proof. |
| Defect/security review | Candidate categories cover pointer, boundary, initialization, return, resource, state, security, performance and control-flow. Security mode and category filtering are visible. No exhaustive-detection claim. |
| Performance investigation | Cppcheck performance severity is normalized as performance; source/static candidates share validation and reports. UI explicitly excludes runtime profiling. The actual demo produced zero performance candidates. |
| Explanation | Analyze Source exposes Function Explanation, Module Summary, Code Q&A, Dependency Summary and Control-Flow Summary. Existing captured-source/header retrieval and citation validation apply. No complete-call-graph claim. |
| Imported diagnostics | Compiler/static/build/runtime/CI evidence can be pasted with declared origin, tool/version and selected snapshot. Text file:line and Cppcheck XML locations are checked and mapped into captured source. Invalid/malformed locations are rejected. Commands are never executed. |
| Rules and coding standards | Existing six original/demo engineering rules remain unchanged. UI displays rule ID, title from body, evidence, relevance and remediation. MISRA-oriented notice is visible; no official rule text, certification or compliance claim. |
| Historical precedent | Retrieve at most two relevant ACCEPTED/EDITED findings for matching file/function after authorization and provenance checks. Preserve old snapshot, revision, authenticated reviewer/time and changed-source flag. Exclude pending/rejected. Current source always takes priority; history is optional and removed first for corrective context. No model training. |
| Consistent pipeline | Authorization → captured source → exact/semantic retrieval → analyzer/internal guidance → bounded local model → schema/citation validation → human review, applied to every analyzable function. |
| Human review | Original AI findings and source remain immutable. Authenticated Accept/Edit/Reject revisions record timestamp, notes, changed fields and validated evidence. Reviewer judgment remains mandatory. |
| Support | Backend STRONG/SUPPORTED/AI-ONLY CANDIDATE levels are derived from source/analyzer/rule support, separate from existing analyzer-supported label. Neither history nor model confidence raises the level. Support is not correctness probability. |
| Reports | Repository JSON includes snapshot/time, files/functions, coverage, analyzer status, all outcomes, root causes/security/rules/performance, counts, timings, evidence/history and current reviewer dispositions. Individual reports remain available. |
| UI | Dark charcoal theme; Overview, Repository Review, Analyze Source, Diagnostics, Findings, History & Reports. Progress, summary cards, severity colors, filters/sorting, selected finding evidence and downloads. Untrusted content uses text/code/JSON, not HTML. |

The exact UI notice is:

> This review demonstrates MISRA-oriented and internal coding-standard assistance. Formal MISRA compliance requires approved/licensed standards, qualified tools, and engineering review.

## Verification evidence

- Final complete suite: **89 passed in 19.143 seconds** (original 75 retained;
  14 added tests). Private log: `.local/alignment-final-regressions.txt`.
- New deterministic tests cover enumeration, split-function deduplication,
  one outcome per unit, analyzer-once reuse, failure isolation, scope denial before
  storage, snapshot pinning across changed/deleted source, parser coverage,
  interrupted restart, history filtering/edits, optional context priority,
  security/performance/support, report aggregation, imported XML mappings and dark
  navigation. Existing authorization/path/injection/stale/citation/budget/failure
  and Accept/Edit/Reject regressions still pass. Mocked quality tests are not
  evidence of real model accuracy.
- Nine isolated real PostgreSQL migration checks pass, including all-ten-table
  copy, representative queries, nonempty-target refusal, interrupted-copy
  rollback, restart, revisions and original immutability. Repository progress and
  indexing-event tables were empty in that isolated migration fixture; actual
  deployed repository persistence was verified separately after API restart.
- All six authenticated pages load against the real local API through Streamlit
  AppTest. Finding detail with retained rule evidence exposed a missing-title
  display error during inspection; fixed using the rule-body title. No actual
  reviewer action was submitted by the development assistant.
- Browser visual inspection confirms the deployed charcoal login, readable text,
  masked credential and local/private banner. Authenticated workflow inspection
  used AppTest; a full authenticated browser screenshot was not captured.
- Docker API/UI/PostgreSQL are healthy. `/repositories/demo_ecu` and `/data/models`
  are read-only mounts. Completed repository JSON matched exactly after API
  restart; snapshot was retained.
- Actual pinned CPU Jina evaluation: **20 fixed queries**, exact lookup **100%**,
  relevant top-3 **100%**, duplicate/stale-active rates **0%**, disposable indexing
  **15.975 s**. Changed/deleted source, idempotency, reopen, denial and offline
  runtime checks pass. These are corpus-specific retrieval measurements.
- Imported synthetic build-log demo returned **ANSWERED**, two cited hypotheses,
  validated `src/diagnostics.cpp:29` mapping to `uninitializedCounter`, in
  **13.984 s**. Persisted run `49c45691-204a-484e-acd5-7e63bce35e0f`.
  No build/compiler/CI command ran. Origin and execution history remain unverified.
  See `docs/demonstrations/alignment-imported-build-result.json`.

Machine-readable checks are in
[case-study4-alignment-verification.json](evaluation/case-study4-alignment-verification.json).

## Actual repository-wide demonstration

Final run `b436f20a-28d4-46a8-8340-630e49620692`, prompt `case4-v16`, snapshot
`4489ceef577d88d9b56d83b98f7bd986f7baad4b11c81b65c1705c9c7c50b104`.
Docker Cppcheck **2.10**, status **degraded** (`missingIncludeSystem`; no supplied
build configuration). This is not the native Cppcheck 2.22 environment.

| Measurement | Recorded result |
|---|---:|
| Discovered entries / indexed C/C++ and headers | 8 / 7 |
| Analyzable functions discovered / reviewed | 31 / 31 |
| Parser failures / unreviewed functions | 0 / 0 |
| Candidate findings / functions with candidates | 21 / 18 |
| Critical / high / medium / low / information | 0 / 17 / 4 / 0 / 0 |
| Null-pointer / boundary / resource / state | 9 / 4 / 2 / 1 |
| Initialization / unchecked-return / security | 2 / 2 / 1 |
| Performance / control-flow | 0 / 0 |
| Analyzer-supported / AI-only candidates | 6 / 15 |
| STRONG / SUPPORTED / AI-ONLY CANDIDATE evidence levels | 6 / 14 / 1 |
| NO_SUPPORTED_FINDING / INSUFFICIENT_EVIDENCE / FAILED | 13 / 0 / 0 |
| Scan / unchanged re-index | 0.050 s / 0.367 s |
| Total review / mean function review | 138.431 s / 4.436 s |
| Functions per minute | 13.436 |
| Processed inside approved scope | 100% of 31 processed functions |
| Validated candidate provenance | 21 / 21 |
| Model citation/schema rejections / max reported input tokens | 0 / 1640 |
| Historical items used / reviewer dispositions | 0 / 21 PENDING |

31 is the actual repository enumeration; the fixed labels cover only 30
functions (20 defective, 10 safe). `sensorConnected` is an extra unlabelled unit.
No labels or source were added/removed to change scores. JSON contains every
case, including unsuccessful cases.

## Fixed-corpus comparison and context investigation

| Recorded run | TP / FN / safe FP | Per-labeled-function precision | Recall | Safe FP rate |
|---|---|---:|---:|---:|
| Preserved Checkpoint 2 native baseline | 16 / 4 / 1 | 94.12% | 80% | 10% |
| Preserved Checkpoint 3 native v14 | 17 / 3 / 1 | 94.44% | 85% | 10% |
| Initial new Docker repository v15 | 12 / 8 / 1 | 92.31% | 60% | 10% |
| Corrected Docker repository v16 | 15 / 5 / 1 | 93.75% | 75% | 10% |

These are fixed synthetic function-level scores, **not universal model accuracy**.
Extra incorrect allegations on already-defective functions are not exhaustively
adjudicated; this is not per-finding precision. Analyzer version/prompt/settings
and run organization differ from the earlier native experiments, so the table
is not a controlled accuracy benchmark or productivity comparison.

The first v15 repository run is retained as
[repository-alignment-v15.json](evaluation/repository-alignment-v15.json), private
full report `.local/repository-live-v15.json`. It reviewed all 31 functions in
151.961 s, with 20 findings and one FAILED `forbiddenStateTransition` review.
Added prompt/schema/title overhead caused the conservative 6144-input estimator
to omit RES-001/STATE-001 guidance. That was observable in saved resource contexts.

Correction: remove duplicate rule-title metadata from prompt, reduce added
instructions, keep the original compact generated-finding wire format and derive
root-cause display from already-validated explanations. Required source is never
truncated. v16 now supplies all six rules for `doubleFreeSample`/`useFreedSample`,
resolves the state-transition validation failure and has zero failed reviews.
The original Checkpoint 2 doubleFree corrective-budget failure and four recorded
misses remain preserved; the earlier native v14 success is not rewritten.

**Remaining v16 misses:** `calculatePressure`, `readActivePressure`,
`activateSession`, `useFreedSample`, `doubleFreeSample`. The model describes double
free/use-after-free but assigns them the null-pointer category with PTR-001,
so they correctly count as resource-class misses. Restoring context did not fix
that semantic classification error. References remain valid; validation cannot
prove category/diagnosis correctness. Do not silently relabel model output.

**Safe false positive:** `readSensor`, still preserved and visible. Previous
semantic caveats (leakingSessionFile guard and copyDiagnostic remediation) remain
in prior reports; a valid citation never guarantees a safe proposed fix.

Final full private JSON: `.local/repository-live-v16.json`; public sanitized
results: [repository-alignment-results.json](evaluation/repository-alignment-results.json).
All original checkpoint reports, demo source, labels and demo rules remain
unchanged. Protected baseline/label/rule hashes are recorded in both run JSONs.

## Remaining limits

- Candidate detector quality remains limited as measured above; human judgment
  is required. No universal accuracy, exhaustive security coverage or safety claim.
- Function-only repository review does not review declarations/global-only
  chunks as separate targets; parser failures and oversized contexts are visible
  coverage limitations. No full call graph, project compilation or runtime profile.
- Background jobs are single-process, sequential local work. Interrupted runs
  persist but do not automatically resume; explicitly start another review.
- Re-indexing after source changes creates a new active snapshot. A running
  repository review remains on its captured snapshot; its results do not describe
  newly edited source. Git metadata is optional and not currently collected.
- Historical retrieval uses latest 100 approved entries and max two relevant
  file/function matches. The live operational demo used none because there were
  no reviewer-approved findings. Inclusion/exclusion/staleness mechanisms were
  tested with disposable authenticated reviewer fixtures, not fabricated approvals.
- Logs/report origin is declared; verified line existence is not verified
  execution. Imported XML support recognizes Cppcheck-style `location` elements;
  arbitrary report formats are not claimed as universally parsed.
- Only original/demo guidance is installed. Official/licensed MISRA support is
  a future conditional capability, not delivered compliance.
- Data access uses the existing local credential/path scope, not enterprise SSO
  or six new role-specific applications. Routine source remains local; encryption
  and production operating controls remain deployment responsibilities.
- **Debug resolution time, defect leakage and real productivity gains are NOT
  MEASURED.** Static performance observations are not speed measurements.
- Structured histories/reports are bounded pilot lists, not an unbounded search
  platform; file/function explanation may report partial context limitations.

## Stakeholder workflows

| User | Same-application workflow |
|---|---|
| Embedded developer | Analyze Source explanations/reviews and Diagnostics root-cause hypotheses. |
| Code reviewer | Findings evidence, rule relevance, Accept/Edit/Reject and immutable history. |
| Technical lead | Repository Review counts, coverage, failures and full JSON export. |
| Cybersecurity engineer | Category/severity filters and source-backed security candidate detail. |
| CI/CD administrator | Diagnostics imported build/CI logs; no pipeline execution. |
| Quality manager | History & Reports, dispositions, preserved evaluation provenance and limitations. |

Use the [exact eight-minute flow](case-study4-presentation.md) for presentation.

## Changed files

The following source/config/test/demo/document files were changed or added in
this alignment task. Private `.local` reports, logs and before-copies are
validation artifacts; generated bytecode and runtime databases are not source
changes. No dependency versions, Docker mounts, fixture labels or demo source
changed.

- [.streamlit/config.toml](../.streamlit/config.toml) — modified
- [README.md](../README.md) — modified
- [app/analysis/cppcheck.py](../app/analysis/cppcheck.py) — modified
- [app/db/database.py](../app/db/database.py) — modified
- [app/ingestion/indexer.py](../app/ingestion/indexer.py) — modified
- [app/llm/context.py](../app/llm/context.py) — modified
- [app/llm/prompts.py](../app/llm/prompts.py) — modified
- [app/llm/schemas.py](../app/llm/schemas.py) — modified
- [app/main.py](../app/main.py) — modified
- [app/repository_review.py](../app/repository_review.py) — added
- [app/retrieval/history.py](../app/retrieval/history.py) — added
- [app/retrieval/retriever.py](../app/retrieval/retriever.py) — modified
- [app/review_service.py](../app/review_service.py) — modified
- [app/reviewer.py](../app/reviewer.py) — modified
- [app/support.py](../app/support.py) — added
- [app/validation/evidence_validator.py](../app/validation/evidence_validator.py) — modified
- [docs/case-study4-alignment.md](../docs/case-study4-alignment.md) — added
- [docs/case-study4-presentation.md](../docs/case-study4-presentation.md) — added
- [docs/demonstrations/alignment-imported-build-result.json](../docs/demonstrations/alignment-imported-build-result.json) — added
- [docs/evaluation/case-study4-alignment-verification.json](../docs/evaluation/case-study4-alignment-verification.json) — added
- [docs/evaluation/repository-alignment-results.json](../docs/evaluation/repository-alignment-results.json) — added
- [docs/evaluation/repository-alignment-v15.json](../docs/evaluation/repository-alignment-v15.json) — added
- [scripts/demo_repository_review.py](../scripts/demo_repository_review.py) — added
- [tests/test_delivery.py](../tests/test_delivery.py) — modified
- [tests/test_repository_review.py](../tests/test_repository_review.py) — added
- [ui/streamlit_app.py](../ui/streamlit_app.py) — modified
