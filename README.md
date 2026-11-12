# Secure Code Debugging and Review Assistant

Local Case Study 4 implementation for authorized C/C++ source and imported
engineering evidence. Scope and approval checkpoints are in AGENTS.md and
PROJECT_PLAN.md. No Git/PR/CI automation or automatic source modifications.

Analysis-quality experiments preserve the local stack and original benchmark. See
[code-aware analysis](docs/code-aware-analysis.md) for syntax facts, structural
retrieval, embedding reuse, captured Cppcheck options and same-model verification.
`ANALYSIS_QUALITY` selects `baseline`, `ast`, `hybrid` or `verified`. Keep the
default `baseline`: the [measured quality results](docs/analysis-quality-results.md)
show that the three enhanced modes remain experimental because their finding
quality regressed.

A separate [deterministic post-candidate guard experiment](docs/ast-guard-experiment.md)
keeps baseline detector prompts/retrieval unchanged and makes no verifier call.
Its measured quality metrics did not improve, so `guarded` also remains optional
and the deployed default stays `baseline`.

## Current implementation

Checkpoint 1 provides a verified local Ollama smoke test, credential-bound
repository/path permissions, read-only scanning, Tree-sitter parsing with
bounded fallback chunks, content snapshots, CPU Jina embeddings, persistent
Chroma storage, exact/semantic code retrieval and approved rule retrieval.

Checkpoint 2 adds a local FastAPI service, Cppcheck on captured source,
code Q&A, cited function/module explanations, imported diagnostics, candidate
findings, recommendations, schema/citation validation and SQLite run/finding
history. Checkpoint 3 adds Streamlit, authenticated Accept/Edit/Reject,
immutable originals with reviewer revisions, structured reports, a verified
SQLite-to-PostgreSQL migration and local Docker delivery.
The Case Study 4 alignment adds sequential repository-wide review, persisted
progress/coverage, optional approved historical evidence, derived evidence-support
levels and a compact dark dashboard. Snapshot identity does not require Git;
optional commit metadata is not collected.

## Primary workflow and presentation

Open the local UI at http://127.0.0.1:8501 and enter your private configured
credential and press **Sign in**. The credential stays in this Streamlit session;
**Sign out** clears it and the session's selected reports/forms. The default
**Overview** guides repository selection, indexing, analysis and reviewer decisions.
It shows captured files/functions, parser
failures, last indexing/review and the active content snapshot. Use **Index /
re-index source**, then **Review Entire Repository**. Cppcheck runs once
on captured source; each analyzable function goes through the existing bounded
pipeline sequentially. Progress and every function outcome persist in PostgreSQL.
A failed function does not abort the other functions. A process restart marks an
unfinished job INTERRUPTED; it never claims unprocessed functions were reviewed.

**Repository Review** provides coverage, severity/category counts, timings,
filterable findings, readable printable HTML and complete JSON exports. While a
review runs, duplicate starts are disabled and elapsed time/current function are
visible. Index status describes captured source, not model/analyzer health.
**Analyze Source** groups tasks as **Review**, **Explain** and **Ask a Question**.
It exposes function/module explanation, code Q&A, dependency/control-flow summaries, security review,
coding-standard assistance and static performance investigation. **Diagnostics**
imports compiler/static reports or build/runtime/CI text as evidence; it never
executes those commands. Text file:line and Cppcheck XML locations are checked
against captured source and displayed as mappings, not verified execution history.
Captured source is previewed before analysis with original line numbers, exact
file/function/signature selection and pages of at most 200 lines. Re-index to
capture source changed outside this application. **Findings** defaults to
awaiting decisions; search, category/severity/status filters and **All statuses**
are available. Only the selected finding's full report is fetched.
**Findings** supports authenticated Accept/Edit/Reject; **History & Reports**
retains originals, revisions, snapshots and repository reports.

Approved ACCEPTED/EDITED findings may provide optional precedent for the same
file/function. PENDING/REJECTED findings are excluded. Original snapshot,
reviewer, action and time are retained; current source takes priority and history
is omitted first when context is tight. History does not train the model or
increase the evidence-support level.

STRONG means source plus relevant analyzer plus applicable demo rule; SUPPORTED
means source plus rule or analyzer; AI-ONLY CANDIDATE means cited source without
that corroboration. **Evidence support is not a probability of correctness.**
Root causes remain hypotheses. Performance observations are static/source-level;
there is no runtime profiler. Original/demo guidance is not official MISRA text
and does not establish compliance.

