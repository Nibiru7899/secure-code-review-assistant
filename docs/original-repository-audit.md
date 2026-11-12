# Original repository audit — 4 October 2026

The application workflow and provenance checks passed. The AI findings are not all semantically correct and still require engineering review.

This audit checked the actual authenticated application at `http://127.0.0.1:8501/`, its local API, and the original `D:\TataTech\demo_ecu` source. It did not use the earlier controlled visual fixture.

## Current operational review

- Run: `e3623127-37ff-44c9-a962-7a8cdf84e747`, started 13:05 IST.
- Snapshot: `4489ceef577d88d9b56d83b98f7bd986f7baad4b11c81b65c1705c9c7c50b104`.
- Seven captured files match the original files line for line. Independent parsing of the originals matches all 31 stored function names, signatures and line boundaries.
- All 29 cited source quotes match the original source lines. All 21 findings currently pass the backend provenance validator. This establishes citation provenance, not diagnostic correctness.
- Displayed totals match the stored report: 31/31 functions reviewed, 21 candidates across 18 functions, 17 high and four medium; 144.728 seconds. All 21 decisions remain pending.
- Cppcheck coverage remains degraded. Completion does not certify safety or complete analysis.

## Findings that remain incorrect or incomplete

`readSensor` is a safe-function false positive. Its conditional return explicitly checks `activeSensor.connected`; it does not dereference a nullable returned pointer. The model's explanation incorrectly says the function does not check that condition. A caller might misuse its return value, but the available finding does not establish such misuse in this function.

`calculatePressure`, `readActivePressure` and `activateSession` remain missed. `useFreedSample` and `doubleFreeSample` describe real resource-lifetime problems but are labeled `null-pointer` rather than the expected `resource` category. They therefore remain misses under the original category/location matching criteria. The current `doubleFreeSample` review completed rather than failing its context/retry budget; its category is still incorrect.

On the unchanged fixed synthetic quality corpus: 15 true positives, five false negatives, one safe-function false positive; 93.75% precision per labeled function, 75% recall, 10% safe-function false-positive rate. These are not universal model accuracy. Extra allegations on defective functions have not been exhaustively adjudicated.

The repository contains one additional safe helper, `sensorConnected`, outside the original 20-defect/10-safe quality set. Its result remains in the complete 31-function case ledger. The evaluation script previously included it when counting false positives while reporting a denominator of ten safe functions. This audit corrected that accounting, explicitly marks fixed-set membership, and reports auxiliary false positives separately. The correction leaves this run's metrics unchanged. Earlier evaluation artifacts were preserved.

## Verification

- Running API and UI: all 38 checked application/UI/rule/theme files in each container match workspace SHA-256 hashes.
- API, UI and PostgreSQL containers are healthy. The original reviewed repository is mounted read-only.
- Actual preview failure responses: invalid credential 401, path escape 404, nonexistent snapshot 409.
- All six pages render against the real authenticated backend in an isolated Streamlit test session; signing out clears that session's authentication.
- Full regressions: **108 tests passed in 64.676 seconds**, including two new tests for fixed-corpus accounting and rejection of missing fixed cases. Tests exercise disposable data and controlled model responses; they do not prove live-model accuracy.
- All 17 protected source/prompt/rule/fixture/previous-evaluation artifact hashes remain unchanged.
- No new inference, repository indexing, source modifications, reviewer decisions, CI jobs or build commands were triggered during this audit.
- Streamlit/Chroma deprecation warnings remain; they did not prevent the verified workflows.

Machine-readable results: [original-repository-audit.json](evaluation/original-repository-audit.json). Actual screenshots: [completed review](screenshots/audit-actual-review.jpg), [source preview](screenshots/audit-actual-source.jpg) and [false-positive finding](screenshots/audit-actual-false-positive.jpg).

Changed implementation files: `scripts/demo_repository_review.py` and `tests/test_repository_evaluation.py`. Added this audit, its JSON results and actual screenshots. Runtime analysis behavior, models and prompts were unchanged; no deployment restart was needed.
