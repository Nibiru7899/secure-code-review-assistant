# Analysis-quality delivery — 4 October 2026

**Decision: keep `ANALYSIS_QUALITY=baseline`.** The requested code-aware pipeline is implemented and measured, but its finding-quality gate failed. `ast`, `hybrid` and `verified` remain explicit experimental modes. The deployed application uses the previous analysis behavior. Retrieval and cache improvements do not establish better defect diagnosis.

All measurements below concern the unchanged local synthetic corpus. They are not universal model accuracy, automotive safety certification or formal MISRA compliance. Precision is the existing per-labeled-function metric; extra findings on defective functions have not all been semantically adjudicated.

## 1. Architecture before and after

Before: authorized captured source → function chunks → exact target plus Jina/Chroma neighbors → Cppcheck/demo guidance → Qwen → schema/provenance validation → human review.

Experimental: authorized captured source → Tree-sitter facts → exact target and syntactic symbol context → identifier/vector ranking → Cppcheck/demo guidance → compact facts/source context → Qwen detector → selective same-Qwen verifier → schema/provenance validation → human review.

Identifiers, signatures, scopes and line references have exact meaning. Semantic similarity cannot establish a call relationship. Embeddings supplement structural evidence; they do not determine program structure. [Implementation details](code-aware-analysis.md) describe the boundaries.

## 2. Changed files

Modified:

- `app/ingestion/chunker.py`, `app/ingestion/indexer.py`: opt-in complete function units, captured facts, cache and timing metadata.
- `app/retrieval/retriever.py`, `app/llm/context.py`: opt-in structural retrieval and bounded source/facts context.
- `app/review_service.py`: quality-mode selection, detector/verifier audit and measurements.
- `app/analysis/cppcheck.py`, `app/main.py`: safe optional analysis configuration and explicit experimental mode.
- `ui/components.py`, `ui/reports.py`: existing detail expanders and escaped reports expose new audit data; no UI redesign.
- `.env.example`, `compose.yaml`, `README.md`: baseline default, configuration and documentation.

Added:

- `app/ingestion/code_facts.py`, `app/retrieval/code_retrieval.py`, `app/retrieval/embedding_cache.py`.
- `app/analysis/configuration.py`, `app/analysis/candidate_verifier.py`.
- `tests/test_code_quality.py`.
- `scripts/evaluate_code_quality.py`, `scripts/evaluate_code_retrieval.py`, `scripts/demonstrate_code_quality.py`.
- This report, `docs/code-aware-analysis.md`, new `docs/evaluation/quality-*.json` and `docs/demonstrations/quality-*.html` artifacts. The complete artifact inventory is in [quality-results.json](evaluation/quality-results.json).

No reviewed original source, fixture labels, original detector prompt module, unchanged evaluation script, earlier screenshots/reports or operational history were modified. All 30 protected artifact hashes checked equal their pre-change values. Operational rows remain unchanged: 226 analysis runs, 110 findings and zero reviewer actions. Development has no Git checkout; no repository/branch was created.

## 3–4. Facts and conservative signals

Facts include qualified identity/signature/return type, scope, parameter type and pointer/reference syntax, local declarations and initialization presence, conditions/loops/switches, calls and visible receivers, returns/early returns, assignments, pointer operations, null comparisons and resource operations. Each observation carries captured text and original line ranges. Packages carry repository, snapshot, file/content hash, schema, parser and grammar versions.

Signals cover possible repeated release, access after release, nullable returns, pointer-parameter use, visible guards, a narrow uninitialized-return pattern and ignored results for narrowly recognized operations. They are observations, never confirmed findings. Standard operations require matching captured standard headers and no visible name shadowing; arbitrary user functions named `free` do not acquire library semantics. Intervening assignments, reacquisition, declaration or control transfer suppress simple repeated-release signals.

## 5–6. Retrieval and caching

