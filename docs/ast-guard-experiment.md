# Deterministic post-candidate guard — controlled experiment

4 October 2026. **Acceptance gate failed: no meaningful quality metric improved. Keep `ANALYSIS_QUALITY=baseline`.** Guarded mode remains experimental. Measurements apply only to the unchanged fixed synthetic corpus, not universal accuracy or formal MISRA compliance.

## What changed

The previous experiment added AST/hybrid context to Qwen and then invoked a second Qwen verifier. That increased false positives and sometimes rejected real defects.

This experiment keeps baseline captured source, chunking, retrieval, guidance, detector prompts, schema, temperature and budgets. Only an already-generated, provenance-valid candidate is checked against narrow local syntax observations. The effective result is validated again before persistence. No extra LLM, embedding, analyzer or source-read workflow is introduced.

Baseline Qwen → existing candidate validation → deterministic AST factual cross-check → effective candidate validation → human review.

Existing Tree-sitter extraction and its source-byte/language cache are reused. Added byte positions and local branch ancestry establish which visible branch contains an access. Cached facts are rebound to the authorized repository/snapshot; no live source paths are read by the guard. This does not establish whole-program dominance or binding.

## Policies and rules

`ANALYSIS_QUALITY=guarded` enables the optional experiment. `AST_GUARD_POLICY=annotation` retains every candidate; `strict` filters only narrowly tested direct local contradictions. The default remains baseline. Use a baseline index; if storage was last indexed by an earlier structural experiment, restore baseline indexing first. No re-index is needed merely to add guarded checks to an existing baseline index.

- **Explicit null guard:** exact pointer parameter, cited dereference/member access, an applicable visible non-null branch, no shadowing or intervening uncertain effects. Strict suppression additionally requires every use of that operand to be guarded and a narrow missing-check allegation. Unrelated branches, aliases, other identifiers and uncertain effects retain the candidate.
- **Repeated release:** corroborates an already-described repeated-release mechanism using the existing conservative same-operand signal and recognized standard operations. Reassignment, reacquisition, unknown intervening calls and shadowed library names prevent corroboration.
- **Access after release:** corroborates an already-described mechanism only for the same exact syntactic resource. No alias inference.
- **Visible initialization:** a direct literal initialization precedes a direct local return, without intervening observations, ambiguous control or shadowing. This deliberately does not implement general definite-assignment analysis.
- **Visible condition:** an exact quoted identifier/field occurs in a relevant captured local condition. This is annotation only; presence of a check does not establish its adequacy.
- **Category consistency:** a described, syntax-supported resource mechanism and an inconsistent model category produce a warning. Categories and citations are never rewritten.

Updates, goto, asm and try syntax are treated conservatively as unsupported. Parser failures retain original candidates with explicit limitations. Facts/signals do not generate findings. Keywords select a possible check; exact operands, cited regions and captured syntax are still required. The only confidence label is `DETERMINISTIC_PATTERN`.

## Fresh baselines and live comparison

Before implementation, the complete suite passed **130 tests in 25.663 seconds**. The unchanged benchmark returned 17 TP, 3 FN and 1 safe FP: 94.44% precision, 85% strict recall and 10% safe FP rate.

After implementation, baseline, Guarded-A and Guarded-B ran sequentially in the same process/environment with the same pinned Qwen/Ollama runtime, native Cppcheck 2.22.0, baseline index/retrieval and unchanged evaluation script/scoring. All used snapshot `8f781c9f82d1bc827b7aff6b2d327d307d01d2ffd248fcbefcc1a4569c0d3a04`.

| Mode | TP / FN / safe FP | Precision | Strict recall | Detection recall | Safe FP rate | Wrong-category mechanism cases |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 17 / 3 / 1 | 94.44% | 85% | 85% | 10% | 0 |
| Guarded-A, annotation | 17 / 3 / 1 | 94.44% | 85% | 85% | 10% | 0 |
| Guarded-B, strict | 17 / 3 / 1 | 94.44% | 85% | 85% | 10% | 0 |

Detection means the expected mechanism was recognized. Additional different diagnoses do not count as detection of a missed expected mechanism. Precision retains the original per-labeled-function scoring; extra diagnoses on defective functions have not all been semantically adjudicated. Failed cases remain in every denominator.

Each guarded run corroborated **one candidate**, warned about **one potential contradiction**, issued **zero category warnings**, and suppressed **zero candidates**. Suppressed true positives and suppressed safe false positives are both zero. No quality result, false positive, false negative or category changed.

## Per-case outcomes

Only metadata changed:

| Function | Baseline result / expected category | Guard observation | Effective result |
|---|---|---|---|
| `useFreedSample` | Candidate / resource | Same captured operand is freed and then dereferenced, lines 32–33 | Retained; strict result unchanged |
| `leakingSessionFile` | Candidates / resource | A candidate's absence-of-check allegation conflicts with the visible `!file` condition at line 7 | Warning only; all candidates retained |

The visible-condition warning does not remove the real resource-leak finding. There is no live category reclassification or suppression. Generic unit fixtures demonstrate strict suppression for locally contradicted null-guard and literal-initialization assertions; those synthetic unit results are not counted as benchmark improvements.

The safe false positive remains **`readSensor`**. Its source visibly returns a nullable pointer; the guard does not invent an unchecked local dereference to establish a contradiction. Remaining misses are **`readActivePressure`**, **`activateSession`**, and **`doubleFreeSample`**. The first two produced no supported candidate; the last failed existing output/citation validation. A post-candidate guard cannot recover a finding that never reaches it.

All other 26 fixed cases remain unchanged. [Machine-readable results](evaluation/guard-results.json) preserve all 30 cases, guard observations and original/effective candidates. Earlier experiments, misses, screenshots and reports remain unchanged.

