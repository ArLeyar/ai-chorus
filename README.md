# ai-chorus

> Vendor-agnostic AI ops platform. **Phase 1: multi-model PR review.**

When one model isn't enough, run several. Every PR in this repo gets reviewed
by three independent LLMs in parallel — Gemini, Llama (Groq), DeepSeek R1
(OpenRouter) — and the results are merged with deterministic consensus logic.

Built with [Pydantic AI](https://pydantic.dev/docs/ai/), runs entirely on
GitHub Actions free tier, no paid API keys required.

## Why

A typical "diff-only" code review misses cross-file impact. A single LLM
hallucinates. Three independent LLMs with tool access (`grep`, `read_file`,
`find_callers`) produce findings you can triangulate — when 2-of-3 flag the
same issue, that's signal. When they disagree on severity, that's worth a
human glance.

## How it works

```
PR opened/synchronized
      │
      ▼
GitHub Actions runner
      │
      ├── checkout (repo on disk)
      ├── uv sync
      └── python -m chorus.review
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Pydantic AI agents (asyncio.gather)  │
   │                                      │
   │  • google-gla:gemini-2.5-flash       │
   │  • groq:llama-3.3-70b-versatile      │
   │  • openrouter:deepseek/...:free      │
   │                                      │
   │  output_type = ReviewResult (Pydantic)
   │  tools = read_file / grep / find_callers
   └──────────────────────────────────────┘
            │
            ▼
   Deterministic consensus (Python, not LLM)
   ── group findings by file + fuzzy title
   ── classify: consensus / unique / disagreement
            │
            ▼
   Markdown render → gh pr comment
```

The split between `ReviewResult` (LLM output_type) and `ProviderReview`
(orchestrator wrapper with status: ok/skipped/failed/timeout) makes graceful
degradation part of the data model. If a reviewer fails, the comment posts
anyway with a clear ⚠️ marker.

## Setup (in your repo)

1. Get free API keys (none require credit card):
   - Google AI Studio: <https://aistudio.google.com/> → Get API key
   - Groq: <https://console.groq.com/keys>
   - OpenRouter: <https://openrouter.ai/settings/keys>

2. Add as repo secrets:

   ```bash
   gh secret set GOOGLE_API_KEY      # for Gemini
   gh secret set GROQ_API_KEY        # for Llama
   gh secret set OPENROUTER_API_KEY  # for DeepSeek R1
   ```

   All three are optional — missing keys gracefully degrade to "skipped".

3. Copy `.github/workflows/review.yml` and `src/chorus/` into your repo.

## Running locally

```bash
# Single provider for fast iteration
GOOGLE_API_KEY=... CHORUS_PROVIDERS=gemini uv run python -m chorus.review --dry-run

# All providers
GOOGLE_API_KEY=... GROQ_API_KEY=... OPENROUTER_API_KEY=... \
  uv run python -m chorus.review --dry-run
```

`--dry-run` prints the markdown comment to stdout instead of posting.

## Architecture decisions

- **Vendor-agnostic via Pydantic AI**: model strings live in `providers.py`,
  swap a provider with one config entry.
- **Structured output, not markdown merge**: agents return validated Pydantic
  models; consensus is deterministic Python; rendering is pure.
- **Graceful degradation**: every provider failure is captured as
  `ProviderReview(status=...)` with error context, so the Action never
  appears broken.
- **Tools are optional, not required**: free models vary in tool-calling
  reliability. Diff alone yields a baseline review; tools augment it.

## Cost

At free-tier limits — **$0 marginal**. If migrated to paid Sonnet+GPT-4o for
faster, more reliable inference, expect ~$0.20-0.40 per PR for three reviews.

Free-tier rate limits (links to authoritative sources, since they change):
- [Gemini](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Groq](https://console.groq.com/docs/rate-limits)
- [OpenRouter](https://openrouter.ai/docs/api-reference/limits)

## Roadmap

- **Phase 2 — Slack assistant.** FastAPI + Slack Bolt async; same agents +
  tools answer "how does X work?" in channels.
- **Phase 3 — Linear agent.** Linear Agent API (OAuth `actor=app`,
  AgentSessionEvent webhook). Issue assignment → planning → optional coding.
- **Phase 4 — Unified gateway.** Single FastAPI service consolidating all
  edges (GitHub/Slack/Linear) with shared agent core, Postgres for memory.

## Tests

```bash
uv run pytest -q
```

Consensus and rendering have full unit coverage without LLM mocks — that's
the point of structured output.

## License

MIT