Repository endpoints: `POST /review/repository`, `GET /repository-reviews?repository=...`,
`GET /repository-reviews/{id}?repository=...`, and
`GET /repository-reviews/{id}/report?repository=...`.
The request uses an authorized repository and its active snapshot. All reads,
progress and exports enforce the same credential/path scope.

Reproduce the live local demonstration without changing fixtures:

```powershell
Set-Location D:\TataTech
& .\.venv\Scripts\python.exe -m scripts.demo_repository_review --report .local\repository-live-repeat.json
```

This executes the local review application, not repository builds or CI jobs.
Each invocation records a new measured run; the public latest-run JSON is updated
by default. Supply `--summary docs/evaluation/your-new-run.json` to preserve older
artifacts, as done in this polish demonstration.
The preserved v15 run and earlier checkpoint evaluations are separate artifacts.
See [alignment results and limitations](docs/case-study4-alignment.md) and the
[exact eight-minute presentation](docs/case-study4-presentation.md).

## Setup (Windows PowerShell)

Use Python 3.12 for the recorded Windows dependency lock (other Python versions
are not verified). The current `.venv` was created with the Codex bundled runtime.
On another machine, install Python 3.12 and create the environment first:

```powershell
Set-Location D:\TataTech
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock
ollama pull qwen2.5-coder:7b
& .\.venv\Scripts\python.exe -m scripts.prepare_embeddings
& .\scripts\prepare_cppcheck.ps1
& .\.venv\Scripts\python.exe -m scripts.smoke_ollama --timeout 120 --report .local\ollama-smoke.json
```

For this existing workspace the environment, dependencies and embedding
artifacts are already prepared. Do not re-create them to run the demo.
The setup script downloads fixed model/code revisions into `.local/models` and
localizes custom-code references. Runtime verifies artifact hashes, loads local
files only, and runs embeddings on CPU. Retain that directory for offline use.
Downloads occur only in the explicit setup step.

Ollama must be running locally on port 11434. Start its application if necessary;
do not start a duplicate server. The smoke test never downloads models, sends
only synthetic code, and reports model digest, quantization, duration, input/
output counts, actual loaded context and GPU allocation. It fails explicitly
on unavailable services or mismatches. The 3b fallback requires a measured 7b
memory problem; it is never selected automatically.

## Run the authorized retrieval demo

For a new setup only, generate demo credentials once; existing credentials are
never overwritten:

```powershell
& .\.venv\Scripts\python.exe -m scripts.foundation setup-demo
```

Credentials already exist in this workspace. Load the local token and run:

```powershell
$env:REVIEW_TOKEN = Get-Content -Raw .local\demo-token.txt
& .\.venv\Scripts\python.exe -m scripts.foundation index
& .\.venv\Scripts\python.exe -m scripts.foundation status
& .\.venv\Scripts\python.exe -m scripts.foundation retrieve --symbol calculatePressure --query 'nullable sensor pointer pressure'
& .\.venv\Scripts\python.exe -m scripts.foundation retrieve --query 'release owned file resources'
```

Select overloads with `--file` and/or `--signature`; ambiguous symbols return
candidate metadata. Missing targets return `not_found`. Unknown credentials and
dependency failures return explicit errors. Exit 1 denotes failure; exit 2
denotes CLI argument errors.

Administrator-managed `.local/access.json` maps SHA-256 credential digests to
users and users to approved absolute repository roots/path prefixes. Prefix `.`
grants the registered root; otherwise only listed files/directories are indexed.
Do not authenticate with a requester-supplied username. Add approved roots and
permissions to select another repository via `--repository`. Application data
must remain outside scanned roots. Changing path scope requires indexing that
scope; an old broader index is not reused.

Scanning accepts C/C++/headers, rejects links/junctions and path escapes, and
records skipped unsupported, secret, generated, oversized, binary or unreadable
files. UTF-8 is supported; other encodings are reported explicitly. Snapshots
capture source evidence without claiming a directory stayed unchanged throughout
the run. Re-index after edits. Failed publication preserves the previous active
snapshot. Changed/deleted chunks are removed from active vectors; captured source
snapshots remain local for provenance.

