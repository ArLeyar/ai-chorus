"""Agent exploration tools — what reviewers call to dig beyond the diff.

Three tools intentionally; small surface area. The agent decides when to
use them. We keep results bounded (max bytes/lines) — free-tier models
have small context windows and `lost-in-the-middle` matters.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# Per-tool output caps. Tuned for free-tier context windows.
MAX_FILE_BYTES = 30_000
MAX_GREP_BYTES = 8_000
MAX_GREP_MATCHES = 100


@dataclass
class Deps:
    """Dependencies passed to every reviewer agent via Pydantic AI's deps system."""

    repo_dir: Path


def read_file(deps: Deps, path: str) -> str:
    """Read a repo file. Path is relative to repo root.

    Returns either file contents (truncated) or an error marker. We never
    raise — agents should be able to recover from a bad path themselves.
    """
    p = (deps.repo_dir / path).resolve()
    repo_root = deps.repo_dir.resolve()

    # Path traversal guard — agents must not escape the worktree.
    try:
        p.relative_to(repo_root)
    except ValueError:
        return f"ERROR: path '{path}' outside repo root"

    if not p.exists() or not p.is_file():
        return f"NOT FOUND: {path}"

    try:
        text = p.read_text(errors="replace")
    except OSError as e:
        return f"ERROR reading {path}: {e}"

    if len(text) > MAX_FILE_BYTES:
        return text[:MAX_FILE_BYTES] + f"\n\n[truncated at {MAX_FILE_BYTES} bytes]"
    return text


def grep(deps: Deps, pattern: str, path_glob: str = "") -> str:
    """ripgrep across the repo. Returns up to MAX_GREP_MATCHES as file:line:text.

    Use cases for the agent:
      - Find all callers of a function
      - Locate similar patterns elsewhere
      - Verify a hypothesis ("is this constant defined anywhere else?")
    """
    cmd = ["rg", "-n", f"--max-count={MAX_GREP_MATCHES}", "--no-heading", pattern]
    if path_glob:
        cmd += ["--glob", path_glob]
    cmd.append(".")

    try:
        result = subprocess.run(
            cmd, cwd=deps.repo_dir, capture_output=True, text=True, timeout=15
        )
    except subprocess.TimeoutExpired:
        return "ERROR: grep timed out"
    except FileNotFoundError:
        return "ERROR: ripgrep (rg) not installed"

    if result.returncode > 1:  # rg returns 1 for "no matches" — that's fine
        return f"ERROR: {result.stderr.strip() or 'rg failed'}"

    output = result.stdout or "(no matches)"
    if len(output) > MAX_GREP_BYTES:
        return output[:MAX_GREP_BYTES] + f"\n\n[truncated at {MAX_GREP_BYTES} bytes]"
    return output


def find_callers(deps: Deps, symbol: str) -> str:
    """Find places that call a function/method by name.

    Heuristic: word-boundary + symbol + opening paren. Not perfect (no LSP
    here) but catches the 80% case for Python/JS/Go/Rust without parsing.
    """
    return grep(deps, rf"\b{symbol}\s*\(")