## Detector and workflow controls

All **31 review generation prompts**, including the corrective request, match byte-for-byte across the three modes. A deterministic integration test compares the entire request payload, including schema/system/options, and retrieved evidence. There are no AST facts in detector context and no hybrid ranking in guarded mode.

Function/module and Q&A prompts also match. Separate diagnostic imports have different `imported_at` timestamps, so the complete 37-generation prompt arrays are not byte-identical. This metadata difference is recorded, not normalized away in the original live artifacts. Diagnostic prompt/template/retrieval code is unchanged.

Capability outcomes are unchanged across modes: module explanation, compiler interpretation and runtime interpretation answered; function explanation, Q&A and imported CI/build-log interpretation returned insufficient evidence. These pre-existing limitations are not presented as successful demonstrations.

Final conservative unsupported-syntax checks, exact-condition metadata and duplicate-warning cleanup were validated by replaying the identical saved baseline candidates through both policies without inference. Both replays again yielded 17 TP/3 FN/1 FP and zero suppression. Replay guard plus validation took 0.0643 seconds for annotation and 0.0605 seconds for strict. The first replay harness tried to parse a `FAILED` run as a model response; it was corrected to retain that failed case unchanged in the same denominator.

## Performance

| Mode | 30-function review | Guard time total / per function | Detector / verifier calls | Review embedding calls | Functions/minute |
|---|---:|---:|---:|---:|---:|
| Baseline | 117.225 s | 0 / 0 | 31 / 0 | 30 | 15.355 |
| Guarded-A | 106.817 s | 0.061851 s / 2.062 ms | 31 / 0 | 30 | 16.851 |
| Guarded-B | 108.998 s | 0.047740 s / 1.591 ms | 31 / 0 | 30 | 16.514 |

All modes made 38 embedding API calls including index initialization and the six capability tasks. Guarding itself made zero embedding calls. The extra detector call is the existing corrective retry, not an AST verifier. Primary generation remains sequential.

Measured guard cost is small: approximately 0.058% of Guarded-A review duration and 0.044% of Guarded-B duration. Faster later total runs are warm-up/cache/runtime variation, not a claimed speedup from adding a guard. Baseline embedding/cache and Cppcheck configuration behavior remain intact; no experimental cache/index policy was promoted into baseline.

## Tests, persistence and reports

Final complete regression: **149 passed in 32.086 seconds**. The 19 new tests consist of 15 guard unit tests and four integration/UI tests. They cover null-branch applicability, exact identifiers, alias uncertainty, release/access patterns, reassignment/reacquisition/shadowing, initialization, condition scope, category warnings, immutable originals, policy behavior, injected comments, CRLF provenance, denied/stale access, identical detector payloads, persistence/history, escaping and Streamlit rendering without additional inference. Existing authorization, previews, indexing/retrieval, diagnostics, Cppcheck, reviewer decisions/conflicts, historical reports and UI tests still pass.

Runs store `original_candidate`, `ast_guard_result`, effective candidate/status and policy separately. Existing finding/reviewer schemas remain compatible. The compact optional **Deterministic code checks** section shows observations and captured lines; technical metadata stays in the existing details expander. Checks describe the original model candidate, not a later reviewer edit. JSON and escaped, script-free printable HTML retain the audit and reviewer disposition.

Examples from actual guarded benchmark runs: [annotation report](demonstrations/guard-guarded-a-report.html), [strict report](demonstrations/guard-guarded-b-report.html). Both retain pending human decisions; no operational findings were accepted automatically.

All **54 protected file hashes** match. Operational history was hashed before and after: 226 analysis runs, 110 findings, zero reviews and five repository-review records. All remain unchanged. The rebuilt local services remain healthy with baseline selected; all six authenticated pages and sign-out pass against the deployed backend.

## Changed-file list and acceptance

Application changes: `app/ingestion/code_facts.py`, new `app/analysis/ast_guard.py`, `app/review_service.py`, `app/main.py`, `ui/components.py`, `ui/reports.py`, `.env.example`, `compose.yaml`, `README.md`.

Verification/docs: `tests/test_ast_guard.py`, `tests/test_guard_integration.py`, `scripts/evaluate_ast_guard.py`, `scripts/replay_ast_guard.py`, this document, new `docs/evaluation/guard-*.json` and `docs/demonstrations/guard-*.html`. No dependency or architecture replacement was added.

Security/provenance, regression, no-additional-inference and small measured guard-cost checks pass. Strict recall, precision and safe FP equal baseline. **The required meaningful quality improvement does not occur, so acceptance fails and baseline stays deployed.** No new FP/FN was introduced in this fixed corpus. Guarded mode remains an explicit experiment.

Remaining limitations: narrow local syntax patterns, no alias or interprocedural analysis, no macro expansion or full compiler semantics, incomplete parser coverage, baseline model/citation failures, existing insufficient explanation/Q&A/CI-log outcomes, and limited corpus size. AST corroboration is not proof of defect correctness. Original/demo guidance and human review remain necessary.

Reproduce with `.venv\Scripts\python.exe -m scripts.evaluate_ast_guard`; this invokes the unchanged fixed evaluation three times in disposable storage and writes new guarded artifacts. `.venv\Scripts\python.exe -m scripts.replay_ast_guard` rechecks the recorded baseline candidates without inference. Native configuration is explicit process environment; `.env.example` is not automatically loaded. Keep baseline selected for ordinary use.

Confirmed: same local Qwen and CPU Jina code embeddings, same baseline detector and retrieval, no second-Qwen verifier, no original-source/label changes, no cloud inference, no automatic fixes, no Git/CI automation and no formal MISRA compliance claim. Stop at this delivery.
