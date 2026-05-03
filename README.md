# ai-chorus

> Vendor-agnostic AI ops platform. **Phase 1: multi-model PR review.**

When one model isn't enough, run several. Every PR in this repo gets reviewed
by three independent LLMs in parallel — Gemini Flash, Llama 3.3 70B (Groq),
Nemotron Nano 30B (OpenRouter) — and the results are merged with deterministic
consensus logic.

Built with [Pydantic AI](https://pydantic.dev/docs/ai/), runs entirely on
GitHub Actions free tier, no paid API keys required.

## Why

A typical "diff-only" code review misses cross-file impact. A single LLM
hallucinates. Three independent LLMs whose findings can be triangulated
produce signal — when 2-of-3 flag the same issue, pay attention. When they
disagree on severity, that's worth a human glance.

Reviewers that support tool calling (`grep`, `read_file`, `find_callers`)
get them registered automatically; those that don't fall back to a
diff-only review via `PromptedOutput`. See "tools as capability" below.

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
   │  • openrouter:nvidia/nemotron-3-     │
   │             nano-30b-a3b:free        │
   │                                      │
   │  output_type = ReviewResult (Pydantic)
   │  tools (when supports_tools=True):   │
   │    read_file / grep / find_callers   │
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

## Use in your repo

ai-chorus ships as a [composite GitHub Action](https://docs.github.com/en/actions/sharing-automations/creating-actions/creating-a-composite-action),
so consuming repos add a single workflow file — no Python code copied across
projects.

### 1. Get free API keys (no credit card required)

- Google AI Studio — <https://aistudio.google.com/> → Get API key
- Groq — <https://console.groq.com/keys>
- OpenRouter — <https://openrouter.ai/settings/keys>

All three are optional — missing keys gracefully degrade to "skipped" in
the comment.

### 2. Add them as repo secrets

```bash
gh secret set GOOGLE_API_KEY      # → Gemini
gh secret set GROQ_API_KEY        # → Llama
gh secret set OPENROUTER_API_KEY  # → Nemotron Nano
```

### 3. Drop in this workflow

```yaml
# .github/workflows/ai-chorus.yml
name: AI Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: ai-chorus-${{ github.ref }}
  cancel-in-progress: true

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: ArLeyar/ai-chorus@v1
        with:
          providers: gemini,groq,openrouter   # subset is fine
          polish: '1'                          # 0 to disable verdict line
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}
          PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
```

That's it. Open a PR and watch the multi-model review comment appear.

### Action inputs

| Input | Default | Description |
|---|---|---|
| `providers` | `gemini,groq,openrouter` | Comma-separated subset to enable |
| `polish` | `1` | LLM-as-judge verdict line (`0` to disable) |

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
- **Tools as capability, not assumption**: each `ProviderConfig` declares
  `supports_tools`. When False, the agent uses `PromptedOutput` (JSON in
  text) instead of the default tool-call-based structured output. Free
  OpenRouter routes routinely return 404 on `tool_choice` — diff-only
  review beats a failing reviewer.

## Cost

At free-tier limits — **$0 marginal**. If migrated to paid frontier models
(e.g. Claude Sonnet 4.6 + GPT-5 + Gemini 2.5 Pro) for higher quality and
fewer rate-limit interruptions, expect roughly $0.30-0.80 per PR for three
parallel reviews on a typical mid-sized diff. Vendor-agnostic providers
make the swap a one-line config change in `src/chorus/providers.py`.

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

## Local development

A `Makefile` mirrors the CI gates so you can run the full check before
pushing:

```bash
make install   # uv sync (runtime + dev)
make hooks     # install pre-commit (one-time)

make fmt       # ruff format
make lint      # ruff check (lint rules)
make type      # mypy --strict
make test      # pytest --cov
make check     # all of: fmt --check, lint, type, test
```

Pre-commit (configured in `.pre-commit-config.yaml`) runs `ruff check
--fix` and `ruff format` on every commit so style stays clean without
manual remembering.

Consensus and rendering have full unit coverage without LLM mocks — that's
the point of structured output.

## License

MIT
