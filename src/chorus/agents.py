"""Reviewer agent factory.

One agent per provider, all sharing the same prompt and the same
`ReviewResult` shape. Tools and the structured-output strategy are
per-provider capabilities (see `ProviderConfig.supports_tools`):

- supports_tools=True  → tool-call output, `read_file`/`grep`/`find_callers`
                         registered.
- supports_tools=False → `PromptedOutput(ReviewResult)`, no tools registered.

The vendor-agnostic dream — swap the model string, keep most of the rest.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_ai import Agent, RunContext
from pydantic_ai.output import PromptedOutput

from chorus.models import ReviewResult
from chorus.tools import Deps, find_callers, grep, read_file

if TYPE_CHECKING:
    from chorus.providers import ProviderConfig

PROMPT_PATH = Path(__file__).parent / "prompts" / "reviewer.md"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text()


def make_reviewer(provider: ProviderConfig) -> Agent[Deps, ReviewResult]:
    """Build a Pydantic AI agent configured for the given provider.

    Every agent shares prompt and output_type. Tools are registered only
    when provider.supports_tools is True — some free-tier endpoints return
    404 on tool_choice, and degrading to diff-only review beats failing.

    Vendor-agnosticism is a config change, not an architectural pivot.
    """
    # Pydantic AI defaults to tool-call-based structured output. For
    # providers without tool support, switch to PromptedOutput which asks
    # the model to return JSON in plain text and parses it ourselves.
    output: type[ReviewResult] | PromptedOutput[ReviewResult] = (
        ReviewResult if provider.supports_tools else PromptedOutput(ReviewResult)
    )

    agent: Agent[Deps, ReviewResult] = Agent(
        provider.model,
        deps_type=Deps,
        output_type=output,
        system_prompt=_load_prompt(),
    )

    if provider.supports_tools:

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
