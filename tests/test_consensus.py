"""Unit tests for deterministic consensus.

These run without any LLM — that's the point of structured output.
"""

from chorus.consensus import consolidate
from chorus.models import Finding, ProviderReview


def _f(file: str, title: str, severity="major", line=10, conf=0.8) -> Finding:
    return Finding(
        file=file,
        line=line,
        severity=severity,
        title=title,
        description="...",
        confidence=conf,
    )


def _r(provider: str, *findings: Finding, status="ok") -> ProviderReview:
    return ProviderReview(
        provider=provider,
        model=f"{provider}:test",
        status=status,
        findings=list(findings),
        summary="test",
    )


def test_consensus_two_reviewers_same_issue():
    """Same file, similar titles → grouped as 'consensus'."""
    reviews = [
        _r("gemini", _f("auth.py", "missing null check on user input")),
        _r("groq", _f("auth.py", "user input not null-checked")),
    ]
    result = consolidate(reviews)
    assert len(result.groups) == 1
    g = result.groups[0]
    assert g.classification == "consensus"
    assert sorted(g.providers) == ["gemini", "groq"]


def test_unique_finding_only_one_provider():
    reviews = [
        _r("gemini", _f("auth.py", "missing null check")),
        _r("groq"),  # no findings
    ]
    result = consolidate(reviews)
    assert len(result.groups) == 1
    assert result.groups[0].classification == "unique"
    assert result.groups[0].providers == ["gemini"]


def test_disagreement_severity_spread():
    """Same issue, but one says critical and other says nit → disagreement."""
    reviews = [
        _r("gemini", _f("api.py", "input validation issue", severity="critical")),
        _r("groq", _f("api.py", "validation of input", severity="nit")),
    ]
    result = consolidate(reviews)
    assert len(result.groups) == 1
    assert result.groups[0].classification == "disagreement"


def test_different_files_dont_merge():
    """Same title, different files → two separate groups."""
    reviews = [
        _r("gemini", _f("a.py", "missing null check")),
        _r("groq", _f("b.py", "missing null check")),
    ]
    result = consolidate(reviews)
    assert len(result.groups) == 2
    assert all(g.classification == "unique" for g in result.groups)


def test_skipped_reviews_dont_contribute_findings():
    reviews = [
        _r("gemini", _f("x.py", "real issue")),
        _r("groq", _f("x.py", "ghost finding"), status="skipped"),
    ]
    result = consolidate(reviews)
    assert result.total_reviews_attempted == 2
    assert result.total_reviews_ok == 1
    # Skipped findings ignored — only one finding survives
    assert len(result.groups) == 1
    assert result.groups[0].providers == ["gemini"]


def test_severity_max_wins_in_consensus_group():
    """When grouped, the highest severity is reported."""
    reviews = [
        _r("gemini", _f("x.py", "sql injection risk", severity="major")),
        _r("groq", _f("x.py", "SQL injection", severity="critical")),
    ]
    result = consolidate(reviews)
    assert len(result.groups) == 1
    assert result.groups[0].severity == "critical"


def test_ordering_consensus_before_unique():
    """Consensus groups should come before unique ones in output."""
    reviews = [
        _r("gemini", _f("a.py", "shared bug"), _f("b.py", "only gemini saw")),
        _r("groq", _f("a.py", "shared bug")),
    ]
    result = consolidate(reviews)
    assert result.groups[0].classification == "consensus"
    assert result.groups[-1].classification == "unique"


def test_empty_reviews():
    result = consolidate([])
    assert result.groups == []
    assert result.total_reviews_attempted == 0
    assert result.total_reviews_ok == 0


def test_all_failed_reviews():
    reviews = [
        _r("gemini", status="failed"),
        _r("groq", status="timeout"),
    ]
    result = consolidate(reviews)
    assert result.groups == []
    assert result.total_reviews_ok == 0
