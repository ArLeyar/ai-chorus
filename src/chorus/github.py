"""GitHub I/O — isolated wrapper around the `gh` CLI.

Keeping the dependency on `gh` confined to one module makes it trivial to
swap for a REST API client later (httpx + GitHub token). For Phase 1, `gh`
is preinstalled on GitHub Actions runners and locally Ar already has it,
so it's strictly cheaper.
"""

from __future__ import annotations

import os
import subprocess


def fetch_diff(base_sha: str, head_sha: str, *, repo_dir: str | None = None) -> str:
    """Return the unified diff between two SHAs via local git."""
    result = subprocess.run(
        ["git", "diff", base_sha, head_sha],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def post_pr_comment(pr_number: int | str, body: str) -> None:
    """Post a comment on the given PR. Requires `gh` auth (or GITHUB_TOKEN env)."""
    env = os.environ.copy()
    # Prefer GITHUB_TOKEN if set (CI), otherwise fall back to gh's own auth.
    if "GITHUB_TOKEN" in env and "GH_TOKEN" not in env:
        env["GH_TOKEN"] = env["GITHUB_TOKEN"]

    subprocess.run(
        ["gh", "pr", "comment", str(pr_number), "--body", body],
        check=True,
        env=env,
    )
