# LearnX CLI — Product Context

> For DevLoop workflow instructions (spec days, implementation loop, commands) see **DEVLOOP.md**.

---

## What This Project Is

LearnX is a Python CLI that converts a Markdown document into an audio-first tutorial
with optional video. The pipeline is:

```
Document → chunk → LLM summarise → LLM curriculum → LLM dialogue
        → TTS render → assemble audio (+ timing.json)
        → (optional) LLM visual plan → render slides → subtitle → mp4
```

Entry point: `tutor/__main__.py`. CLI commands live in `tutor/cli/`.
Primary platform: Windows / PowerShell. Python 3.12+.

---

## Two Layers in This Repo

```
tutor/     LearnX CLI — the product. Audio tutorial generator.
scripts/   DevLoop — the build system. Runs Claude in Docker, manages review pipeline.
```

These are independent concerns that share one repository. `scripts/` is never imported
by `tutor/`. A user of LearnX CLI never touches `scripts/`.

---

## Product Layout

```
tutor/              the Python package
  __main__.py         CLI entry point
  models.py           all dataclasses — start here to understand data shapes
  constants.py        silence gap constants, limits
  config.py           LLM provider / model config
  audio/              audio pipeline (audio_builder.py, tts_renderer.py)
  generation/         LLM pipeline (curriculum, dialogue, narrator, visual_planner)
  ingestion/          document processing (chunker, doc_analyzer)
  visual/             video pipeline (beat_timer, slide_compositor, subtitle_writer…)
  player/             interactive playback
  cli/                CLI commands and shell
  tests/              pytest unit suite — mirrors tutor/ structure
  tests/e2e/          E2E smoke tests — run real pipeline, check output quality
  infra/              LLM client wrapper

specs/              versioned spec files — source of truth for all tutor/ code
  v0/ … v3/          completed versions (regression reference)
  v4-workflow/        DevLoop upgrade specs (archived)
  v5/ … v11/         active versions

plan/               version-level design and architecture docs
  v0_plan.md … v11_plan.md
  v4_update_plan.md  DevLoop v4 upgrade rationale
  v4_architecture.md DevLoop component map

fixes/              post-mortem notes (fix001.md … )
                    read these before starting — they contain env/API gotchas

dev_setup/          developer process documentation
  spec-driven_plan.md      what SDD means and how to write specs
  context_hygiene_plan.md  how to manage session context
  sandbox_plan.md          git branch + test isolation strategy
  autonomy_plan.md         how to run the implement→test→fix loop (Level 1–4)
  handoff_template.md      copy-paste prompt for starting each spec day
  container_plan.md        how to run Claude inside Docker (Level 4 workflow)

scripts/            DevLoop tooling (NOT imported by tutor/)
  devloop.py          launcher — runs Claude inside Docker
  run_review.py       triggers 5-agent code + product review
  dk/                 devloop submodules (config, docker, dashboard, runners…)
  tests/              pytest tests for scripts/

sandbox/            throwaway prototype scripts — NOT imported by tutor/

.claude/
  settings.json       allow list only (deny rules removed — Docker is the sandbox)
  agents/             review + product check agent definitions
```

---

## Code Quality Rules

These rules apply to every file touched during a spec day or refactoring session.

```
MAX 400 LOC PER FILE — if a file exceeds 400 lines, split it before committing.
  Extract by cohesion: group things that change together and depend on each other.
  Keep the public interface in the original file; move implementation to submodules.

CLEAN CODE
  Functions do one thing. Name them for what they do, not how.
  No functions longer than 40 lines. No nesting deeper than 3 levels.
  No magic numbers — use named constants.
  No dead code, no commented-out blocks, no TODO left in committed code.
  Never hardcode a parameter value inside a function body when the caller
    passed that value as an argument — always forward the parameter.

MAINTAINABILITY
  Every module has a single clear responsibility (SRP).
  Avoid deep coupling: pass what a function needs, don't let it reach into globals.
  Prefer explicit imports over star imports.
  Update imports everywhere when you move code.

SCALABILITY
  New behaviour should be addable without modifying existing logic (OCP).
  Favour composition over inheritance for extending behaviour.
  Config goes in devloop.toml / llm_config.toml, not hardcoded in source.

REUSABILITY
  Pure functions (no side effects) are easier to test and reuse — prefer them.
  Separate I/O (file reads, subprocess calls, network) from logic.
  If two files share a helper, extract it to a shared module; never duplicate.
```

---

## Where to Find Things

| Question | Where to look |
|---|---|
| What does this feature do? | `specs/vN/dayN.md` |
| Why was this approach chosen? | `plan/vN_plan.md` |
| Why does this edge case exist? | `fixes/fix0NN.md` |
| What dataclasses exist? | `tutor/models.py` |
| What silence constants are used? | `tutor/constants.py` |
| How is the LLM called? | `tutor/infra/llm.py` |
| How to start a new spec day? | `dev_setup/handoff_template.md` |

---

## Read Before Starting Any v3 Day

1. `fixes/fix001.md` — ffmpeg is not always on PATH on Windows; pydub needs the binary patched in at startup.
2. `fixes/fix013.md` — timing inflation root cause: `compute_slide_timings()` was using estimated beat offsets instead of actual MP3 durations.
3. `fixes/fix009.md` — per-unit loudnorm breaks audio duration with image-based concat video; volume boost is applied at encode time instead.
4. `plan/v3_plan.md` — the architectural rationale for the whole v3 approach.
