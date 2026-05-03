# Roadmap

Status as of 2026-05-03 after Phase 1 ship + multi-reviewer integration.
Living document — update as priorities shift.

## Where we are

**Phase 1 — multi-model PR review — done and tagged v1.0.0.**

What's live in `main`:

- Composite GitHub Action (`uses: ArLeyar/ai-chorus@v1`) — three parallel
  free-tier reviewers (Gemini Flash, Llama 70B Groq, Nemotron Nano 30B)
- Pydantic AI agent factory with per-provider capability flags
- Deterministic consensus (rapidfuzz grouping, classification)
- Optional LLM-as-judge polish layer with provider fallback chain
- Structured output (`ReviewResult` / `ProviderReview` / `Consensus`)
- Graceful degradation across the board
- CI: ruff strict + mypy --strict + pytest --cov, branch protection
- Pre-commit, Makefile, agent guidelines (CLAUDE.md / AGENTS.md)
- Codex GitHub App with auto code review enabled (parallel reviewer)
- README with quick-start, action inputs, architecture decisions

Known caveat: Claude GitHub App skips PRs that modify CLAUDE.md, AGENTS.md
or `.github/workflows/` files (security guard against guidance/workflow
poisoning). On normal feature PRs it should respond.

---

## Phase 2 — Slack assistant

**Goal:** developers ask "@bot how does X work?" in Slack channels and get
a code-aware answer using the same agent core that ai-chorus uses for
review.

**Stack**

- FastAPI app, deployed on existing `fathom` VPS via Docker
- Slack Bolt async (`AsyncApp`)
- `SlackRequestHandler` mounted on FastAPI route `/slack/events`
- Reuses `chorus.agents.make_reviewer` factory but with a different prompt
  (`prompts/slack_assistant.md`) and tool set:
  - `read_file`, `grep`, `find_callers` (existing)
  - `code_search` (semantic, optional, pgvector-backed)
- Memory layer: Postgres for conversation history per Slack thread

**Open design questions**

- Bot identity: Slack "App" vs Workflow Builder? Bolt is the standard
- Authoritative repo: how does the bot know which repo to search? Per-channel
  config? Slack workspace-level mapping?
- Cold start: first response latency budget — Slack's 3 s ack window
- Permissions model: which channels can invoke the bot

**Dependencies / unknowns**

- Need Slack workspace + bot token
- Need pgvector on Postgres (Supabase free tier is fine)
- Code-search index ingestion job (separate cron / git hook)

**Estimate:** 8-13 SP for working MVP on one repo / one channel.

---

## Phase 3 — Linear agent

**Goal:** assign a Linear issue to the agent, the agent acknowledges and
posts a draft plan within 10 s, then optionally takes the implementation.

**Stack**

- Linear Agent API (released 2026)
- OAuth `actor=app` flow (not API key — agents are first-class members)
- AgentSessionEvent webhook → `/linear/webhooks` on the same FastAPI app
- Two-stage agent: planning → human approve → coding
- Coding stage runs in isolated Docker container (sandbox), uses werma-style
  worktrees over a bare clone

**Open design questions**

- Approval gate UX — Linear comment "approve" detection, or label-based?
- How to bound coding agent's bash exec — allowlist + filesystem restrictions
- Failure recovery — how does the agent communicate "stuck" back to Linear

**Dependencies / unknowns**

