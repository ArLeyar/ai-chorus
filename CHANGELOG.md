# Changelog

All notable changes to this project will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Optional pairing with `anthropics/claude-code-action` as a paid-tier
  reviewer alongside ai-chorus. Auth via Claude Pro/Max OAuth token.
- `CHANGELOG.md` documenting public-facing changes.

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
