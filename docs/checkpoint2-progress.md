# Checkpoint 2 â€” implementation and verification

Checkpoint 1 was approved by the user. Checkpoint 2 is implemented and awaiting
the user's review. Checkpoint 3 has not started.

## Scope confirmation

Before implementation, AGENTS.md and PROJECT_PLAN.md were inspected against the
frozen Case Study 4 boundary. Their phase tasks, numbered rechecks and completion
gates retain repository access and engineering-evidence interpretation without
Git-diff review, PR/CI automation, branch operations, automatic fixes, application
agents, graph databases or Kubernetes. Snapshots work with ordinary directories
and Git working trees; Git metadata is optional and currently not collected.
The only scope-document edits in this checkpoint clarify the user's explicit
MISRA restrictions. Section numbering and the three approval gates are retained.

The six original rules in rules/coding_rules.md are unchanged. Their SHA-256 is
2675b8fa41cf2c693e4b9c64e403d4593daffd2ef17e84fb790657b8b7077a56.
No actual MISRA rule text was downloaded, copied, embedded or reproduced, and
no MISRA compliance is claimed. Future support requires explicitly supplied
approved/licensed guidance. Demo rules cannot establish certification.

## Implemented behavior

- Credential/path authorization precedes source retrieval, analysis and inference.
- Cppcheck uses a disposable copy of captured authorized source, fixed argument
  arrays, bounded time/output and normalized snapshot-linked warning IDs. It runs
  no repository scripts, hooks, build commands, addons or compilation databases.
  External/dynamic/traversal includes are rejected. Source is never executed.
- FastAPI provides repository indexing/status/selectors, function/file review,
  function/module explanation, code Q&A, imported diagnostic interpretation and
  authorized candidate-finding history. The pilot binds to loopback.
- Context contains selected source, bounded related code, approved rules and
  relevant analyzer evidence. Dependency/control-flow descriptions are limited
  to supplied calls, branches and headers; unresolved relationships remain unknown.
- Separate review/explanation schemas constrain model output. The model selects
  supplied line IDs; deterministic resolution supplies exact captured quotes,
  locations and functions. Unknown IDs, wrong snapshots, fabricated locations,
  mismatched rule categories and unrelated analyzer support are rejected.
- One bounded regeneration is permitted after rejection. Invalid output is never
  silently repaired. Security findings can use an empty applicable-rule list
  because the existing demo rules contain no security-category guidance.
- Imported compiler/build/runtime/CI text records stable IDs, timestamps,
  declared origin/tool and snapshot association. Source mappings are checked;
  declared provenance remains unverified. Interpretations are qualified hypotheses.
  Commands in imported logs are data and are never executed.
- SQLite persists runs, original structured output, evidence and candidate
  findings. Every finding remains PENDING. Accept/Edit/Reject, reviewer revisions,
  Streamlit, PostgreSQL and Docker remain Checkpoint 3 work.

## Verification results

The complete deterministic suite passed twice: **65 tests**, including all Checkpoint 1
tests. Storage tests use a deterministic embedding double; client-failure and
fabrication tests use synthetic model responses. The suite also ran real pinned
Cppcheck. These tests do not establish live-model semantic quality.

Actual CPU Jina retrieval evaluation passed all 20 fixed questions: exact lookup
1.0, relevant top-k 1.0, duplicate rate 0 and stale active chunk rate 0. Unchanged,
changed and deleted files, reopening/persistence, denied access and offline
embedding runtime passed. Tests cover ordinary directories, Git working trees,
dirty source changes, junction/path escapes, parser fallback and interrupted
publication without introducing a Git-diff workflow.

The local HTTP smoke test passed seven checks: liveness, missing-credential denial,
unregistered-root denial, indexing, snapshot/status, local schema and authorized
history. Native failure demonstrations passed unknown-identity denial before
storage, missing Cppcheck, connection-refused local model and context overflow
before inference. Ollama itself was left running; an unused loopback port was
used to demonstrate real transport failure.

The suite rejects fabricated IDs/files/functions/lines/quotes/rules/analyzer
references, wrong-category analyzer support, unsupported diagnostic mappings,
stale evidence, malformed JSON and context overflow. It tests source/log prompt
injection, denied history access, dependency failures and immutable source.
No unauthorized content reached a model call and no invalid citations reached
validated output in these tests. This is not a universal security guarantee.

Dependency consistency and Python compilation checks passed. A Windows disposable
database cleanup race was reproduced and addressed with a bounded fixture cleanup
retry after shutdown. Filtered queries on buffered one-vector Chroma collections
intermittently failed. An isolated comparison reproduced the error with default
buffering; 40 equivalent databases using batch size 1 and sync threshold 1
completed 20 alternating source/rule queries each without that error. Actual HNSW
files were observed with the new setting. The adapter applies this persistence
setting to new and existing pilot collections. Operational data was backed up
before the change; its active snapshot was preserved. Repeated tiny-index queries
and restart, the complete suite twice, actual CPU retrieval and native API/failure
checks passed afterward. API handling also returns an explicit vector dependency
failure. These finite checks do not prove that all future storage failures are
eliminated.
The pilot remains a single-worker application with serial indexing commands.

