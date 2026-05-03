"""Unit tests for markdown rendering."""

from chorus.consensus import consolidate
from chorus.markdown import render
from chorus.models import Finding, ProviderReview


def _f(file: str, title: str, severity="major") -> Finding:
    return Finding(
        file=file,
        line=10,
        severity=severity,
        title=title,
        description="why it matters",
        confidence=0.8,
    )


def test_render_includes_status_for_each_reviewer():
    reviews = [
        ProviderReview(
            provider="gemini",
            model="google-gla:gemini-2.5-flash",
            status="ok",
            findings=[_f("a.py", "issue")],
        ),
        ProviderReview(
            provider="groq",
            model="groq:llama-3.3-70b-versatile",
            status="skipped",
            error="missing GROQ_API_KEY",
        ),
    ]
    output = render(consolidate(reviews), reviews)
    assert "✅" in output
    assert "⚠️" in output
    assert "missing GROQ_API_KEY" in output


def test_render_all_failed_does_not_crash():
    """Even if every reviewer failed, render produces non-empty output."""
    reviews = [
        ProviderReview(provider="gemini", model="x", status="failed", error="boom"),
        ProviderReview(provider="groq", model="y", status="timeout"),
    ]
    output = render(consolidate(reviews), reviews)
    assert "ai-chorus" in output
    assert "boom" in output


def test_render_consensus_findings_section():
    reviews = [
        ProviderReview(
            provider="gemini", model="x", status="ok",
            findings=[_f("a.py", "bug found", severity="critical")],
        ),
        ProviderReview(
            provider="groq", model="y", status="ok",
            findings=[_f("a.py", "found bug", severity="critical")],
        ),
    ]
    output = render(consolidate(reviews), reviews)
    assert "Consensus findings" in output
    assert "🔴" in output  # critical emoji


def test_render_no_findings():
    """Clean PR — reviewers ran but found nothing."""
    reviews = [
        ProviderReview(provider="gemini", model="x", status="ok",
                       findings=[], summary="LGTM"),
    ]
    output = render(consolidate(reviews), reviews)
    assert "0 findings" in output