- Linear workspace + OAuth app registration
- Bare-repo + worktree pipeline (similar to werma's pattern, can be lifted)
- Sandbox runtime — Docker is fine, but need a strict allowlist policy

**Estimate:** 13-21 SP. Two-stage agent is the harder part; the webhook
plumbing is straightforward.

---

## Phase 4 — Unified gateway

**Goal:** consolidate Slack and Linear (and any future channels — GitHub
issues, Discord, etc) behind one FastAPI service that owns the agent core,
memory, and provider config.

**Architectural sketch**

```
GitHub PR ──webhook──┐
Linear   ──webhook──┼─→ /events   ┐
Slack    ──events───┘              │
                                   ▼
                          Unified core agent
                          (Pydantic AI, our existing)
                                   │
                                   ▼
                          Postgres (conversations,
                          idempotency, provider state)
```

Same agent core for all channels; only the edge handlers differ.

**Open design questions**

- Conversation identity across channels (e.g. user reports bug in Slack,
  agent files Linear issue, agent opens PR — is that one "session" or
  three?)
- Auth/idempotency
- Multi-tenancy if this ever becomes SaaS

**Dependencies**

- Postgres (Supabase or self-hosted on `fathom`)
- LiteLLM proxy by this point (cost tracking + virtual keys for prod)

**Estimate:** Pure scaffolding 5 SP if Phase 2 + 3 already share the core.
Becomes the natural home for both.

---

## Backlog (smaller, not on a critical path)

Ordered loosely by ratio of value-to-effort.

### Already-decided to-do

- [ ] Drop `claude-trigger.yml` — confirmed not working (Anthropic App
      filters bot-author @mentions and modifying workflows further triggers
      security skip). Manual `@claude` in PR description / comment is the
      working pattern. Do this in a non-meta PR so its own merge doesn't
      itself get skipped by review.
- [ ] Smoke test on a fresh non-meta PR after `claude-trigger.yml` removal:
      should produce 3 review surfaces — ai-chorus comment, Codex 👍 (or
      review), Claude review.
- [ ] Decide: keep both `CLAUDE.md` and `AGENTS.md` or drop one. Test
      empirically: open one PR with only AGENTS.md changed, observe whether
      Claude App still respects guidelines. If yes, drop CLAUDE.md.

### Stats / observability

- [ ] Stats block at top of comment: total time, fastest reviewer, total
      findings count. Useful and small (~30 lines in `markdown.py`).
- [ ] Cost tracking — capture token counts per provider where API exposes
      them, surface a "≈ \$X this run" line in the comment.
- [ ] Per-provider duration breakdown in the failure-status messages.

### Quality / coverage

- [ ] Severity gate as opt-in input: `fail_on_severity: critical`. Action
      exits 1 if any reviewer raises that severity. Lets repos use
      ai-chorus as a true merge-gate, not just an advisory comment.
- [ ] Inline PR comments instead of (or in addition to) the single body
      block — `gh api pulls/{n}/comments` with file + line. Bigger refactor;
      gated on whether the user wants line-anchored review UX.
- [ ] Cache provider responses by diff hash — if a PR re-pushes with no
      diff change, reuse the prior review. Saves quota. Watch invalidation.

### Distribution / polish

- [ ] PyPI publish for `chorus-review` CLI (already declared in
      `pyproject.toml` as a `[project.scripts]` entry). Then `uvx chorus-review --dry-run`
      works for any developer locally on any repo.
- [ ] Screenshots / GIF for README hero. Static PNG of a real review
      comment is the highest-signal artifact for recruiters.
- [ ] Custom per-repo `chorus.toml` — let consumers override prompts,
      provider weights, severity thresholds without forking.
- [ ] GitHub Marketplace listing (publish v1.0.0 release with the
      "Publish to Marketplace" toggle in the release UI).

### Cost / model strategy

- [ ] Add Anthropic as a fourth optional provider (`anthropic:claude-haiku`
      via paid `ANTHROPIC_API_KEY`, ~\$0.05-0.10/PR). Only worth it if
      portfolio benefits from the brand presence; current free-tier trio
      already demonstrates the architecture.
- [ ] LiteLLM proxy when ≥3 paid providers are in play — cost tracking,
      virtual keys per consumer, fallback chains at the gateway level.

### Tests / verification

- [ ] Verify Codex "Review triggers" toggle behaviour: push a fixup commit
      to an open PR, observe whether Codex re-reviews. Settings page had
      both "Auto code review" and "Review triggers" — need to confirm
      what the latter actually controls.
- [ ] Bigger-diff stress test — generate a 5K-line synthetic diff, check
      per-provider timeout behaviour and the truncation marker is correct.
- [ ] Empty-diff test on a PR that only renames files — does our
      `resolve_diff()` handle this gracefully?
- [ ] Cross-language sample apps: a Go, a Rust, a TypeScript file each
      with a planted bug; verify the reviewers catch issues outside
      Python (since our agent prompt is language-agnostic).

---

## Notes captured this session — don't lose these

- Anthropic restricted OAuth tokens to claude.ai / Claude Code only
  (Feb 2026). Never use `claude setup-token` output in CI; use API keys
  there instead.
- Anthropic free API tier is 5 RPM / 10 K input TPM across all Claude
  models — too tight for an agent loop. Paid Haiku (\$1/1M in, \$5/1M
  out) is the cheapest viable Anthropic option for ai-chorus.
- Gemini free tier is 20 RPD on Flash. Multi-turn agent runs eat 3-5
  calls each, so daily budget is ~4-6 PR runs. Polish layer doubles
  that — fallback chain in `polish.py` is the mitigation.
- Groq free tier llama-3.3-70b-versatile: 12K TPM means PR diffs over
  ~30K chars get rejected. Per-provider `max_input_chars=20_000` is the
  fix shipped in v1.0.0.
- OpenRouter free tier `nvidia/nemotron-3-nano-30b-a3b:free` does not
  support `tool_choice`. We use `PromptedOutput` for it, set
  `supports_tools=False` in `ProviderConfig`. Larger free models
  (`nemotron-3-super-120b-a12b:free`) timed out on every diff — picked
  the nano variant deliberately.
- GitHub Actions on `pull_request` event withholds secrets from fork
  PRs by default — public repo is safe to leave keys in repo secrets.
  Never use `pull_request_target` for code-execution triggers.
- The Claude App reacts with 👀 to @claude mentions but **does not
  post a review** when the PR modifies its own guidance/workflow files
  — a security guard, same pattern as `anthropics/claude-code-action`'s
  workflow-validation skip. This was empirically observed on PR #6
  (workflow change) and PR #9 (CLAUDE.md change).
- Codex configuration `Auto code review` and `Review triggers` per-repo
  defaults to `Follow personal preference`. If the personal default is
  off, every repo silently has no review. Toggle the personal default
  or override per-repo.
- Codex by design only flags P0 / P1 issues; on a clean docs PR it
  posts a 👍 reaction with no comment. Not a bug. Aligned with our
  AGENTS.md guidance.