## Tests and actual-model evaluation

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -m scripts.evaluate_retrieval --report .local\retrieval-evaluation.json
```

Unit/integration storage tests use a deterministic embedding double. The
evaluation uses the actual pinned CPU model, 20 fixed questions and a disposable
demo copy. It blocks socket connections, checks idempotency/change/delete/
persistence/denial and removes fixtures. Ground-truth labels remain outside
retrieved source. Results are small-corpus retrieval measurements, not defect
detection or production accuracy claims.

## Run Checkpoint 2

Re-index the expanded demo corpus, then run a review or explanation:

```powershell
$env:REVIEW_TOKEN = Get-Content -Raw .local\demo-token.txt
& .\.venv\Scripts\python.exe -m scripts.foundation index
& .\.venv\Scripts\python.exe -m scripts.demo_review review_function --file src/sensor.cpp --function readSensorValue --report .local\review-demo.json
& .\.venv\Scripts\python.exe -m scripts.demo_review explain_function --file src/brake_control.cpp --function clampPressure --question 'Explain the visible branches and return values'
& .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

In another PowerShell window, select the active snapshot explicitly:

```powershell
$token = Get-Content -Raw D:\TataTech\.local\demo-token.txt
$headers = @{ Authorization = "Bearer $token" }
$status = Invoke-RestMethod http://127.0.0.1:8000/repositories/demo_ecu/status -Headers $headers
$body = @{ repository = 'demo_ecu'; snapshot = $status.snapshot; file = 'src/sensor.cpp'; function = 'readSensorValue' } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/review/function -Method Post -Headers $headers -ContentType 'application/json' -Body $body
Invoke-RestMethod 'http://127.0.0.1:8000/findings?repository=demo_ecu' -Headers $headers
```

The local API schema is available at `/openapi.json`. Endpoints:

| Method/path | Purpose |
| --- | --- |
| `GET /health` | Application liveness; dependencies checked during requests |
| `POST /repositories/index` | Index a registered repository; body `repository` |
| `GET /repositories/{repository}/status` | Authorized files, functions and snapshot |
| `POST /review/function`, `/review/file` | Selected source review |
| `POST /explain/function`, `/explain/module` | Cited explanations; optional `question` |
| `POST /qa` | Evidence-based question; required `question` |
| `POST /diagnostics/interpret` | Imported compiler/build/runtime/CI text interpretation |
| `GET /findings`, `/findings/{id}` | Authorized candidates; `repository` query required |
| `GET /repositories` | Repository IDs authorized for the authenticated identity |
| `GET /analysis-runs` | Latest 100 authorized runs; `repository` required |
| `GET /analysis-runs/{id}/report` | Original run, effective findings and reviewer history; `repository` required |
| `POST /findings/{id}/review` | Authenticated Accept/Edit/Reject with revision check |
| `GET /approved-findings` | Approved history in the current authorized path scope |

Analysis bodies require `repository` and `snapshot`; selectors are `file`,
`function` and optional `signature`. Diagnostics additionally require `text`
and `origin`, with optional `tool`, `tool_version`, `observed_at` and
`diagnostic_snapshot`. Origin/association are user-declared and never treated
as independently verified. Evidence records import time and a stable content ID.
No commands extracted from logs or source are executed.

Unknown credentials/path scopes are denied before retrieval, analyzer or model
calls. Missing targets return HTTP 404; stale snapshots or ambiguous targets return HTTP 409; invalid request
bodies return 422. Dependency/schema/evidence failures return explicit FAILED
responses (HTTP 503). Required source exceeding the input budget returns
INSUFFICIENT_EVIDENCE; select a smaller function/file. Optional related evidence
can be omitted with a visible limitation. Input is bounded conservatively by
UTF-8 bytes plus template reserve, then checked against Ollama's reported token
count. Context is 8192, input budget 6144, output reserve 1536, uncertainty 512.

Run outcomes are CANDIDATES, NO_SUPPORTED_FINDING, INSUFFICIENT_EVIDENCE, FAILED,
or ANSWERED for explanations/Q&A/diagnostics. NO_SUPPORTED_FINDING never means
the source is safe. Responses expose analyzer status/coverage, cited evidence,
limitations, model digest, prompt version, timings and PENDING disposition.
Source quotes/locations, selected functions, rules and analyzer IDs must validate;
analyzer support must match the issue's category/location. Citation validity
establishes provenance; it does not establish semantic correctness. Human review
must assess each candidate diagnosis, explanation and recommendation.
Review and explanation use separate model schemas. The model selects supplied
line evidence IDs (such as `S1L10`); the backend resolves exact quotes, file,
function and locations from captured evidence, then validates the result again.
Unknown IDs are rejected. This resolution never repairs an invented citation.
Run outcomes are derived from validated findings/claims. Generation is constrained
to available citation/rule IDs. Rejected output may be regenerated once with
validation feedback within the same input budget.

