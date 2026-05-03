"""Optional LLM-as-judge that adds a one-line verdict on top of the comment.

Strictly post-processing — the judge consumes the already-built Consensus
and ProviderReview list, never mutates them. Toggled by env CHORUS_POLISH=1.

Why opt-in: the judge is a small but real source of non-determinism. The
deterministic pipeline (consolidate → render) must remain the source of
truth. The judge only adds prose at the top — useful for human skimmers
on busy PRs, optional for everyone else.

If the judge fails (timeout, missing key, malformed output), polish() returns
None and rendering proceeds as if it was disabled. Never crashes the run.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.output import PromptedOutput

from chorus.providers import PROVIDERS, has_api_key

if TYPE_CHECKING:
    from chorus.models import Consensus, FindingGroup, ProviderReview

# Try providers in order. First one with a key that responds wins.
# Reviewers and the judge can compete for the same daily quota (Gemini free
# tier is 20 RPD on 2.5 Flash), so falling back keeps polish working when
# one provider is exhausted.
JUDGE_FALLBACK_ORDER = ("gemini", "groq", "openrouter")

JUDGE_TIMEOUT_S = 30.0

JUDGE_PROMPT = """\
You are summarizing a multi-model code review for a senior engineer.

You will receive a structured summary of:
- How many reviewers ran and their statuses (ok/skipped/failed/timeout)
- Findings grouped into: consensus (>=2 reviewers agree), disagreement
  (same issue, different severity), and unique (only one reviewer raised)
- Per-reviewer summaries

Write ONE sentence (max 30 words) capturing the overall verdict for the PR.

Rules:
- Do NOT invent issues. Do NOT contradict the structured findings.
- Be specific: if there are findings, name the file or concern; say "clean"
  if no findings exist.
- Acknowledge degraded reviewers if any failed/skipped/timed-out.
- No filler. No "this PR introduces...". Just the verdict.
"""


class Verdict(BaseModel):
    """Output type the judge model is constrained to."""

    headline: str = Field(description="One-sentence verdict, max 30 words.")


def _format_for_judge(consensus: Consensus, reviews: list[ProviderReview]) -> str:
    """Compact text representation of the review state."""
    lines: list[str] = []

    statuses = ", ".join(f"{r.provider}={r.status}" for r in reviews)
    lines.append(f"Reviewers: {statuses}")
    lines.append(f"({consensus.total_reviews_ok}/{consensus.total_reviews_attempted} ok)")
    lines.append("")

    by_class: dict[str, list[FindingGroup]] = {
        "consensus": [],
        "disagreement": [],
        "unique": [],
    }
    for g in consensus.groups:
        by_class[g.classification].append(g)

    for label, groups in by_class.items():
        if not groups:
            continue
        lines.append(f"{label.upper()} ({len(groups)}):")
        for g in groups:
            lines.append(f"  - [{g.severity}] {g.file}: {g.title} (by: {', '.join(g.providers)})")
        lines.append("")

    for r in reviews:
        if r.status == "ok" and r.summary:
            lines.append(f"{r.provider} summary: {r.summary[:200]}")

    return "\n".join(lines)


async def polish(
    consensus: Consensus,
    reviews: list[ProviderReview],
) -> str | None:
    """Return a one-sentence verdict, or None if disabled/unavailable/failed.

    Disabled by default. Set CHORUS_POLISH=1 to enable. Errors are swallowed —
    the comment posting flow must never depend on this.

    Tries JUDGE_FALLBACK_ORDER in sequence; the first provider whose key is
    set and which responds wins. This handles the common case where one
    provider's free quota is exhausted (e.g. Gemini 20 RPD).
    """
    if not os.environ.get("CHORUS_POLISH"):
        return None

    summary = _format_for_judge(consensus, reviews)

    for key in JUDGE_FALLBACK_ORDER:
        cfg = PROVIDERS.get(key)
        if cfg is None or not has_api_key(cfg):
            continue

        # OpenRouter free routes often reject tool_choice; use PromptedOutput
        # for non-tool providers, mirroring the reviewer agent strategy.
        output: type[Verdict] | PromptedOutput[Verdict] = (
            Verdict if cfg.supports_tools else PromptedOutput(Verdict)
        )
        agent: Agent[None, Verdict] = Agent(
            cfg.model,
            output_type=output,
            system_prompt=JUDGE_PROMPT,
        )

        try:
            result = await asyncio.wait_for(agent.run(summary), timeout=JUDGE_TIMEOUT_S)
        except Exception:
            # Try next provider — typical reasons: 429 quota, 5xx, timeout.
            continue

        headline = result.output.headline.strip()
        if headline:
            return headline

    return None
