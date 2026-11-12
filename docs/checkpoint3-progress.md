# Checkpoint 3 — human review and delivery

The user approved Checkpoint 2 and authorized this phase on 2026-10-03.
AGENTS.md and PROJECT_PLAN.md retain the frozen Case Study 4 scope. Only original
demo engineering rules are used; no actual MISRA text or compliance claim.

## Implemented behavior

Streamlit offers authorized repository/file/function selection, indexing,
review, explanations, Q&A, imported diagnostics, separate evidence panels,
visible limitations, history and report download. Untrusted text renders as
text/code. Accept/Edit/Reject creates authenticated, timestamped revisions;
request-supplied reviewer identity is forbidden. Originals remain immutable.
Edited evidence validates against the original captured snapshot even after
re-indexing. Conflicting revisions require a reload. Historical candidates
failing current validation are marked and cannot be accepted without a valid edit.

SQLite/PostgreSQL share catalog operations. Migration preserves IDs/originals/
history, checks all copied rows, refuses nonempty targets, rolls back interrupted
copies and retains SQLite. Docker provides local API/UI, private PostgreSQL,
persistent Chroma and app storage, read-only source/model mounts, CPU embeddings
and host-managed Ollama. Hash-verified local model code uses a separate writable
application cache. Only setup downloads dependencies; runtime has no external
inference fallback. Container host inference requires an explicit local gateway.

No Git-diff workflows, PR/CI automation, automatic fixes, agents, graph databases,
Kubernetes, or repository script/build/hook execution was added.

## Preserved baseline and unchanged-corpus rerun

The private `.local/review-evaluation.json` is unchanged. Its SHA-256 is
`ce18932b5d53da8b3b1c61f3fbec4953063e5958566aa0186c54be9560ce0ada`.
`docs/evaluation/checkpoint2-baseline.json` preserves a sanitized copy for fresh
setup. The final rerun uses unchanged labels and records source/rule hashes.

| Fixed synthetic measurement | Approved Checkpoint 2 | Checkpoint 3 rerun |
| --- | ---: | ---: |
| Defective / safe functions | 20 / 10 | 20 / 10 |
| Found / missed defect cases | 16 / 4 | 17 / 3 |
| Safe-function false positives | 1 | 1 |
| Precision per labeled function | 94.12% | 94.44% |
| Known-defect recall | 80% | 85% |
| Safe-function false-positive rate | 10% | 10% |
| Mean review time | 4.133 seconds | 5.046 seconds |
| Failed review runs | 1 | 0 |
| Runs with rejected attempts | 2 | 2 |
| Malformed-output / analyzer-failure runs | 0 / 0 | 0 / 0 |

These numbers describe only the fixed synthetic corpus, not universal model
accuracy. Precision counts labeled functions, not an exhaustive adjudication of
every finding. Startup and local workloads affect latency; these are observed
means, not guaranteed warm-service timings. Native Cppcheck is 2.22.0; all 30
reviews expose degraded coverage without a real build configuration and with
one analyzer record lacking source location. Linux Cppcheck is pinned separately
to Debian 2.10-2; native metrics must not be attributed to that tool version.

All four original misses remain recorded: `calculatePressure`,
`readActivePressure`, `activateSession`, `doubleFreeSample`. The first three
remain missed in the rerun. `readSensor` remains the safe false positive:
returning a nullable pointer does not itself establish an unchecked dereference.
Manual inspection also found an extra null-pointer allegation on
`leakingSessionFile` overlooking its existing guard. That error on an already
defective function is outside the safe-function false-positive metric and is
not hidden behind the precision number. The proposed `strncpy` remediation for
`copyDiagnostic` needs termination/capacity review. No finding was auto-accepted.

## doubleFreeSample correction

The original first attempt cited a rule with the wrong category. Correction
text plus optional evidence required 6242 conservative input units, over the
6144 budget. This was a retry-budget failure, not GPU OOM. Review retries did
not trim optional evidence.