Cppcheck uses captured authorized files and fixed arguments, without a shell,
addons, compilation databases, repository scripts, hooks or build commands.
Absolute/traversal/dynamic include directives are rejected to prevent reading
uncaptured external source. Defaults are C11/C++17 without a supplied build
configuration, so coverage is limited. Missing tools, nonzero exits, timeouts,
invalid XML and output overflow are surfaced explicitly. Set `CPPCHECK_EXE` to
an administrator-approved executable for another local installation.

Rules are the six original rules in `rules/coding_rules.md`. No actual MISRA
rule text is used or downloaded and no MISRA compliance is claimed. Licensed,
approved guidance would be a separately authorized future capability.

```powershell
& .\.venv\Scripts\python.exe -m scripts.evaluate_final --report .local\final-evaluation.json
& .\.venv\Scripts\python.exe -m scripts.evaluate_explanations
& .\.venv\Scripts\python.exe -m scripts.smoke_api
& .\.venv\Scripts\python.exe -m scripts.smoke_review_failures
```

This fixed live evaluation covers 20 defective and 10 safe functions, plus Q&A,
explanations and imported diagnostics. Expected labels remain outside model
evidence. Disposable copied source/databases are removed after evaluation.
The deliberate local test artifact includes prompts and model outputs for manual
inspection; routine application logs do not include these bodies. Protect `.local`
reports with the same OS access controls as captured source. The evaluation
records missed findings, false positives, rejected output, analyzer support and
latency; it is separate from deterministic unit/integration tests.

The explanation evaluation runs on the authorized existing demo index. Failure
smoke tests use a non-listening loopback port, a missing tool path and a reduced
context budget; they do not stop Ollama or execute log commands.

## Privacy and limitations

Restrict `.local` to approved OS users: it contains credentials, captured source,
vectors and reports. This pilot does not encrypt those files itself; apply
organizational disk encryption/access controls for sensitive deployments.
Source/prompt bodies are never sent to external services. Chroma telemetry and
automatic embedding functions are disabled. Its transitive Kubernetes client
dependency is unused; no Kubernetes functionality is built.

Ollama requests disable proxies and reject remote origins/redirects. Native
operation accepts loopback only. Docker explicitly permits the single
`host.docker.internal` origin to reach host-managed Ollama; arbitrary remote
inference origins remain denied.
Responses are bounded and failures are explicit. The model's absent `optimum`
warning concerns optional ONNX export; the tested PyTorch CPU path does not use it.
Chroma 1.0.20 uses a pinned internal shutdown adapter to release Windows handles;
its pilot collections use batch size 1 and sync threshold 1 to persist tiny
indexes and avoid the reproduced filtered-reader failure. Existing collection
settings are updated without deleting vectors or snapshots.
all clients must finish before shutdown. Current commands are serial local jobs,
not concurrent indexing workers. Native Windows path/HTTP tests may require
execution outside an agent sandbox. Never reset operational data or modify
reviewed source to test the application.

The Anaconda PowerShell hook error is separate. Explicit `.venv\Scripts\python.exe`
avoids conda. If necessary use `powershell.exe -NoProfile` or `pwsh -NoProfile`;
this project does not change shell profiles.

## Checkpoint 3: native reviewer UI

Start the API as above, then run in another PowerShell window:

```powershell
& .\.venv\Scripts\python.exe -m streamlit run ui/streamlit_app.py
```

Open http://127.0.0.1:8501. Enter your existing local credential from
`.local/demo-token.txt` in the password field; it is never included in reports.
Select an authorized repository, index it, then select a file/function and
Review, Explain, Code Q&A or Interpret diagnostics. Source, analyzer evidence,
original engineering guidance and imported logs are displayed separately from
AI interpretations. Coverage, degraded dependencies and insufficient evidence
remain visible. The UI renders untrusted text as text/code rather than HTML.
Code Q&A submits through the dedicated `/qa` endpoint. Earlier unsuccessful Q&A
evaluations remain recorded; this routing correction does not tune the model.
Diagnostics accepts pasted text or a local `.txt`, `.log` or `.xml` file.
Provide a declared origin; tool/version are optional. Input must be valid UTF-8,
nonempty and no longer than 6,000 characters. Oversized input is rejected without
truncation, and malformed XML is rejected before submission. Origin is a user
declaration, not proof that a build or CI system ran.

