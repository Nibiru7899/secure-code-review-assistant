import re


class InvalidEvidence(ValueError):
    pass


def validate(response, context, manifest):
    evidence = {item["id"]: item for item in context["evidence"]}
    target = [item for item in evidence.values() if item.get("target") and item["kind"] == "source"]
    if response.outcome == "CANDIDATES" and not response.findings:
        raise InvalidEvidence("Candidate outcome needs findings")
    if response.outcome != "CANDIDATES" and response.findings:
        raise InvalidEvidence("Outcome conflicts with findings")
    if response.outcome == "ANSWERED" and not response.claims:
        raise InvalidEvidence("Answered outcome needs cited claims")

    def reference(ref):
        item = evidence.get(ref.id)
        if item is None:
            raise InvalidEvidence("Citation id was not supplied")
        snapshot = item.get("review_snapshot") if item["kind"] == "historical" else item["snapshot"]
        if snapshot != manifest["snapshot"] or item["repository"] != manifest["repository"]:
            raise InvalidEvidence("Citation snapshot/repository mismatch")
        if not item["start_line"] <= ref.start_line <= ref.end_line <= item["end_line"]:
            raise InvalidEvidence("Citation line range outside supplied evidence")
        lines = item["text"].splitlines()
        selected = "\n".join(lines[ref.start_line - item["start_line"]:ref.end_line - item["start_line"] + 1])
        if item["kind"] == "analyzer":
            selected = item["text"]
        if ref.quote not in selected:
            raise InvalidEvidence("Citation quote does not match supplied lines")
        if item["kind"] == "source":
            source = manifest["source"].get(item["file"])
            if source is None or ref.quote not in "\n".join(source.splitlines()[ref.start_line - 1:ref.end_line]):
                raise InvalidEvidence("Source quote does not match snapshot")
        return item

    for finding in response.findings:
        if finding.file not in manifest["source"]:
            raise InvalidEvidence("Finding file absent from authorized snapshot")
        if not any(item["file"] == finding.file and item["function"] == finding.function
                   and item["start_line"] <= finding.start_line <= finding.end_line <= item["end_line"] for item in target):
            raise InvalidEvidence("Finding location/function outside retrieved target")
        refs = [reference(ref) for ref in finding.evidence]
        if not any(item["kind"] == "source" and item["file"] == finding.file
                   and item["function"] == finding.function and ref.start_line <= finding.end_line
                   and ref.end_line >= finding.start_line for item, ref in zip(refs, finding.evidence)):
            raise InvalidEvidence("Finding requires source evidence for its function")
        for rule in finding.applicable_rules:
            if rule not in evidence or evidence[rule]["kind"] != "rule":
                raise InvalidEvidence("Applicable rule was not retrieved")
            category = {"pointer": "null-pointer"}.get(evidence[rule]["category"], evidence[rule]["category"])
            if category != finding.category:
                raise InvalidEvidence("Applicable demo rule category does not match finding")
        for item in refs:
            if item["kind"] == "analyzer" and (item["file"] != finding.file
                    or not finding.start_line <= item["start_line"] <= finding.end_line
                    or item["category"] != finding.category):
                raise InvalidEvidence("Analyzer citation does not corroborate category/location")
    for claim in response.claims:
        refs = [reference(ref) for ref in claim.evidence]
        if any(item["kind"] == "historical" for item in refs) and not any(item["kind"] == "source" for item in refs):
            raise InvalidEvidence("Historical precedent cannot replace current source support")
        for rule in re.findall(r'\b[A-Z]+-\d+\b', claim.text):
            if not any(item["kind"] == "rule" and item["id"] == rule for item in refs):
                raise InvalidEvidence("Rule named in claim requires a citation to its retrieved guidance")
        symbols = {c["symbol"] for c in manifest["chunks"] if c["symbol"]}
        for symbol in symbols:
            if re.search(r'\b' + re.escape(symbol) + r'\b', claim.text) and not any(
                    item.get("function") == symbol or re.search(r'\b' + re.escape(symbol) + r'\b', ref.quote)
                    for item, ref in zip(refs, claim.evidence)):
                raise InvalidEvidence("Function named in claim is not supported by its cited source/log")
    # Check explicit file/rule references in prose as well as structured fields.
    # Other semantic assertions remain candidate interpretations for a reviewer.
    prose = "\n".join([f.issue + "\n" + f.explanation + "\n" + f.suggested_fix + "\n" + f.root_cause + "\n" + f.security_implication for f in response.findings]
                      + [c.text for c in response.claims] + response.limitations)
    supplied_files = {item["file"] for item in evidence.values() if item["kind"] == "source"}
    included_names = {name for item in evidence.values() if item["kind"] == "source"
                      for name in re.findall(r'#\s*include\s*"([^"]+)"', item["text"])}
    for path in re.findall(r'(?<![\w/])(?:[\w.-]+/)*[\w.-]+\.(?:cpp|cxx|hpp|cc|h|c)\b', prose):
        captured_include = path in included_names and any(p == path or p.endswith("/" + path) for p in manifest["source"])
        if path not in supplied_files and path not in {p.split("/")[-1] for p in supplied_files} and not captured_include:
            raise InvalidEvidence("Prose names a source file absent from supplied evidence")
    for rule in re.findall(r'\b[A-Z]+-\d+\b', prose):
        if rule not in evidence or evidence[rule]["kind"] != "rule":
            raise InvalidEvidence("Prose names a coding rule absent from supplied evidence")
    for identity, line in re.findall(r'\b(S\d+|R[0-9a-f]+|D[0-9a-f]+|[A-Z]+-\d+)L(\d+)\b', prose):
        item = evidence.get(identity)
        if item is None or not item["start_line"] <= int(line) <= item["end_line"]:
            raise InvalidEvidence("Inline line citation is outside supplied evidence")
    # Citation checks cannot prove semantic truth. Enforce the explicit no-MISRA
    # scope, but never present validated prose as a certified defect diagnosis.
    if re.search(r'(?:C\+\+|C)\s+Standard|\b(?:ISO|IEC)\s*\d', prose, re.I):
        raise InvalidEvidence("External standard citation has no approved retrieved guidance")
    if re.search(r"\bMISRA\b", response.model_dump_json(), re.I):
        raise InvalidEvidence("No MISRA guidance is supplied; model standards claims are rejected")
    if context.get("task") == "diagnostics" and response.claims and not any(
            evidence[ref.id]["kind"] == "diagnostic" for claim in response.claims for ref in claim.evidence):
        raise InvalidEvidence("Diagnostic interpretation requires a citation to the imported log")
    if context.get("task") == "diagnostics" and any(c.kind != "hypothesis" for c in response.claims):
        raise InvalidEvidence("Unverified imported diagnostics require qualified hypothesis claims")
    return response
