# Eight-minute Case Study 4 presentation

## Before the presentation

Use the existing prepared local workspace; do not download models or rebuild
indexes during setup unless needed. Start Ollama, then in PowerShell:

```powershell
Set-Location D:\TataTech
docker compose up -d
docker compose ps
```

Open http://127.0.0.1:8501. Enter the existing private credential from
`.local/demo-token.txt` in the masked sign-in form, then press Sign in; do not project that file.
Select `demo_ecu`. The polish demonstration repository review is
`2d2280dd-9cfd-4f2a-b48d-4ac004e2220b` (04 Oct 2026, 12:08 IST).
The earlier v16 run `b436f20a-28d4-46a8-8340-630e49620692` is also preserved. Keep it as a fallback if a new run fails
or takes longer than the recorded 142.598 seconds. Timing is not guaranteed.
Use only synthetic demo source. Do not submit a human decision automatically.
For a strict eight-minute slot, open the retained explanation and diagnostic
reports while repository review runs; regenerate those only after it completes.
Do not queue concurrent LLM requests and assume fixed timing.

## Timed flow

| Time | Action | Explain |
|---|---|---|
| 0:00–0:40 | Overview: show repository, snapshot, seven files, 31 functions, parser status and local/private banner. | Credential authorization precedes retrieval. Source and embeddings stay local; repositories are read-only. |
| 0:40–1:00 | Click Index / re-index, then Review Entire Repository. | Content snapshots work for ordinary directories. One captured analyzer run; sequential bounded function prompts on local Qwen. |
| 1:00–1:50 | Analyze Source: Explain > Function Explanation, `src/brake_control.cpp`, `clampPressure`; run and inspect cited source. | Explain the visible behavior and branches; external contracts remain unknown. |
| 1:50–2:40 | Diagnostics: select Build log, `src/diagnostics.cpp`, `uninitializedCounter`; paste or import the local `docs/demonstrations/imported-build.log`, declare synthetic origin/tool, and ask “Explain the warning and warnings-as-errors failure with log citations.” Run interpretation. | Evidence is imported, never executed. Inspect source mapping, origin, snapshot, hypotheses, citations and limitations. Use the saved demonstration report if regeneration is insufficient. |
| 2:40–3:30 | Repository Review: return to the new run; show progress or completed coverage, outcomes, severity/category counts and timings. | Every analyzable function has an outcome. FAILED and INSUFFICIENT_EVIDENCE are distinct from NO_SUPPORTED_FINDING; none establishes safety. |
| 3:30–4:30 | Filter category Security and select `insecureFormat`. Expand All supplied evidence to inspect Source, Static analysis and guidance; inspect the actual format-string call, hypothesis and remediation. | Backend support is corroboration, not a correctness probability. Security observations require source citations. |
| 4:30–5:10 | Clear filter, choose a rule-supported candidate. Show rule ID/title/body and relevance. Open Review > Coding-standard / MISRA-oriented review assistance under Analyze Source. | These are original demo rules. Read the visible notice; do not claim MISRA compliance or certified-tool replacement. |
| 5:10–6:10 | Human reviewer inspects one candidate and explicitly chooses Accept or Edit, uses the readable fields if editing, adds a note, then saves. Keep location/citations read-only unless using advanced JSON. Show immutable original and authenticated revision/history. A reviewer may Reject the `readSensor` false positive after inspecting it. | Accept/Edit/Reject changes workflow history, never source. Edited citations are validated. Do not accept a defect solely because its references are valid. |
| 6:10–6:50 | History & Reports: select the repository run and download readable HTML and complete JSON; open HTML locally and show browser Print; show reviewer dispositions, original snapshots and limitations. | ACCEPTED/EDITED history is optional untrusted precedent; pending/rejected history cannot become retrieval guidance. Current source wins. |
| 6:50–7:30 | Show Review > Performance observations and report counts. | Static/source observations are supported; this corpus produced zero performance findings. No profiler or speedup is claimed. All six stakeholder roles share this application. |
| 7:30–8:00 | Show fixed-corpus metrics and remaining misses from the alignment report. | Polish demonstration and v16: 15/20 detected, one safe false positive, 93.75% per-labeled-function precision, 75% recall. Earlier results are preserved and not universal accuracy. Debug resolution time and defect leakage are NOT MEASURED. |

End at eight minutes. Do not demonstrate Git/PR/CI execution, automatic edits,
branch/commit operations, merges or releases. If a live result fails, show its
explicit outcome and retained cited report rather than describing it as success.

The polish pass changes usability, not model accuracy. The five current misses
are calculatePressure, readActivePressure, activateSession, useFreedSample and
doubleFreeSample; readSensor remains the safe-function false positive. Earlier
four Checkpoint 2 misses and all unsuccessful runs remain recorded. Use the
separate polish QA and diagnostic result files in docs/demonstrations; a
successful example does not replace the earlier capability evaluation set.
