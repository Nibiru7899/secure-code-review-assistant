from app.llm.schemas import Claim, EvidenceRef, Finding, ModelResponse
from app.validation.evidence_validator import InvalidEvidence


def citation_map(context):
    citations = {}
    for item in context["evidence"]:
        if item["kind"] == "analyzer":
            citations[item["id"]] = (item, EvidenceRef(id=item["id"], start_line=item["start_line"],
                end_line=item["end_line"], quote=item["text"]))
        else:
            for offset, text in enumerate(item["text"].splitlines()):
                if not text.strip():
                    continue
                line = item["start_line"] + offset
                citations[item["id"] + "L" + str(line)] = (item,
                    EvidenceRef(id=item["id"], start_line=line, end_line=line, quote=text))
    return citations


def resolve(parsed, context, review):
    citations = citation_map(context)

    def reference(identifier):
        if identifier not in citations:
            raise InvalidEvidence("Model selected an evidence ID absent from the supplied package")
        return citations[identifier]

    if review:
        findings = []
        for generated in parsed.findings:
            sources = [reference(identifier) for identifier in generated.source_ids]
            if any(item["kind"] != "source" or not item.get("target") for item, _ in sources):
                raise InvalidEvidence("Finding source IDs must select target source evidence")
            locations = {(item["file"], item["function"]) for item, _ in sources}
            if len(locations) != 1:
                raise InvalidEvidence("Finding mixes different source files/functions")
            file, function = locations.pop()
            analyzers = [reference(identifier) for identifier in generated.analyzer_ids]
            if any(item["kind"] != "analyzer" for item, _ in analyzers):
                raise InvalidEvidence("Analyzer IDs must select normalized analyzer evidence")
            refs = [ref for _, ref in sources + analyzers]
            fields = generated.model_dump(exclude={"source_ids", "analyzer_ids"})
            findings.append(Finding(**fields, file=file, function=function or "",
                start_line=min(r.start_line for r in refs), end_line=max(r.end_line for r in refs),
                evidence=refs, status="candidate"))
        return ModelResponse(outcome="CANDIDATES" if findings else "NO_SUPPORTED_FINDING",
                             findings=findings, claims=[], limitations=parsed.limitations)
    claims = [Claim(text=c.text, kind=c.kind, evidence=[reference(i)[1] for i in c.evidence_ids]) for c in parsed.claims]
    return ModelResponse(outcome="ANSWERED" if claims else "INSUFFICIENT_EVIDENCE",
                         findings=[], claims=claims, limitations=parsed.limitations)