The repair retains all required selected source/log evidence, removes optional
related source first, then rules, then analyzer observations only when needed,
rebuilds the allowed citation schema and regenerates at most once. It never
repairs invented citations or loosens validation. The rerun rejected the wrong
rule, then cited the two actual `free` lines, Cppcheck and RES-001. Correction
estimate: **6018 <= 6144**; actual Ollama input: **1563 tokens**. The baseline
failure remains recorded.

## Completed verification

- **75 regressions passed**, including earlier phases, ordinary/Git directories,
  change/delete/re-index, authorization/path escapes, interrupted publication,
  stale/fabricated evidence, injection, bounded contexts, dependency failures,
  immutable reviewer history, identity spoofing and Streamlit workflows.
- **20/20 actual offline CPU retrieval questions passed**; exact/top-k 1.0,
  zero duplicate/stale active chunks, change/delete/reopen checks passed.
- **9 real PostgreSQL 16.13 isolated checks passed**: all-table/query equivalence,
  restart persistence, retained SQLite, nonempty refusal, interrupted rollback,
  original IDs/contents, revision conflicts and removal of rejected revisions
  from approved-finding retrieval.
- **8 live native API delivery checks passed**. Reviewer actions used a
  disposable captured-run catalog; operational candidates remain pending.
- **8 live Docker API delivery checks passed**, using CPU embeddings, Linux
  Cppcheck and the host Ollama gateway. The double-free review produced a
  validated candidate. These checks are separate from the native quality corpus.
- **11 Docker operational checks passed**: read-only source/model mounts,
  writable app storage, unprivileged API (UID 10001), loopback publication,
  explicit database-down failure, authorization before database access,
  snapshot/report persistence across restart, dependency consistency, and no
  credentials or sampled source body in inspected service logs.
- **4 actual dependency/authorization/context failure checks passed**.
- Final provenance recheck validated **22 findings, 8 claims, 56 references**,
  with zero invalid validated citations in this corpus. Provenance is not
  diagnosis correctness. Ten prompts and ten findings were selected and inspected,
  including false positives, corrective retry and remediation limitations.
- Native UI credential boundary/layout was inspected in the browser; Streamlit
  AppTest exercised source panels and all three reviewer actions.

The fixed capability set answered module summary and compiler/runtime diagnostics;
function explanation, Q&A and imported CI/build interpretation returned
`INSUFFICIENT_EVIDENCE`. A supplemental `clampPressure` branch explanation
succeeded, while several supplemental Q&A questions also returned insufficient
evidence. Supplemental demonstrations do not replace unsuccessful fixed cases.
The UI's Code Q&A uses a question on the existing explanation endpoints, as
specified in PROJECT_PLAN.md. A supplemental question about the negative branch
of `clampPressure` returned one validated cited answer through that route. The
fixed dedicated Q&A case remains recorded as `INSUFFICIENT_EVIDENCE`.

Private artifacts: `.local/final-evaluation.json`, `final-retrieval.json`,
`final-inspection.json`, `final-manual-inspection.txt`, `postgres-smoke-final.json`,
`native-delivery-smoke.json`, `final-failure-smoke.json`,
`docker-delivery-smoke.json`, `deployment-smoke.json`, `native-migration-report.json`,
`checkpoint3-tests-final.txt`. Protect prompt/response artifacts and exports.
`docs/evaluation/checkpoint3-results.json` is the sanitized measured summary;
it contains no source bodies, prompts, model responses or credentials.

## Native-history migration and deployed services

The complete native SQLite history was copied into the deployment's PostgreSQL
16.13 before API startup: **59 analysis runs, 5 findings, 3 snapshots**, one
repository/user/permission/active pointer, and zero pre-existing reviewer actions.
All copied table contents matched, with SHA-256
`13d1aca6350d3871d5e995cd89608aefa909fcd109da7f7c194f53b48113adaa`.
Native SQLite, Chroma and model artifacts remain retained. The consistent backup
is `/data/native-migration-backup.sqlite3` in the persistent application volume;
the verified report is exported to `.local/native-migration-report.json`.
Rollback after new PostgreSQL decisions requires reverse migration rather than
simply switching back to the older SQLite database.

