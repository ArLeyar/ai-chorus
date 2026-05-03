# Changelog

All notable changes to this project will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `AGENTS.md` and `CLAUDE.md` (identical content) — review guidelines
  for the parallel AI reviewers (Claude GitHub App, Codex App,
  ai-chorus). Centralises severity calibration, what to focus on
  vs skip, code conventions. Both filenames committed because vendor
  branding hasn't converged on a single standard yet.
- `.github/workflows/claude-trigger.yml` — posts a single `@claude
  please review` comment on every newly opened PR (regardless of how
  the PR was opened: UI, API, script, bot). The official Claude GitHub
  App responds using the user's Pro/Max subscription quota. No OAuth
  token, no API key, no secrets in CI.
- `.github/pull_request_template.md` with `## What` / `## Tests`
  structure for human-authored PR descriptions.

### Removed
- `.github/workflows/claude-review.yml` and the OAuth-token integration
  with `anthropics/claude-code-action`. Anthropic restricted OAuth
  tokens to claude.ai / Claude Code in Feb 2026, so headless CI use
  hits authentication errors. The PR-template-plus-App path is
  simpler, free under the existing subscription, and avoids
  maintaining secrets in GitHub.

## [v1.0.0] — 2026-05-03

Initial public release as a composite GitHub Action.

### Added
- Composite action surface (`action.yml`); consumers integrate via
  `uses: ArLeyar/ai-chorus@v1` plus seven env vars.
- Three parallel free-tier reviewers: Gemini 2.5 Flash, Llama 3.3 70B
  via Groq, Nemotron Nano 30B via OpenRouter.
- Pydantic AI agent factory with per-provider capability flags
  (`supports_tools`, `max_input_chars`, `timeout_s`).
- Deterministic consensus (rapidfuzz grouping; consensus / disagreement
  / unique classification).
- Optional LLM-as-judge polish layer with provider fallback chain;
  rendered as a GitHub `[!NOTE]` callout.
- Graceful degradation: missing API keys, 429s, timeouts, and
  malformed model output all become `ProviderReview(status=...)`
  markers — comments always post.
- Strict tooling baseline: ruff (11 rule sets), mypy `--strict`,
  pytest with branch coverage, pre-commit hooks, Makefile mirroring CI.

[Unreleased]: https://github.com/ArLeyar/ai-chorus/compare/v1.0.0...HEAD
[v1.0.0]: https://github.com/ArLeyar/ai-chorus/releases/tag/v1.0.0
