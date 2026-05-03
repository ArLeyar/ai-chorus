"""Diff resolution helpers.

Extracted from review.py to keep that module focused on orchestration.
"""

from __future__ import annotations

import os
import subprocess

from chorus import github as gh

# Hard cap on diff size to protect token budgets across all reviewers.
MAX_DIFF_CHARS = 80_000


def truncate_diff(diff: str, max_chars: int = MAX_DIFF_CHARS) -> str:
    """Truncate a diff to max_chars, appending a marker."""
    if len(diff) < max_chars:
        return diff
    return diff[:max_chars] + f"\n\n[diff truncated at {max_chars} chars]"


def resolve_diff() -> str:
    """Get the diff to review.

    Modes (in priority order):
      1. PR_BASE_SHA + PR_HEAD_SHA env (CI): diff between those SHAs
      2. Local: HEAD~1..HEAD if it exists
      3. Local: full latest commit (single-commit repo)
      4. Local: uncommitted working tree changes
    """
    base = os.environ.get("PR_BASE_SHA")
    head = os.environ.get("PR_HEAD_SHA")
    if base and head:
        return gh.fetch_diff(base, head)

    try:
        return gh.fetch_diff("HEAD~1", "HEAD")
    except Exception:  # noqa: BLE001
        pass

    try:
        out = subprocess.run(
            ["git", "show", "HEAD", "--format="],
            capture_output=True, text=True, check=True,
        )
        return out.stdout
    except Exception:  # noqa: BLE001
        out = subprocess.run(
            ["git", "diff", "HEAD"], capture_output=True, text=True
        )
        return out.stdout
