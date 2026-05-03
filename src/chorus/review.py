"""Orchestrator: diff → parallel reviewers → consensus → markdown → post.

Graceful degradation is woven through here: missing API keys, exceptions,
and timeouts all turn into ProviderReview objects with non-ok status.
The Action never silently crashes — it always posts something.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from chorus import consensus as consensus_mod
from chorus import github as gh
from chorus import markdown as md
from chorus.agents import make_reviewer
from chorus.models import ProviderReview
from chorus.providers import ProviderConfig, active_providers, has_api_key
from chorus.tools import Deps

# Per-provider wall-clock cap. Free models are slow; this catches the
# pathological "stuck connection" case without killing healthy long runs.
PROVIDER_TIMEOUT_S = 90.0

# Keep the diff bounded — large PRs explode token budgets fast.
MAX_DIFF_CHARS = 80_000


async def _run_one(provider: ProviderConfig, diff: str, deps: Deps) -> ProviderReview:
    """Run a single reviewer; convert any failure into a ProviderReview."""
    if not has_api_key(provider):
        return ProviderReview(
            provider=provider.key,
            model=provider.model,
            status="skipped",
            error=f"missing {provider.env_var}",
        )

    started = time.monotonic()
    try:
        agent = make_reviewer(provider)
        prompt = (
            "Review this pull request diff.\n\n"
            "```diff\n"
            f"{diff}\n"
            "```\n"
        )
        result = await asyncio.wait_for(
            agent.run(prompt, deps=deps),
            timeout=PROVIDER_TIMEOUT_S,
        )
        review = result.output
        return ProviderReview(
            provider=provider.key,
            model=provider.model,
            status="ok",
            findings=review.findings,
            summary=review.summary,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except TimeoutError:
        return ProviderReview(
            provider=provider.key,
            model=provider.model,
            status="timeout",
            error=f"exceeded {PROVIDER_TIMEOUT_S:.0f}s",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    except Exception as e:  # noqa: BLE001 — we want to capture anything for the comment
        return ProviderReview(
            provider=provider.key,
            model=provider.model,
            status="failed",
            error=f"{type(e).__name__}: {e}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )


async def run_reviews(diff: str, repo_dir: Path) -> list[ProviderReview]:
    providers = active_providers()
    deps = Deps(repo_dir=repo_dir)
    return await asyncio.gather(*[_run_one(p, diff, deps) for p in providers])


def _resolve_diff() -> str:
    """Get the diff to review.

    Two modes:
      - PR_BASE_SHA + PR_HEAD_SHA env (CI): diff between those SHAs
      - dry-run local: HEAD~1..HEAD as a sensible default
    """
    base = os.environ.get("PR_BASE_SHA")
    head = os.environ.get("PR_HEAD_SHA")
    if not base or not head:
        # Local default — last commit
        base, head = "HEAD~1", "HEAD"
    return gh.fetch_diff(base, head)


async def _amain(args: argparse.Namespace) -> int:
    diff = _resolve_diff()
    if not diff.strip():
        print("Empty diff — nothing to review.", file=sys.stderr)
        return 0

    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + f"\n\n[diff truncated at {MAX_DIFF_CHARS} chars]"

    repo_dir = Path.cwd()
    reviews = await run_reviews(diff, repo_dir)
    consensus = consensus_mod.consolidate(reviews)
    body = md.render(consensus, reviews)

    if args.dry_run:
        print(body)
        return 0

    pr_number = os.environ.get("PR_NUMBER")
    if not pr_number:
        print("ERROR: PR_NUMBER not set and --dry-run not given", file=sys.stderr)
        return 2

    gh.post_pr_comment(pr_number, body)
    print(f"Posted review to PR #{pr_number}", file=sys.stderr)
    return 0


def cli() -> None:
    parser = argparse.ArgumentParser(prog="chorus-review")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print review markdown to stdout instead of posting to GitHub",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    cli()
