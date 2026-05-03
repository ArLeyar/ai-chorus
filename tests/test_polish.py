"""Tests for the optional LLM-as-judge polish layer.

The judge itself is best-effort and depends on a live LLM call, so we
test only the deterministic surface around it: gating, formatting input,
and that disabled mode never touches the network.
"""

from chorus.consensus import consolidate
from chorus.models import Finding, ProviderReview
from chorus.polish import _format_for_judge, polish


def _f(file: str, title: str, severity: str = "major") -> Finding:
    return Finding(
        file=file,
        line=1,
        severity=severity,  # type: ignore[arg-type]
        title=title,
        description="...",
        confidence=0.8,
    )


def _r(provider: str, *findings: Finding, status: str = "ok") -> ProviderReview:
    return ProviderReview(
        provider=provider,
        model=f"{provider}:test",
        status=status,  # type: ignore[arg-type]
        findings=list(findings),
        summary="t",
    )


async def test_polish_disabled_returns_none(monkeypatch):
    """CHORUS_POLISH unset → polish() never calls a model."""
    monkeypatch.delenv("CHORUS_POLISH", raising=False)
    reviews = [_r("gemini", _f("a.py", "x"))]
    result = await polish(consolidate(reviews), reviews)
    assert result is None


async def test_polish_no_api_key_returns_none(monkeypatch):
    """Even with CHORUS_POLISH=1, missing GOOGLE_API_KEY → graceful None."""
    monkeypatch.setenv("CHORUS_POLISH", "1")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    reviews = [_r("gemini", _f("a.py", "x"))]
    result = await polish(consolidate(reviews), reviews)
    assert result is None


def test_format_for_judge_groups_classifications():
    reviews = [
        _r("gemini", _f("a.py", "shared")),
        _r("groq", _f("a.py", "shared")),
        _r("openrouter", _f("b.py", "lonely")),
    ]
    text = _format_for_judge(consolidate(reviews), reviews)
    assert "CONSENSUS" in text
    assert "UNIQUE" in text
    assert "a.py" in text
    assert "b.py" in text


def test_format_for_judge_lists_statuses():
    reviews = [
        _r("gemini", status="ok"),
        _r("groq", status="failed"),
    ]
    text = _format_for_judge(consolidate(reviews), reviews)
    assert "gemini=ok" in text
    assert "groq=failed" in text