Docker indexing rebuilt the active vector index in its own application volume.
Historical native runs retain their original captured snapshots; their evidence
is never checked against newly changed source. Migration preserved history IDs
and original contents. New Docker reviews are additional pending candidates.

API, Streamlit and PostgreSQL are healthy after the tested shutdown/restart.
UI: http://127.0.0.1:8501; API: http://127.0.0.1:8000. PostgreSQL is private to
Compose. Enter the existing local credential in the UI; it is never printed in
reports. Docker build uses the pinned Linux dependency lock and base-image digest.
Cppcheck 2.10 in Docker is recorded separately from native 2.22.0. Ollama 0.35.1
uses the recorded local Qwen 7B Q4_K_M digest. The independent native GPU/context
smoke passed at 8192 context tokens with 5133943438 bytes reported in VRAM.

## Reproduction, limitations and approval gate

README.md covers native setup/UI, migration/rollback, Docker startup/shutdown,
and fixed evaluation. Real productivity measures—defect-resolution time,
review throughput and downstream defect leakage—are **NOT_MEASURED**. A separate
fresh physical machine has not been tested. A clean container build and deployed
runtime were tested with the prepared local model artifacts. The three remaining
misses, safe-function false positive, additional semantic errors and insufficient
fixed capability answers above remain limitations requiring human judgment.

## Conditional-approval follow-up: imported build log

After conditional Checkpoint 3 approval, the user requested one successful
imported build/CI-log interpretation demonstration before final sign-off.
The existing deployed `POST /diagnostics/interpret` endpoint imported
`docs/demonstrations/imported-build.log`, a synthetic local build log. No compiler,
build command or CI pipeline was executed; no application code, model settings,
validation rules or automation capabilities were changed.

The successful persisted run is `ded88ff8-1181-4f65-a4bd-f2dc352bc192`, on Docker
snapshot `4489ceef577d88d9b56d83b98f7bd986f7baad4b11c81b65c1705c9c7c50b104`.
It returned **ANSWERED**, **two cited hypothesis claims**, **one model attempt**,
**zero validation rejections**, in **6.486 seconds**:

- Log line 2 reports that `count` may be used uninitialized in
  `uninitializedCounter`. The selected captured function visibly leaves `count`
  unassigned when `enabled` is false (source lines 27–29). The model's first claim
  cites the imported warning; the supplied source corroborates that explanation.
- Log line 3 reports the warnings-as-errors policy and compile-step exit code 1.
  The second claim cites that exact line to explain the reported build failure.

Both log citations resolve to evidence ID `D78532f4d04ad6626`, with exact quoted
lines. An independent pass through the existing deterministic validator checked
IDs, ranges, quotes, snapshot association and qualified diagnostic claims. The
structured report was retrieved from PostgreSQL and matched the returned run.
`docs/demonstrations/imported-build-result.json` records the log, cited claims,
limitations and successful checks. Origin/snapshot association remain
user-declared and independently unverified; this is an interpretation of
synthetic evidence, not proof of real compilation or pipeline execution.

Two earlier supplemental requests returned `INSUFFICIENT_EVIDENCE`:
`a928b207-99c2-41fb-b1b6-5db817a38e11` (one citation rejection, then empty claims)
and `fbdda4ba-388f-4c0e-839e-e786c8d54f41` (empty claims). Their private run
artifacts are retained under `.local/imported-build-demo-attempt1.json` and
`attempt2.json`, and all three runs persist in history. The successful request
uses concise warning/policy/failure evidence. It does not replace the fixed
CI/build evaluation failure or establish general reliability across logs.
The approved baseline, final fixed evaluation, corpus labels/source and demo
rules were hash-checked unchanged. No application tests were rerun for this
evidence-and-documentation-only follow-up; the prior 75-test result remains
separate from this live capability demonstration.

Checkpoint 3 implementation and local verification are complete. Conditional
approval is recorded; this additional demonstration is complete and final user
sign-off is pending. No subsequent phase or additional scope is authorized.
AGENTS.md requires: "At each phase gate, record measured results, show working
success/failure behavior, and stop for the user's explicit checkpoint approval
before beginning the next phase."
