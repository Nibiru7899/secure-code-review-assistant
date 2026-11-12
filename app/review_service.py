from datetime import datetime, timezone
import json
from time import perf_counter
import uuid
import threading

from app.support import evidence_support
from app.retrieval.history import approved_evidence

from pydantic import ValidationError

from app.llm.context import build_context, ContextOverflow, prompt, estimated_tokens
from app.llm.ollama_client import OllamaError
from app.llm.prompts import system_for, TEMPLATE_VERSION
from app.llm.schemas import ReviewResponse, ExplanationResponse
from app.retrieval.retriever import Retriever
from app.validation.evidence_validator import validate, InvalidEvidence
from app.validation.citation_resolver import citation_map, resolve

MODEL = "qwen2.5-coder:7b"
DIGEST = "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364"


class TargetNotFound(ValueError):
    pass


class ReviewService:
    def __init__(self, indexer, analyzer, client, input_budget=6144, quality='baseline', guard_policy='annotation'):
        self.indexer, self.analyzer, self.client = indexer, analyzer, client
        self.input_budget = input_budget
        self.model_lock = threading.Lock()
        if quality not in ('baseline', 'ast', 'hybrid', 'verified', 'guarded'):
            raise ValueError('Unknown analysis quality mode')
        if guard_policy not in ('annotation', 'strict'):
            raise ValueError('Unknown AST guard policy')
        self.quality = quality
        self.guard_policy = guard_policy

    def analyze(self, token, request, mode, captured_manifest=None, captured_analyzer=None):
        started = perf_counter()
        scope = self.indexer.permissions.authorize(token, request.repository)
        if request.file:
            scope.resolve(request.file)
        # Capture one immutable manifest; retrieval must return this same snapshot.
        with self.indexer.lock:
            self.indexer.open_storage(scope)
            manifest = (self.indexer.catalog.snapshot(scope, captured_manifest["snapshot"]) if captured_manifest
                        else self.indexer.catalog.current(scope))
        if manifest is None:
            raise ValueError("No active index for this authorized scope")
        if request.snapshot != manifest["snapshot"]:
            raise ValueError("Snapshot is stale or unknown; select the active indexed snapshot")
        if mode == "diagnostics" and request.diagnostic_snapshot not in (None, manifest["snapshot"]):
            raise ValueError("Imported diagnostics are associated with another snapshot")
        query = request.question or request.function or request.file or "code evidence"
        retrieval_started = perf_counter()
        retrieved = Retriever(self.indexer).retrieve(token, request.repository, query,
                    file=request.file, symbol=request.function, signature=request.signature, k=3,
                    captured_snapshot=manifest["snapshot"] if captured_manifest else None, hybrid=self.quality in ('hybrid', 'verified'))
        if retrieved["snapshot"] != manifest["snapshot"]:
            raise ValueError("Index changed during retrieval; retry against the new snapshot")
        if retrieved["retrieval_status"] == "not_found":
            raise TargetNotFound("Selected target does not exist in the authorized captured snapshot")
        if retrieved["retrieval_status"] != "ok":
            raise ValueError("Target ambiguous; select a file/function/signature")
        run = {"id": str(uuid.uuid4()), "created": datetime.now(timezone.utc).isoformat(),
               "repository": scope.repository, "snapshot": manifest["snapshot"], "user": scope.user,
               "mode": mode, "outcome": "FAILED", "findings": [], "claims": [], "evidence": [],
               "limitations": [], "model": MODEL, "model_digest": DIGEST,
               "prompt_version": TEMPLATE_VERSION, "validation_rejections": 0, "model_status": "not_requested"}
        run['quality_pipeline'] = self.quality
        if self.quality in ('ast', 'hybrid', 'verified'): run['code_context_version'] = 'syntax-context-v2'
        run['retrieval_ranking'] = retrieved.get('ranking')
        run['retrieval_seconds'] = round(perf_counter() - retrieval_started, 4)
        run['primary_model_calls'] = 0
        run['primary_generation_seconds'] = []
        analyzer = (captured_analyzer if captured_analyzer is not None else self.analyzer.run(manifest)) if mode.startswith("review") else {
            "status": "not_requested", "version": None, "findings": [],
            "limitations": ["Explanation/diagnostic task; static analysis was not requested"]}
        run["analyzer"] = analyzer
        try:
            history = approved_evidence(self.indexer, token, request.repository, manifest, retrieved["target"]) if mode.startswith("review") else []
            context = build_context(mode, request, retrieved, analyzer, manifest, self.input_budget, history, code_aware=self.quality in ('ast', 'hybrid', 'verified'))
            if self.quality in ('ast', 'hybrid', 'verified'):
                run['code_facts'] = context.get('code_facts', [])
            run["evidence"] = context["evidence"]
            run["limitations"] = context["limitations"]
            run["coverage"] = {"selected_source_ranges": [{k: item[k] for k in ("file", "function", "start_line", "end_line")}
                              for item in context["evidence"] if item["kind"] == "source" and item.get("target")],
                              "required_target_included": True}
            tags = self.client.request("tags").get("models", [])
            if not any(m.get("name") == MODEL and m.get("digest") == DIGEST for m in tags):
                raise OllamaError("Pinned local model is missing or its digest changed")
            review = mode.startswith("review")
            schema = ReviewResponse.model_json_schema() if review else ExplanationResponse.model_json_schema()
            citations = citation_map(context)
            if review:
                fields = schema["$defs"]["GeneratedFinding"]["properties"]
                fields["source_ids"]["items"]["enum"] = [i for i, (e, _) in citations.items() if e["kind"] == "source" and e.get("target")]
                analyzer_ids = [i for i, (e, _) in citations.items() if e["kind"] == "analyzer"]
                if analyzer_ids:
                    fields["analyzer_ids"]["items"]["enum"] = analyzer_ids
                else:
                    fields["analyzer_ids"]["maxItems"] = 0
                rules = [e["id"] for e in context["evidence"] if e["kind"] == "rule"]
                if rules:
                    fields["applicable_rules"]["items"]["enum"] = rules
                else:
                    fields["applicable_rules"]["maxItems"] = 0
            else:
                schema["$defs"]["GeneratedClaim"]["properties"]["evidence_ids"]["items"]["enum"] = list(citations)
                if mode == "diagnostics":
                    schema["$defs"]["GeneratedClaim"]["properties"]["kind"]["enum"] = ["hypothesis"]
            feedback = ""
            for attempt in range(2):
                generation_started = perf_counter()
                with self.model_lock:
                    run['primary_model_calls'] += 1
                    raw = self.client.request("generate", {"model": MODEL, "system": system_for(mode),
                        "prompt": prompt(context) + feedback, "format": schema, "stream": False,
                        "keep_alive": "5m", "options": {"num_ctx": 8192, "num_predict": 1536, "temperature": 0}})
                run['primary_generation_seconds'].append(round(perf_counter() - generation_started, 4))
                run["model_attempts"] = attempt + 1
                run["model_status"] = "responded"
                count = raw.get("prompt_eval_count")
                run["input_tokens"] = count
                run["output_tokens"] = raw.get("eval_count")
                if raw.get("model") != MODEL or raw.get("done") is not True:
                    raise OllamaError("Model response identity/completion is unverified")
                if raw.get("done_reason") == "length":
                    raise OllamaError("Generation exhausted the output budget")
                if type(count) is not int or not 0 < count <= self.input_budget:
                    raise ContextOverflow("Reported model input tokens are unverified or exceed budget")
                try:
                    # Derive run metadata; do not repair or fill model citations.
                    if review:
                        parsed = ReviewResponse.model_validate_json(raw.get("response", ""))
                    else:
                        parsed = ExplanationResponse.model_validate_json(raw.get("response", ""))
                    response = resolve(parsed, context, review)
                    response = validate(response, context, manifest)
                    run["generated_output"] = parsed.model_dump()
                    break
                except (ValidationError, InvalidEvidence) as exc:
                    run["validation_rejections"] += 1
                    reason = str(exc) if isinstance(exc, InvalidEvidence) else "Malformed structured output"
                    run.setdefault("validation_errors", []).append(reason)
                    if attempt:
                        raise
                    correction = ("source_ids must select target source LINE IDs such as S1L10; analyzer_ids must use supplied IDs. applicable_rules must match the finding category; security has no matching demo rule, so use an empty applicable_rules array. Rules are optional when none applies."
                        if review else "evidence_ids must select supplied LINE IDs. Function names must match the cited source's function metadata or visible quoted calls. Correct the mismatched claim and keep supported explanations.")
                    feedback = ("\nAUTHORIZED CORRECTION: Previous output rejected: " + reason
                        + ". Regenerate from the same evidence. " + correction + " Do not guess or copy invalid citations.")
                    if estimated_tokens(context) + len(feedback.encode()) > self.input_budget:
                        context = dict(context, evidence=list(context["evidence"]),
                            limitations=context["limitations"] + ["Optional evidence omitted to fit bounded correction; selected source retained"])
                        # Related code first, then rules, then analyzer observations.
                        # Required source/log evidence is never silently truncated.
                        for kind in ("historical", "source", "rule", "analyzer"):
                            for item in list(reversed(context["evidence"])):
                                if estimated_tokens(context) + len(feedback.encode()) <= self.input_budget:
                                    break
                                if item["kind"] == kind and not item.get("target"):
                                    context["evidence"].remove(item)
                        run["evidence"] = context["evidence"]
                        run["limitations"] = context["limitations"]
                        if review:
                            available = citation_map(context)
                            fields["source_ids"]["items"]["enum"] = [i for i, (e, _) in available.items() if e["kind"] == "source" and e.get("target")]
                            for field, kind in (("analyzer_ids", "analyzer"), ("applicable_rules", "rule")):
                                ids = [e["id"] for e in context["evidence"] if e["kind"] == kind]
                                fields[field]["items"].pop("enum", None)
                                fields[field].pop("maxItems", None)
                                if ids:
                                    fields[field]["items"]["enum"] = ids
                                    fields[field]["maxItems"] = 3 if kind == "analyzer" else 6
                                else:
                                    fields[field]["maxItems"] = 0
                        else:
                            schema["$defs"]["GeneratedClaim"]["properties"]["evidence_ids"]["items"]["enum"] = list(citation_map(context))
                    if estimated_tokens(context) + len(feedback.encode()) > self.input_budget:
                        run["limitations"].append("Corrective regeneration cannot fit the input budget; rejected output is not repaired")
                        raise
                    run["corrective_input_estimate"] = estimated_tokens(context) + len(feedback.encode())
            if review and self.quality == 'guarded' and response.findings:
                from app.analysis.ast_guard import apply
                response, run['ast_guards'] = apply(response, manifest, self.guard_policy)
                response = validate(response, context, manifest)
                run['guard_seconds'] = sum(r['ast_guard_result']['seconds'] for r in run['ast_guards'])
                run['guard_policy'] = self.guard_policy
                if not response.findings:
                    run['limitations'].append('Local syntax contradicts candidate assertions; suppression does not establish safe code')
            if review and self.quality == 'verified' and response.findings:
                from app.analysis.candidate_verifier import verify, VERSION as VERIFIER_VERSION
                effective = []
                run['candidate_verifications'] = []
                run['verifier_metrics'] = {'calls': 0, 'seconds': [], 'input_tokens': []}
                for finding in response.findings:
                    record = {'original_candidate': finding.model_dump(), 'effective_candidate': None}
                    try:
                        accepted, verdict = verify(finding, context, manifest, self.client, self.model_lock, MODEL, self.input_budget, run['verifier_metrics'])
                        record['verifier_result'] = verdict
                        if accepted:
                            effective.append(accepted)
                            record['effective_candidate'] = accepted.model_dump()
                        record['result'] = {'CONFIRM': 'CONFIRMED_CANDIDATE', 'RECLASSIFY': 'RECLASSIFIED_CANDIDATE',
                                            'REJECT': 'VERIFIER_REJECTED', 'INSUFFICIENT': 'INSUFFICIENT_EVIDENCE'}[verdict['decision']]
                    except (ValidationError, InvalidEvidence, ContextOverflow, OllamaError) as exc:
                        record['result'] = 'INSUFFICIENT_EVIDENCE'
                        record['verifier_result'] = {'decision': 'INVALID_OR_UNAVAILABLE', 'reason': str(exc), 'version': VERIFIER_VERSION}
                        run['limitations'].append('Candidate verifier failed or lacked evidence; original retained for audit, not published as validated')
                    run['candidate_verifications'].append(record)
                response = response.model_copy(update={'findings': effective, 'outcome': 'CANDIDATES' if effective else
                    ('INSUFFICIENT_EVIDENCE' if any(r['result'] == 'INSUFFICIENT_EVIDENCE' for r in run['candidate_verifications']) else 'NO_SUPPORTED_FINDING')})
                if not effective:
                    run['limitations'].append('No candidate survived verification; verifier rejection does not establish safe code')
            run["outcome"] = response.outcome
            if response.outcome == "INSUFFICIENT_EVIDENCE":
                run["limitations"].append("Local model returned no supported cited answer; no conclusion is established")
            run["claims"] = [c.model_dump() for c in response.claims]
            run["model_limitations"] = response.limitations
            if response.limitations:
                run["limitations"].append("Model-reported limitations are unverified interpretations; see model_limitations")
            for finding in response.findings:
                item = finding.model_dump()
                item.update(id=str(uuid.uuid4()), run_id=run["id"], snapshot=manifest["snapshot"],
                            repository=scope.repository, disposition="PENDING",
                            support="ANALYZER-SUPPORTED" if any(e.id.startswith("A") for e in finding.evidence)
                            else "AI-ONLY CANDIDATE")
                item["evidence_support"] = evidence_support(item)
                item["root_cause"] = item["root_cause"] or item["explanation"][:1200]
                if item["category"] == "security":
                    item["security_implication"] = item["security_implication"] or item["explanation"][:1200]
                item["root_cause_status"] = "hypothesis"
                item["performance_basis"] = "Static/source-level observation; no runtime profiling" if item["category"] == "performance" else None
                run["findings"].append(item)
            run["limitations"].append("Citation validity establishes provenance; human review must assess diagnosis and remediation")
        except ContextOverflow as exc:
            run["outcome"] = "INSUFFICIENT_EVIDENCE"
            run["limitations"].append(str(exc))
        except (ValidationError, InvalidEvidence, json.JSONDecodeError) as exc:
            run["outcome"] = "FAILED"
            if not run["validation_rejections"]:
                run["validation_rejections"] = 1
            run["malformed_output"] = not isinstance(exc, InvalidEvidence)
            run["limitations"].append("Model output rejected by schema/evidence validation; no validated findings")
            run["validation_error"] = str(exc) if isinstance(exc, InvalidEvidence) else "Malformed structured output"
        except (OllamaError, TypeError, AttributeError):
            run["outcome"] = "FAILED"
            run["model_status"] = "failed"
            run["limitations"].append("Local model unavailable or malformed response; analysis failed")
        run["seconds"] = round(perf_counter() - started, 3)
        run["limitations"] = list(dict.fromkeys(run["limitations"]))
        self.indexer.catalog.save_run(scope, run)
        return run
