"""Evidence support describes corroboration, never a probability of correctness."""


def evidence_support(finding):
    analyzer = any(ref["id"].startswith("A") for ref in finding["evidence"])
    rule = bool(finding["applicable_rules"])
    return "STRONG" if analyzer and rule else "SUPPORTED" if analyzer or rule else "AI-ONLY CANDIDATE"