Accept records an authenticated reviewer decision. Edit provides readable
category, severity, issue, explanation, root-cause hypothesis, security implication,
remediation and supplied-rule fields. Location and citations stay read-only in
this form; an advanced JSON editor permits evidence changes. Save before changing
pages or editor mode because unsubmitted drafts are not retained. Backend checks
validate edited evidence against the original captured
snapshot. Reject retains the candidate and records the decision. These actions
never change reviewed source. Original model findings/runs are immutable; each
decision is a numbered revision with reviewer identity and timestamp. A stale
revision returns HTTP 409; reload the report before deciding again. Edits
failing schema/citation validation cannot be accepted. Historical findings that
fail the current validation policy are explicitly marked; provenance checks do
not certify a diagnosis. Historical approved text remains untrusted evidence.

The review endpoint body is `repository`, `action` (`ACCEPTED`, `EDITED`,
`REJECTED`), `expected_revision` (0 initially), optional `note`, and a full
`edited_finding` only for Edit. Reviewer identity always comes from the bearer
credential. `GET /findings` retains its default immutable-original response.
Optional `include_review_state=true` returns effective summaries, latest disposition
and revision; provenance is checked in the selected full report, not the summary.
`GET /repositories/{repository}/source` takes `snapshot`, exact captured `file`,
optional `function`/`signature`, `start_line` and `limit` (maximum 200). It authorizes
before storage access and never reads live arbitrary paths or calls inference.
Current disposition/history is in the structured run report. History lists are limited
to the latest 100 records; direct IDs can retrieve older runs/findings.

Use **Download readable report** for a self-contained HTML report. Open it locally
in a browser and use Print for paper or the browser's PDF option; no PDF service
is added. HTML escapes untrusted text and has no scripts or external resources.
Complete JSON remains available from the UI and authorized report endpoint. Reports
preserve original snapshot, evidence, model/tool/template identifiers, limitations,
original findings and separate reviewer revisions. Protect exported reports as
source data. Do not change or delete `.local/data` to test reset behavior.

Polish verification, changed files, live demonstrations, screenshots and remaining
limitations are recorded in [docs/polish-results.md](docs/polish-results.md).

## PostgreSQL migration

SQLite remains the native default. PostgreSQL 16.13 is verified in an isolated
Docker test. An administrator can set `DATABASE_URL` to a local PostgreSQL
connection, or `DATABASE_URL_FILE` to a protected file containing it. Never put
a password in a command argument or version-controlled configuration. The
credential configuration stays authoritative; database users/permissions record
audit observations rather than granting access.

Stop the API before copying its catalog. Configure a new, empty PostgreSQL
database, set the connection securely in the process environment, then run:

```powershell
& .\.venv\Scripts\python.exe -m scripts.migrate_postgres --sqlite .local\data\catalog.sqlite3 --backup .local\migration-backup.sqlite3 --report .local\migration-report.json
```

The SQLite backup path must be new. The copier preserves all IDs and JSON
originals/revisions, checks all rows before committing, refuses a nonempty
target and rolls back an interrupted transaction. It never modifies the source
SQLite. Keep its backup and the Chroma/model directories. Start the API with
the PostgreSQL connection to cut over. To roll back **before new decisions are
made**, stop the API, remove `DATABASE_URL`/`DATABASE_URL_FILE`, then start with
the original SQLite catalog. Decisions made after cutover need a separate reverse
migration; switching back alone would hide those newer decisions.

```powershell
& .\.venv\Scripts\python.exe -m scripts.smoke_postgres --report .local\postgres-smoke.json
```

This creates and removes only an isolated test container/catalog and compares
SQLite/PostgreSQL queries, restart persistence, audit relationships, revision
conflicts, nonempty-target refusal and transaction rollback.

## Docker delivery

Install/start Docker Desktop with Linux containers. Prepare Ollama, local CPU
embedding artifacts and demo credentials with the setup above before starting.
Do not run native services on ports 8000/8501 at the same time.

```powershell
& .\.venv\Scripts\python.exe -m scripts.prepare_docker
docker compose build
docker compose up -d
docker compose ps
```

The UI is http://127.0.0.1:8501 and API http://127.0.0.1:8000. Host-managed
Ollama stays on port 11434. Compose uses PostgreSQL, local persistent Chroma,
CPU embeddings and the image's deterministic Cppcheck. Database storage and
captured evidence use separate persistent volumes. Reviewed source and embedding
artifacts are mounted read-only. No credentials, model artifacts or user source
are copied into the image. Services run as an unprivileged user except the
official database initialization process. Published API/UI ports bind loopback;
PostgreSQL has no published port. Health checks report service liveness; model,
embedding and analyzer health is verified during actual requests.

