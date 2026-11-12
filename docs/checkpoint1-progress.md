# Checkpoint 1 verification — 2026-10-03

Status: foundation implemented and verified on this laptop; ready for user
checkpoint review. Phase 2 has not started. The current interface is a local CLI,
not the future Streamlit review UI.

## Delivered behavior

Credential-bound identity and registered repository/path permissions precede
source access, storage queries and embeddings. Windows opened-handle verification
protects source reads from root escapes. Traversal, ADS paths, symlinks and
junctions are rejected. Permission changes cannot reuse a broader stored scope.

The scanner reports unsupported/ignored/oversized/generated/binary/secret files
and unreadable/changed-source failures. Tree-sitter C/C++ extracts functions and
qualified metadata; gaps retain header/global context. Failed parsing produces
bounded file chunks without aborting the other files. Chunks retain byte offsets,
inclusive line ranges and deterministic IDs.

Content-based snapshots work for ordinary directories and Git working trees.
SQLite stores manifests/source provenance; Chroma stores code and rules in
separate collections. Vectors stage before the catalog publishes the active
snapshot. Failed embedding/staging/publication preserves the previous snapshot.
Successful replacement removes obsolete active vectors; captured source history
is retained. Exact/file/symbol lookup and semantic code/rule retrieval return
provenance and explicit ambiguity/absence. Rule provenance identifies the actual
approved file, rule ID, title, category and line range.

## Measured results

| Check | Actual result |
| --- | --- |
| Hardware | RTX 4060 Laptop GPU, 8188 MiB VRAM; 25,480,257,536 bytes system RAM |
| Runtime | Python 3.12.14 isolated environment; Ollama 0.35.1 |
| Model | qwen2.5-coder:7b, Q4_K_M |
| Model digest | dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364 |
| Loaded working context | 8192 tokens |
| Model GPU allocation | 5,133,943,438 bytes reported by Ollama |
| Smoke input | 62 tokens for small explanation; 4874 for working-context case |
| Repeated smoke test | Both full runs passed; explanations manually checked |
| Repeat-run latency | 10.821 s existing/cold load, 0.756 s warm small request, 3.878 s long case |
| Native demo indexing | 6 accepted source/header files; 26 chunks; all parser statuses ok |
| Regression suite | 34 tests passed; pip check found no broken requirements |
| Fixed live retrieval corpus | 20/20 questions passed at top-k=3 |
| Exact lookup/absence checks | 11/11 passed |
| Semantic code/rule checks | 9/9 expected items found in top 3 |
| Final isolated indexing time | 14.394 s including model initialization |
| Average final query time | 0.184 s across 20 cases; affected by concurrent verification load |
| Duplicate/stale active chunk rates | Both 0 |
| Offline retrieval runtime | Passed with socket connection attempts blocked |
| Reindexing | Unchanged IDs/counts stable; changed function replaced; deleted file removed |
| Persistence | Reopened catalog/vector store plus separate CLI process verified |
| Unauthorized request | Explicit AccessDenied; no code retrieval/model input |

The retrieval measures use actual CPU Jina embeddings, not the deterministic test
double. Five contexts were inspected: calculatePressure, readSensor, safePressure,
clampPressure and safeDiagnostic. Their source text/locations matched the demo.
Generic implementation queries can rank unrelated rules; returned rules remain
candidates, not assertions of applicability. A pointer-specific query retrieved
PTR-001 first. No finding precision or bug-detection accuracy is claimed.

Raw synthetic reports are in `.local/ollama-smoke.json`,
`.local/ollama-smoke-repeat.json` and `.local/retrieval-evaluation.json`.
`requirements.lock` records the installed Windows environment. Embedding weights
are pinned to revision 516f4baf13dec4ddddda8631e019b5737c8bc250; supporting custom
code is pinned to 3baf9e3ac750e76e8edd3019170176884695fb94, localized and hash-checked
before loading. No runtime Hub downloads or cloud embedding fallback.

## Failures reproduced and fixed

- The initial 512-line smoke prompt used 6218 tokens, exceeding the reserved 6144
  input budget. Reduced only the synthetic prompt to 400 lines: 4874 tokens,
  preserving both the 8192 context and the original input/output budget. Reports
  now retain the last measured request even if validation fails. Overflow remains
  a rejected condition in regression tests.
- Windows Chroma handles prevented disposable-database cleanup. Added a pinned
  shutdown adapter; fixture cleanup now succeeds without resetting persisted data.
- Storage initialization interruption can now retry safely; partial initialization
  does not leave an unusable catalog/store pair.
- HTTP error responses are closed explicitly. Remote redirects still fail.

## Reproduction and limits

Follow README.md for the existing environment's demo commands, smoke checks,
regression suite and isolated evaluation. Destructive reindex/reset scenarios use
disposable copies only; original demo source was not edited by evaluation.

This is a small synthetic corpus, not evidence of production retrieval quality.
The Phase 2 corpus must expand to 20 known-defect and 10 safe functions; the current
20 functions are labelled in external fixtures with relevant assumptions. A live
service/UI, Cppcheck integration, evidence-backed findings, reviewer workflow,
PostgreSQL and Docker remain later checkpoint work.

Credentials and stored source require appropriate local OS access controls/disk
encryption for sensitive use. Source snapshots are not a filesystem-wide atomic
capture under concurrent edits; each read is checked and captured evidence is
reproducible. Commands are serial; concurrent multi-process indexing is not yet
supported. UTF-8 source is supported; other encodings are explicit failures.
Fresh-machine setup, deployment and encryption requirements are final-phase
checks, not validated claims here.

Native path/HTTP verification required execution outside the agent sandbox. The
offline evaluation still rejected network calls. The upstream model's optional
optimum/ONNX warning does not affect the tested PyTorch CPU path. No shell profile
or Anaconda files were modified.

## Approval gate

AGENTS.md requires explicit user approval after each verified phase. Await
Checkpoint 1 approval before beginning static analysis or review intelligence.
