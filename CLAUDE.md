# Agent guidelines

This repo is reviewed in parallel by ai-chorus (multi-model fan-out)
and external AI reviewers (Claude GitHub App, Codex). These guidelines
apply to all of them. Both `CLAUDE.md` and `AGENTS.md` are committed
with identical content so each tool reads its branded file.

## Repo overview

ai-chorus is a vendor-agnostic AI ops platform shipped as a composite
GitHub Action. Phase 1 is multi-model PR review with deterministic
consensus. The codebase is small, typed, and uses Pydantic AI for the
agent layer.

Critical files:

- `src/chorus/providers.py` — declarative provider config (`ProviderConfig`
  with `supports_tools`, `max_input_chars`, `timeout_s`)
- `src/chorus/models.py` — `Finding` / `ReviewResult` / `ProviderReview`
  / `Consensus` Pydantic models. **Source of truth** for review shape
- `src/chorus/agents.py` — Pydantic AI `Agent` factory, conditional
  tool registration based on `supports_tools`
- `src/chorus/consensus.py` — deterministic Python (rapidfuzz). No LLM
- `src/chorus/polish.py` — optional LLM-as-judge verdict, opt-in via
  `CHORUS_POLISH=1`, fallback chain across providers
- `src/chorus/markdown.py` — pure rendering of `Consensus` to comment
- `action.yml` — composite action surface for downstream consumers

## Review focus

Spend reviewer attention on:

- **Correctness and security**: race conditions, missing error handling
  on real failure paths, secret leakage, prompt injection that could
  reach external systems
- **Architectural invariants**: graceful degradation must hold
  (`ProviderReview.status` set, comment posts no matter what), provider
  config stays the only place model strings live, deterministic consensus
  must remain pure Python
- **API surface**: changes to `action.yml` inputs or env contract that
  break existing consumer workflows
- **Provider-specific gotchas**: tool calling reliability differs per
  provider; `supports_tools=False` providers must use `PromptedOutput`

## Skip / deprioritise

Automated tooling already gates these — flagging them adds noise:

- Style and formatting (ruff handles via `tool.ruff` config)
- Type errors (mypy `--strict` runs in CI)
- Test coverage requests for LLM-bound modules (intentional 0% on
  `agents.py` / `review.py` / `providers.py` — orchestration tested
  end-to-end, not unit-mocked)
- Praise paragraphs or restating what the diff does

## Code conventions

- Python 3.13, line length 100, double quotes, ruff format
- `from __future__ import annotations` everywhere
- Imports used only in annotations live under `if TYPE_CHECKING`
- `BLE001` (blind except) is **not** enabled in ruff — broad catches
  in graceful-degradation paths are intentional and documented inline
- Pydantic models for any data crossing module boundaries; tuples and
  dicts only for purely local helpers
- No `# type: ignore` without a directly-after-issue comment explaining
  why mypy is wrong in this case

## Severity guide

When reporting findings, calibrate:

- **critical** — broken in production; data loss; security vulnerability
- **major** — wrong behaviour; race condition; perf regression
- **minor** — bug in non-critical path; missing edge case; clear smell
- **nit** — style, naming, docstrings (deprioritise — usually skip)

If the diff is clean, return zero findings with a one-line summary.
Don't invent issues to look thorough.

## Tool use

When the review tool exposes file/grep/symbol search, use it. Verify
hypotheses about cross-file impact with evidence before reporting. Do
not guess; cite the file and line you confirmed against.