`prepare_docker` reuses the existing credential mapping, registers only the demo
mount and creates protected local secret files under `.local/docker`. It never
prints credentials or overwrites an existing database password. Protect those
files with OS access controls. Add another repository only through administrator
configuration and an explicit read-only mount.

For a **fresh deployment requiring native history**, replace the initial
`docker compose up -d` above with the sequence below. Stop the native API first.
The PostgreSQL target must be empty and the backup path must be new. The current
verified deployment has already been migrated; do not repeat the copy into it.

```powershell
docker compose up -d postgres
docker compose run --rm --no-deps --volume D:/TataTech/.local/data/catalog.sqlite3:/migration/catalog.sqlite3:ro api python -m scripts.migrate_postgres --sqlite /migration/catalog.sqlite3 --backup /data/native-migration-backup.sqlite3 --report /data/native-migration-report.json
docker compose up -d api ui
```

Wait for PostgreSQL to become healthy before the migration command. Migration
preserves catalog history; use the UI's Index/re-index control after startup to
build Docker's separate active vector index. Existing historical runs retain
their captured evidence. Preserve the native SQLite/Chroma/model directories
and the application-volume backup. Without migration, a fresh deployment starts
with an empty history. Measured migration and restart results are recorded in
`docs/checkpoint3-progress.md`.

```powershell
docker compose stop
docker compose start
docker compose down
```

These preserve named data volumes. Never use `down --volumes` against operational
data. Model downloads are setup only; container runtime loads local hashed
artifacts and has no external model fallback. Native and Linux Cppcheck versions
are recorded separately; do not silently combine their quality measurements.

## Final reproducible evaluation

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -m scripts.evaluate_retrieval --report .local\final-retrieval.json
& .\.venv\Scripts\python.exe -m scripts.evaluate_final --report .local\final-evaluation.json
& .\.venv\Scripts\python.exe -m scripts.smoke_delivery --origin http://127.0.0.1:8000 --report .local\delivery-smoke.json
```

Do not overwrite `.local/review-evaluation.json`: it is the approved Checkpoint 2
baseline. A sanitized copy in `docs/evaluation/checkpoint2-baseline.json` supplies
the same frozen results on a fresh setup without private prompt artifacts.
Final evaluation preserves its four misses (`calculatePressure`,
`readActivePressure`, `activateSession`, `doubleFreeSample`) and the `readSensor`
safe false positive, even if a new run improves. Its 94.12% precision and 80%
recall describe only the fixed synthetic 20-defect/10-safe corpus. The rerun uses
unchanged labels/source and records hashes, settings, timings and all unsuccessful
capability cases. This is per-labeled-function precision; extra diagnoses on
already buggy functions have not been exhaustively adjudicated. Productivity
and downstream defect-leakage improvements remain **not measured**.

The double-free correction now trims optional related code, rules and analyzer
observations only when needed, rebuilds the allowed citation schema and
regenerates once. Required source/log evidence and strict validation remain;
unfittable corrections fail explicitly. `smoke_delivery` exercises live local
review/report APIs and tests human-decision storage in a disposable catalog,
without automatically accepting operational findings.

Measured results: `docs/checkpoint1-progress.md`, `docs/checkpoint2-progress.md`
and `docs/checkpoint3-progress.md`. API references:
[Ollama](https://docs.ollama.com/api/generate),
[Chroma](https://docs.trychroma.com/docs/collections/manage-collections),
[Tree-sitter](https://tree-sitter.github.io/py-tree-sitter/),
[Jina model card](https://huggingface.co/jinaai/jina-embeddings-v2-base-code).
Analyzer reference: [Cppcheck manual](https://cppcheck.sourceforge.io/manual.html).
Delivery references: [Streamlit testing](https://docs.streamlit.io/develop/api-reference/app-testing),
[Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

Final deployed acceptance: [walkthrough and limitations](docs/final-application-acceptance.md)
and [machine-readable results](docs/evaluation/final-application-acceptance.json).
Finding and history selectors use readable result/run numbers to distinguish
repeated analyses; technical IDs remain in details and exports. Runtime/workflow
checks passed, while recorded analysis-quality gaps leave overall acceptance
partial. These usability repairs do not improve model accuracy.