## Live-model quality

The final fixed corpus contains 20 defect functions and 10 safe functions.
Expected category, file/range, assumptions, relevant demo rule and independently
measured Cppcheck support are recorded outside retrieved source in the fixtures.
The actual Qwen/Ollama run is recorded in .local/review-evaluation.json; measured
measurements are listed below.

| Measurement | Final live result |
| --- | --- |
| Labeled functions | 20 defective; 10 safe |
| Expected-category detections / misses | 16 / 4 |
| Safe-function false positives | 1/10 (10%) |
| Precision on labeled functions | 94.12% |
| Known-defect recall | 80% |
| Correct findings with analyzer / AI-only support | 9 / 7 |
| Mean review duration | 4.133 seconds |
| Runs with rejected attempts | 2/30 |
| Failed review runs | 1/30 |
| Malformed output / analyzer failure | 0/30 / 0/30 |
| Validated candidate findings | 21; all PENDING |

Misses were calculatePressure, readActivePressure, activateSession and
doubleFreeSample. The last failed after an unrelated rule selection; bounded
regeneration could not fit the conservative input budget. The security case
regenerated successfully with no unrelated demo rules. Cppcheck remained degraded
because its global informational report lacked a source location and no build
configuration was supplied; zero failed analyzer runs does not mean full coverage.
Reported input token usage ranged from 770 to 1650, within 6144.


Precision is measured per labeled function: expected-category detection divided
by expected-category detections plus safe-function false positives. Additional
categories on already defective functions are not fully labeled, so this is not
finding-level semantic precision. Citation validity measures provenance rather
than whether a diagnosis or remediation is correct. All findings require review.
The 30-function model benchmark preceded the final persistence setting change;
the unchanged cosine retrieval was re-evaluated afterward on all 20 questions.
The quoted review latency measures that recorded model run rather than a new
benchmark of the final persistence setting.

Manual inspection covers ten complete selected prompt packages and ten findings,
including pointer, boundary, initialization, resource, state, security and injected
source examples. Source quotes and analyzer IDs match the captured snapshot.
The known false positive is readSensor: returning a nullable pointer is valid;
the model hypothesizes an unchecked caller without supplied caller evidence.
Suggestions involving strncpy require reviewer scrutiny of capacity and explicit
termination. Caller-contract assumptions can cause additional candidate noise.

Function/module explanations, original PTR-001 guidance, code questions and
compiler/runtime/CI-log interpretations were exercised live. Some requests return
INSUFFICIENT_EVIDENCE despite available source. This model limitation is exposed;
an empty answer is never displayed as a clean review or a supported explanation.
Successful and insufficient outputs are retained, rather than selecting only
successful demonstrations. Model-reported limitations are labeled separately
from verified backend limitations and may themselves contain semantic mistakes.

## Artifacts and reproduction

Use the commands in README.md. Runtime/setup artifacts are:

| Component | Recorded choice |
| --- | --- |
| Ollama / model | Ollama 0.35.1; qwen2.5-coder:7b Q4_K_M |
| Model digest | dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364 |
| Context | 8192 total; 6144 input; 1536 output; 512 uncertainty |
| Hardware | RTX 4060 laptop; CPU embeddings; GPU allocation verified in Checkpoint 1 |
| Jina | Existing pinned/hash-verified local artifact from Checkpoint 1 |
| Cppcheck | 2.22.0; official MSI SHA-256 3929162bab7e71d1b9b18708ec054fb0188bfc8ea1660979ed95837f5a9f547b |
| API/schema | FastAPI 0.116.1; Pydantic 2.13.5 |
| Vector storage | Chroma 1.0.20 |
| Prompt version | case4-v13 |
| Corpus snapshot | 8f781c9f82d1bc827b7aff6b2d327d307d01d2ffd248fcbefcc1a4569c0d3a04 |

Local reports: checkpoint2-tests.txt, checkpoint2-tests-repeat.txt,
checkpoint2-retrieval.json, api-smoke.json, chroma-probe-results.json,
review-failure-smoke.json, review-evaluation.json, explanation-evaluation.json,
function-demo.json and security-demo.json under .local. Earlier versioned reports
are retained for comparison. Report prompt versions identify their implementations.
The full evaluation intentionally stores synthetic prompts/responses for inspection;
routine application logs do not. Protect these reports as captured source.

Evaluation resets only disposable copies/databases. Temporary directories
left after cleanup/initialization errors were verified and removed. Operational source,
credentials, embeddings, databases and reports were preserved.

This is a small synthetic engineering pilot, not production automotive validation.
Fresh-machine setup, encryption, concurrent indexing, deployment, productivity,
defect leakage and real vehicle outcomes are not established by this checkpoint.

## Approval gate

Await explicit Checkpoint 2 approval before starting Checkpoint 3, as requested
by the user and required by AGENTS.md. The results and remaining model/storage
limitations above are the concrete material for that decision.
