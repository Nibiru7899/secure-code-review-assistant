from typing import Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=1800)


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=1600)
    kind: Literal["observation", "hypothesis"]
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=6)


class Finding(StrictModel):
    category: Literal["null-pointer", "boundary", "resource", "state", "initialization", "unchecked-return", "security", "performance", "control-flow"]
    severity: Literal["critical", "high", "medium", "low", "information"]
    file: str = Field(min_length=1, max_length=400)
    function: str = Field(max_length=400)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    issue: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=1800)
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=6)
    applicable_rules: list[str] = Field(max_length=6)
    suggested_fix: str = Field(min_length=1, max_length=1200)
    root_cause: str = Field(default="", max_length=1200)
    security_implication: str = Field(default="", max_length=1200)
    status: Literal["candidate"]


class ModelResponse(StrictModel):
    outcome: Literal["CANDIDATES", "NO_SUPPORTED_FINDING", "INSUFFICIENT_EVIDENCE", "ANSWERED"]
    findings: list[Finding] = Field(max_length=6)
    claims: list[Claim] = Field(max_length=8)
    limitations: list[str] = Field(max_length=8)


class ReviewResponse(StrictModel):
    findings: list["GeneratedFinding"] = Field(max_length=6)
    limitations: list[str] = Field(max_length=8)


class ExplanationResponse(StrictModel):
    claims: list["GeneratedClaim"] = Field(max_length=8)
    limitations: list[str] = Field(max_length=8)


class GeneratedFinding(StrictModel):
    category: Literal["null-pointer", "boundary", "resource", "state", "initialization", "unchecked-return", "security", "performance", "control-flow"]
    severity: Literal["critical", "high", "medium", "low", "information"]
    issue: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=1800)
    source_ids: list[str] = Field(min_length=1, max_length=3)
    analyzer_ids: list[str] = Field(max_length=3)
    applicable_rules: list[str] = Field(max_length=6)
    suggested_fix: str = Field(min_length=1, max_length=1200)


class GeneratedClaim(StrictModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=6)
    text: str = Field(min_length=1, max_length=1600)
    kind: Literal["observation", "hypothesis"]


class TargetRequest(StrictModel):
    repository: str = Field(min_length=1, max_length=100)
    snapshot: str = Field(min_length=1, max_length=64)
    file: str | None = Field(default=None, max_length=400)
    function: str | None = Field(default=None, max_length=400)
    signature: str | None = Field(default=None, max_length=600)
    question: str = Field(default="", max_length=1200)


class DiagnosticRequest(TargetRequest):
    text: str = Field(min_length=1, max_length=6000)
    origin: str = Field(min_length=1, max_length=200)
    tool: str = Field(default="unknown", max_length=100)
    tool_version: str | None = Field(default=None, max_length=100)
    observed_at: datetime | None = None
    diagnostic_snapshot: str | None = Field(default=None, max_length=64)


class ReviewDecision(StrictModel):
    repository: str = Field(min_length=1, max_length=100)
    action: Literal["ACCEPTED", "EDITED", "REJECTED"]
    expected_revision: int = Field(ge=0)
    note: str = Field(default="", max_length=1800)
    edited_finding: Finding | None = None