The exact selected source is mandatory. Unique syntactic local callees, captured includes, associated headers and unique visible types supply structural context. Related candidates rank by structural tier, then weighted reciprocal ranks: identifier weight 2, vector weight 1, constant 20, stable source-location tie breaking. Explicit symbols outrank vague similarity; ordinary prose retains vector fallback. Queries incorporate concise signatures, identifiers and calls. Inclusion reasons remain visible.

Complete functions are retained in structural mode. Required source/facts cannot silently disappear when context is tight; oversized required evidence fails explicitly. Optional history is discarded before current source. Oversized embedding units use bounded identifier summaries only for supplementary vectors.

Jina stays normalized, batched and CPU-local. Content/scope/repository/model hashes key the persistent embedding cache; unchanged vectors are reused without bypassing active-snapshot publication. Deleted source stays out of active retrieval. Parser facts have a bounded source-byte/grammar cache and are rebound to authorized snapshots.

## 7–8. Cppcheck and verification

Optional captured configuration supports bounded include paths, defines, standard, platform and imported compilation-database text. Only supported literal options enter Cppcheck's isolated captured-source directory. Compilation commands remain inert data. External/out-of-scope paths and unsafe options are rejected. Default analysis retains degraded-coverage warnings; `PROJECT_CONFIGURATION` does not guarantee complete build coverage.

The same Qwen verifies candidate findings only. It separately assesses support, source contradiction and category, returning strict `CONFIRM`, `RECLASSIFY`, `REJECT` or `INSUFFICIENT`. Originals, decisions and effective candidates are stored separately; historical records are untouched. Reclassification must be explicit and provenance-valid. No live final candidate was reclassified; deterministic tests cover that path.

Verifier reasons and effective findings reuse citation validation. A discovered mapping bug checked verifier prose against only a source range's first line. The correction validates against its supplied captured range, without fabricating quotes or relaxing validation. Ranges exceeding the existing 1,800-character citation limit fail explicitly. Detector task directives are excluded from verifier inputs; source-grounded assessment precedes its decision.

## 9. Regression and operational checks

- Frozen original suite: **108 passed**, 54.125 seconds.
- Final full suite: **130 passed**, 27.301 seconds, including 22 new deterministic tests. Test duration is not an application speed benchmark.
- Existing authorization, path escape, prompt injection, citation, stale snapshot, reviewer conflict/history, diagnostics, reports and UI regressions pass. New tests cover facts/signals, structural/lexical ranking, vector fallback, cache scope/change/deletion, budget rejection, verifier decisions/citations/immutable originals, safe configuration and inert imported commands.
- All six signed-in pages and sign-out passed Streamlit AppTest against the deployed backend.
- Live read-only API checks returned 401 for invalid credentials, 403 for unregistered repository, 404 for path escape and 409 for unavailable captured snapshot.
- All seven deployed captured-source previews and all 31 function boundaries match original local files. The three rebuilt Docker services are healthy with baseline selected.
- The final experimental original-repository review completed 31/31 functions. All **25 published candidates** have valid provenance; **35 source quotes** were compared with original files. This verifies provenance, not diagnosis correctness. Decisions remain pending.
- The demonstration driver's post-run assertion initially accessed `results` on the compact start response and raised `KeyError` after writing the completed reports. It now checks the full report. The corrected assertion was verified against all 31 saved completed reports; inference was not repeated for this harness-only correction. The original error log is retained.

## 10. Retrieval and indexing measurements

The same 20 fixed retrieval questions were retained. The vector-related control still includes required exact targets; it is not a vector-only target selector.

| Mode | Exact target | Relevant top-k | Syntactic call-context recall | Mean retrieval |
|---|---:|---:|---:|---:|
| Vector-related control | 100% | 100% | 50% | 48.41 ms |
| Hybrid 1:1 | 100% | 100% | 100% | 82.24 ms |
| Hybrid 2:1 selected | 100% | 100% | 100% | 76.43 ms |
| Hybrid 3:1 | 100% | 100% | 100% | 72.54 ms |

Duplicate and stale-snapshot counts are zero. Structural-context scoring includes only two expected local call relationships; this is limited coverage, not general binding accuracy. All tested weights pass equally; 2:1 is a tested middle configuration, not an established optimum. Hybrid is retained experimentally for structural evidence, not a latency win.

