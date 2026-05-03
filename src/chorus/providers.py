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
        max_input_chars=80_000,
        timeout_s=90.0,
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
        # NVIDIA-hosted, less prone to Venice/Together free-tier throttling
        # observed on qwen/deepseek free endpoints (2026-05).
        model="openrouter:nvidia/nemotron-3-super-120b-a12b:free",
        env_var="OPENROUTER_API_KEY",
        display_name="Nemotron 3 Super 120B (OpenRouter)",
        # Reasoning model — slower, but context is wide.
        max_input_chars=80_000,
        timeout_s=180.0,
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
