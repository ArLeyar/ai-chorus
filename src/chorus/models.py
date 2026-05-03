"""Pydantic data models — the structured backbone of chorus.

The split between `ReviewResult` (LLM output_type) and `ProviderReview` (wrapper)
is intentional: LLM only produces findings; status/error/duration belong to the
orchestrator layer. Consensus and rendering operate on `ProviderReview` so that
graceful degradation is part of the data model, not a special case in code.
"""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "major", "minor", "nit"]
ProviderStatus = Literal["ok", "skipped", "failed", "timeout"]


class Finding(BaseModel):
    """A single issue identified by a reviewer agent."""

    file: str = Field(description="Path relative to repo root")
    line: int | None = Field(default=None, description="Line number in the new file, if applicable")
    severity: Severity
    title: str = Field(description="Short title — used for fuzzy grouping across reviewers")
    description: str = Field(description="Full explanation, why it matters")
    confidence: float = Field(ge=0.0, le=1.0, description="0..1 — reviewer's own confidence")


class ReviewResult(BaseModel):
    """What an LLM reviewer returns — passed as `output_type` to Pydantic AI Agent."""

    summary: str = Field(description="One-paragraph overall verdict")
    findings: list[Finding] = Field(default_factory=list)


class ProviderReview(BaseModel):
    """Orchestrator-level wrapper around a reviewer execution."""

    provider: str  # "gemini" | "groq" | "openrouter"
    model: str  # full model string, e.g. "google-gla:gemini-2.5-flash"
    status: ProviderStatus
    findings: list[Finding] = Field(default_factory=list)
    summary: str | None = None
    error: str | None = None
    duration_ms: int | None = None


class FindingGroup(BaseModel):
    """A cluster of similar findings across reviewers."""

    file: str
    title: str  # representative title (from highest-confidence finding)
    severity: Severity  # consensus severity (highest among members)
    classification: Literal["consensus", "unique", "disagreement"]
    findings: list[Finding]  # all matched findings
    providers: list[str]  # which reviewers raised this


class Consensus(BaseModel):
    """The deterministic synthesis output."""

    groups: list[FindingGroup]
    total_reviews_attempted: int
    total_reviews_ok: int