| Re-index scenario | Total | Embeddings computed/reused | Embedding time | AST time |
|---|---:|---:|---:|---:|
| Cold | 8.759 s | 44 / 0 | 8.1863 s | 0.0093 s |
| Unchanged | 0.015 s | 0 / 44 | 0 s | 0 s |
| Changed file | 0.559 s | 5 / 39 | 0.3933 s | 0.0046 s |
| Deleted file | 0.157 s | 0 / 37 | 0.0088 s | 0.0022 s |

Change/deletion ran only in disposable copies. The changed-file write normalized line endings, so five embeddings changed, not just the edited expression. Earlier baseline cold indexing took 21.732 seconds under different startup/cache conditions; no universal cold-start speedup is claimed.

## 11. Fixed quality benchmark and ablations

Every row uses the unchanged 20-defective/10-safe corpus and original strict scoring. Failed cases remain in denominators.

| Pipeline | TP / FN / safe FP | Precision | Strict recall | Detection recall | Safe FP rate | 30-function time |
|---|---:|---:|---:|---:|---:|---:|
| Previously recorded Docker reference | 15 / 5 / 1 | 93.75% | 75% | Not separately adjudicated | 10% | Separate repository run |
| Fresh frozen native baseline | 17 / 3 / 1 | 94.44% | 85% | 85% | 10% | 152.202 s |
| AST context | 17 / 3 / 5 | 77.27% | 85% | 85% | 50% | 171.383 s |
| AST + hybrid | 18 / 2 / 4 | 81.82% | 90% | 90% | 40% | 173.455 s |
| Full final selective verification | 16 / 4 / 3 | 84.21% | 80% | 80% | 30% | 211.086 s |

Detection recall counts recognition of the expected mechanism, not any different issue on the same function. `copyDiagnostic` has an effective null-pointer observation but loses the expected boundary finding: that is not detection of its boundary mechanism. Automatic nonmatching-category count is one; manually adjudicated expected-mechanism/wrong-category count is zero. Detector recognition before verification is 18/20; effective output remains 16/20.

Initial failed variants are also retained, including AST 12 TP/8 FN/1 FP, hybrid 15/5/1, and two verifier versions with zero effective true positives. The earlier ordered verifier produced 16/4/4. The initial retrieval variant reduced semantic top-k recall to 66.67%; the final prose fallback restores 100%. These artifacts are not overwritten or excluded to improve presentation.

Additional live capability checks also show regressions: baseline compiler and runtime interpretation answered, whereas the final experimental run returned `INSUFFICIENT_EVIDENCE` for compiler, runtime and CI/build diagnostics. Final function/module explanations and Q&A answered with validated citations. These failures are another reason to keep the baseline default.

## 12. Exact per-case changes

Relative to the fresh native baseline, final fixed-30 improvements are `readSensor` (candidate withheld as insufficient) and `doubleFreeSample` (supported resource finding rather than failed correction).

Regressions: `safeSensorValue`, `safeRead`, `safeSessionFile` become false positives; `copyDiagnostic` loses its supported boundary candidate; `forbiddenStateTransition` becomes a complete miss.

Unchanged strict results: `readSensorValue`, `calculatePressure`, `safePressure`, `clampPressure`, `readActivePressure`, `safeDiagnostic`, `uncheckedRead`, `uninitializedCounter`, `safeCounter`, `leakingSessionFile`, `activateSession`, `safeActivateSession`, `boundaryRead`, `safeBoundaryRead`, `definiteNull`, `fixedBoundaryRead`, `copySmallBuffer`, `allocateWithoutRelease`, `useFreedSample`, `uninitializedVoltage`, `uncheckedInput`, `insecureFormat`, `injectedNull`.

Of 28 final verifier decisions, 24 confirm, three are insufficient and one rejects. `copyDiagnostic`'s real boundary candidate is rejected because Qwen treats violation of a rule as contradiction of the allegation. Insufficient candidates occur in `readSensor`, `readActivePressure` and an additional null-pointer allegation in `boundaryRead`; that function's expected boundary candidate survives. No live reclassification occurred. Full original/verdict/effective records and reasons are retained.

