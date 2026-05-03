"""Reviewer agent factory.

One agent per provider, all sharing the same prompt, tools, and output_type.
The vendor-agnostic dream — swap the model string, keep everything else.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent, RunContext

from chorus.models import ReviewResult
from chorus.providers import ProviderConfig
from chorus.tools import Deps, find_callers, grep, read_file

PROMPT_PATH = Path(__file__).parent / "prompts" / "reviewer.md"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text()


def make_reviewer(provider: ProviderConfig) -> Agent[Deps, ReviewResult]:
    """Build a Pydantic AI agent configured for the given provider.

    Every agent has the same shape:
      - same system prompt
      - same three tools (read_file / grep / find_callers)
      - same output_type=ReviewResult

    The only thing that differs is the model string. Vendor-agnosticism is
    a five-character config change, not an architectural pivot.
    """
    agent: Agent[Deps, ReviewResult] = Agent(
        provider.model,
        deps_type=Deps,
        output_type=ReviewResult,
        system_prompt=_load_prompt(),
    )

    @agent.tool
    def read_file_tool(ctx: RunContext[Deps], path: str) -> str:
        """Read a file from the repository. Path is relative to repo root."""
        return read_file(ctx.deps, path)

    @agent.tool
    def grep_tool(ctx: RunContext[Deps], pattern: str, path_glob: str = "") -> str:
        """Search the repo with ripgrep. Returns file:line:match lines."""
        return grep(ctx.deps, pattern, path_glob)

    @agent.tool
    def find_callers_tool(ctx: RunContext[Deps], symbol: str) -> str:
        """Find places that call a function/method by name."""
        return find_callers(ctx.deps, symbol)

    return agent
