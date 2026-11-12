# Code-aware analysis and selective verification

The Case Study 4 scope, local models, context budgets, authorization, snapshots and human approval remain unchanged. Syntax facts and verifier decisions are not certified defect diagnoses.

## Architecture

Before: authorized source → function chunks → exact target plus Jina/Chroma neighbors → Cppcheck and demo guidance → Qwen → schema and citation validation → human review.

Enhanced: authorized captured source → Tree-sitter facts → mandatory exact target → syntactic symbol/type/header context plus identifier/vector ranking → Cppcheck and guidance → compact source/facts context → Qwen detector → selective same-Qwen verifier → unchanged citation validation → human review.

Embeddings augment structural retrieval. Identifiers, signatures, scopes and source lines have exact meaning; semantic similarity does not establish a code relationship. Similar methods and implementations are not automatically callees of the selected function.

## Captured syntax

`app/ingestion/code_facts.py` stores schema version, content hash, repository, snapshot and file. Function records preserve qualified names, signatures, return types, scope, parameter types and pointer/reference syntax, locals and initialization presence, conditions, loops/switches, calls/receivers, returns, assignments, pointer operations and recognized resource operations. Assignments distinguish local identifiers, nonlocal identifiers and visible fields without resolving ownership or global bindings.

Every observation retains source text and original line ranges. The bounded parser cache uses immutable source bytes and grammar; results are copied and bound to authorized snapshots. It is accessed after authorization. Parser failures remain explicit.

Signals describe possible repeated release, access after release, nullable return, pointer-parameter use, visible null guard, a narrow uninitialized-return pattern, and ignored results of narrowly recognized operations. Repeated releases require simple operands and no intervening assignment/acquisition/declaration/control transfer. Library operations require the corresponding captured standard header and no visible bare-name shadowing. A field-access condition is not a null guard. Signals are deliberately incomplete and do not replace Cppcheck.

Structural mode retains complete function units. Oversized required source fails explicitly under the existing 6,144-input/1,536-output/512-reserve policy at 8,192 context. Source is never silently truncated. Oversized embedding units use a bounded identifier summary only for the supplementary vector. Residual nonfunction/fallback regions retain bounded chunking.

## Retrieval and guidance

Selected function/file evidence is mandatory. Unique syntactic local-call names, unique captured includes, associated source/header pairs and uniquely named visible types supply structural context. Receiver binding, overload resolution and whole-program semantics remain unresolved.

Related candidates use symbol tiers followed by identifier/vector reciprocal ranks. Measured configuration: lexical weight 2, vector weight 1, reciprocal-rank constant 20. Inclusion reasons are `REQUIRED_TARGET`, `SYMBOL_RELATION`, `IDENTIFIER_MATCH`, `VECTOR_SIMILARITY`, `ENGINEERING_RULE`; historical precedent retains existing authorization/provenance and lower priority.

English words coinciding with common variables do not override vector fallback. Explicit symbols/types/constants still receive lexical priority. Queries include concise selected signatures and identifiers. Exact-function review omits unrelated vector neighbors; Q&A/explanations can use supplementary results. Guidance priority uses observed syntax/analyzer categories, never expected benchmark labels. Required source/facts are retained; analyzer and deterministic source follow; history is removed first under pressure.

## Embedding reuse

Jina remains pinned, normalized and CPU-local. A private SQLite content cache reuses vectors only within the same authorized repository/scope and embedding identity. Complete content hashes distinguish changes. Active vector records still carry new snapshot identities; deleted source cannot appear in active retrieval. Failed staging preserves the old active snapshot. Index responses record computed/reused vector counts, embedding time and AST time.

## Cppcheck configuration

`POST /repositories/index` accepts optional `analysis_configuration`: `include_paths`, `defines`, `standard`, `platform`, and bounded imported `compile_commands` JSON text. Paths must refer to authorized captured source. Only supported literal options become Cppcheck arguments in its isolated source directory. No compiler, build, script, hook or compilation-database command executes. Unsupported arguments produce partial-configuration limitations. Configuration participates in snapshot identity; supply it again on subsequent indexing.

Default analysis records `DEFAULT_CONFIGURATION` and existing coverage warnings. Supplied options record `PROJECT_CONFIGURATION`, which does not guarantee full build coverage. External SDK paths, arbitrary options and complex macro expressions remain unsupported.

## Verification and audit

The same pinned Qwen checks only candidate findings. Safe/no-supported-finding responses do not trigger verification. It receives the allegation, selected source, compact syntax facts, relevant analyzer evidence and guidance. Unrelated source/history and detector task directives are excluded.

The strict result records support, contradiction, proposed category, decision, concise reason and supplied evidence IDs. Contradiction means source contradicts an allegation; a guidance violation is support, not contradiction. No chain-of-thought is requested.

`CONFIRM`, `RECLASSIFY`, `REJECT`, `INSUFFICIENT` remain separately audited. Reclassification changes the explicit category and retires incompatible guidance without synthesizing citations. Effective findings and verifier reasons pass existing provenance validation. Invalid/unavailable verification withholds candidates with explicit limitations. Originals, verdicts and effective candidates are preserved in new JSON/escaped HTML and the existing UI's audit details. Historical findings and reviewer decisions are untouched.

Verification remains fallible and does not replace engineering review.

## Reproduction and acceptance

`ANALYSIS_QUALITY` selects `baseline`, `ast`, `hybrid`, `verified`; nonbaseline modes capture structural facts on re-index. Failed quality gates leave a component explicitly experimental. Re-indexing creates a new policy/content snapshot; historical records remain readable.

Run `.venv\Scripts\python.exe -m scripts.evaluate_code_quality --mode verified --report .local\quality-new-run.json` for the unchanged fixed synthetic quality set. `scripts.evaluate_code_retrieval` measures retrieval configurations, structural context and cache timings. Evaluation source/data is disposable; originals and labels remain unchanged.

Final acceptance, per-case comparisons, failed initial ablations and the selected default are recorded in [the analysis-quality results report](analysis-quality-results.md). The review-quality gate failed: keep `baseline` selected; `ast`, `hybrid` and `verified` are experimental opt-ins. Hybrid improves the measured syntactic-context retrieval and cache reuse, but false positives and verifier errors prevent promotion. No universal accuracy, formal MISRA compliance, training, autonomous fixes or Git/CI automation is claimed.