## 13–15. Repository runtime, calls and context

Earlier Docker baseline reviewed 31 functions in **144.728 s**. Final native experimental original-repository review took **215.287 s** (48.75% longer across different environments), used one repository Cppcheck invocation, **32 detector calls and 28 verifier calls**, and achieved 8.640 functions/minute. Mean detector generation was 4.5035 s; verifier 2.3108 s; retrieval 0.1554 s including initial embedder startup. The repository result on the same fixed 30 labeled functions is 16 TP/4 FN/4 safe FP: 80% precision, 80% recall, 40% safe FP. The auxiliary `sensorConnected` is reviewed but not added to the fixed denominators.

| Fixed 30-function pipeline | Detector / verifier calls | Exact input tokens, all attempts | Maximum input |
|---|---:|---:|---:|
| Frozen baseline | 31 / 0 | 47,310 | 1,633 |
| AST | 31 / 0 | 46,470 | 1,558 |
| Hybrid | 31 / 0 | 46,905 | 1,619 |
| Full final | 31 / 28 | 73,082 | 1,619 |

Final verification adds 37.631 s (21.69%) over measured hybrid 30-function review; total overhead over the frozen baseline is 38.69%. Mean final detector generation is 4.5756 s, verifier 2.3439 s. Different runs/cache conditions prevent a pure causal timing attribution.

The fixed-30 token table excludes six additional capability tasks. The final benchmark artifact's 83,423 total/1,688 maximum include those tasks; these scopes must not be mixed. Original-repository recorded input is a **73,057-token lower bound**, maximum recorded 1,619: all verifier inputs and last detector input per function were retained, but the first input of one corrective retry was not captured. That missing measurement is not estimated. The reproduction driver now captures all generation requests.

The context remains 8,192 with 6,144 input, 1,536 output and 512 reserve. All recorded actual inputs fit; deterministic overflow tests reject oversized required evidence. Baseline generation/retrieval stage means were not instrumented before freezing and remain unmeasured.

## 16–19. Remaining errors and limitations

Final fixed-30 false positives: `safeSensorValue`, `safeRead`, `safeSessionFile`. The original-repository demonstration also flags `readSensor`; its different verifier decision demonstrates run-to-run variation and does not erase the historical false positive.

Remaining fixed-30 and original-repository misses: `readActivePressure`, `copyDiagnostic`, `activateSession`, `forbiddenStateTransition`. The verifier lacks callee source for `readActivePressure`, overlooks explicit guards/checks in safe examples and confuses rule violations with source contradiction. Provenance validation cannot prove that these interpretations are correct.

Historical Checkpoint 2 misses (`calculatePressure`, `readActivePressure`, `activateSession`, `doubleFreeSample`) and the safe `readSensor` false positive remain in their original reports. New measurements do not redefine those older evaluation sets. The original `doubleFreeSample` corrective retry failed; its experimental resource result now succeeds, with evidence and budgets unchanged. That local improvement does not offset overall quality regression.

Facts are syntax-derived, not compiler binding, alias analysis, full call graphs, symbolic execution or whole-program data flow. Ambiguous relationships are not guessed. Standard-name recognition and signals are deliberately incomplete. Verifier source-range limits, external SDK/configuration limits, degraded analyzer coverage, finite pilot history and contextual omissions remain explicit.

Security/regression checks pass; **review-quality and diagnostic-capability gates fail**. Baseline stays deployed. Experiments require explicit opt-in and re-indexing; they do not rewrite old findings or replace human Accept/Edit/Reject. The [printable final original-repository report](demonstrations/quality-repository-final-report.html) and [machine-readable results](evaluation/quality-results.json) contain audit/provenance and measured outcomes.

Confirmed: same local Qwen model and Jina code embeddings; no cloud inference, benchmark-label changes, original-source changes, automatic fixes, Git/CI automation or formal MISRA compliance claim. Only original/demo guidance was used. Work stops at this delivery.
