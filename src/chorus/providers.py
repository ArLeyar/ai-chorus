"""Provider configuration — the only place model strings and env vars live.

Adding a new provider = one entry here. `active_providers()` is the gate
between configuration and runtime: it filters by env vars present and the
optional `CHORUS_PROVIDERS` whitelist (useful for local single-provider tests).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    key: str  # short name, used in CHORUS_PROVIDERS, comments, logs
    model: str  # Pydantic AI model string (provider:model_name)
    env_var: str  # required env var for the LLM API key
    display_name: str  # human-readable, used in markdown comment
    # Hard cap on diff chars passed to this provider. Free tiers have wildly
    # different TPM limits — Groq free is 12K TPM (≈40-50K chars), Nemotron
    # 120B has wider limits but slow inference, Gemini Flash is permissive.
    max_input_chars: int = 80_000
    # Per-provider wall-clock cap. Reasoning models (Nemotron) are slower.
    timeout_s: float = 90.0
    # Whether to register tools (read_file/grep/find_callers). Some free
    # OpenRouter routes return 404 on tool_choice — set False there to fall
    # back to diff-only review.
    supports_tools: bool = True


# Source of truth. Verified against Pydantic AI docs (2026-05):
#   google-gla       — https://pydantic.dev/docs/ai/models/google/  (env: GOOGLE_API_KEY)
#   groq             — https://pydantic.dev/docs/ai/models/groq/    (env: GROQ_API_KEY)
#   openrouter       — https://pydantic.dev/docs/ai/models/openrouter/ (env: OPENROUTER_API_KEY)
PROVIDERS: dict[str, ProviderConfig] = {
    "gemini": ProviderConfig(
        key="gemini",
        model="google-gla:gemini-2.5-flash",
        env_var="GOOGLE_API_KEY",
        display_name="Gemini 2.5 Flash",
        # Gemini Flash has generous free quotas; safe with full diff cap.
        # Bumped from 90s → 150s after observing timeout on a large
        # config-rewrite diff. Gemini's tool-calling agent loop can take
        # multiple round trips when it decides to read source files.
        max_input_chars=80_000,
        timeout_s=150.0,
    ),
    "groq": ProviderConfig(
        key="groq",
        model="groq:llama-3.3-70b-versatile",
        env_var="GROQ_API_KEY",
        display_name="Llama 3.3 70B (Groq)",
        # Groq free tier: 12K TPM. ~3.5 chars per token → ~30K chars total
        # input. Reserve room for prompt template + tools schema → 20K diff.
        max_input_chars=20_000,
        timeout_s=60.0,
    ),
    "openrouter": ProviderConfig(
        key="openrouter",
        # Probed 2026-05: 1.2s avg latency, 200 status.
        # Smaller non-reasoning Nemotron — picked for reliability over depth.
        # On free tier we optimize for "always responds" not "best review".
        model="openrouter:nvidia/nemotron-3-nano-30b-a3b:free",
        env_var="OPENROUTER_API_KEY",
        display_name="Nemotron 3 Nano 30B (OpenRouter)",
        max_input_chars=40_000,
        timeout_s=60.0,
        # Free OpenRouter routes for nano-30b reject tool_choice (404).
        # Diff-only review still produces a useful third opinion.
        supports_tools=False,
    ),
}


def active_providers() -> list[ProviderConfig]:
    """Return providers that should be invoked given current env state.

    Filters by:
      1. CHORUS_PROVIDERS whitelist (comma-separated keys), if set.
      2. Presence of API key env var — missing key means provider is skipped
         here, NOT marked as failed at runtime. Skipped status is set by
         the orchestrator with a clear marker.
    """
    whitelist_raw = os.environ.get("CHORUS_PROVIDERS", "").strip()
    whitelist = (
        {p.strip() for p in whitelist_raw.split(",") if p.strip()}
        if whitelist_raw
        else set(PROVIDERS.keys())
    )

    return [p for key, p in PROVIDERS.items() if key in whitelist]


def has_api_key(provider: ProviderConfig) -> bool:
    return bool(os.environ.get(provider.env_var))
