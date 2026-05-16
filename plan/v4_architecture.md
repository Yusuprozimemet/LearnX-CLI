# LearnX Dev Workflow v4 — Architecture

## What This Document Is

A reference for the complete dev workflow infrastructure after all 7 spec days are
implemented. Not the tutor application architecture — that lives in `plan/v3_plan.md`.
This covers only the tooling that wraps the application: container, scripts, agents,
tests, CI, and institutional memory.

---

## Target Folder Structure

```
E:/HYF/backend/
│
├── [CONTAINER LAYER]
│   ├── Dockerfile              ← learnx-dev image: Python 3.12 + ffmpeg + Claude Code
│   └── .dockerignore           ← keeps build context small; mirrors .gitignore
│
├── [ENTRY POINT SCRIPTS]
│   └── scripts/
│       ├── __init__.py
│       ├── learnx_dk.py        ← start a container session (no permission prompts)
│       ├── run_review.py       ← trigger 5-agent review pipeline
│       └── tests/
│           ├── __init__.py
│           ├── test_learnx_dk.py       ← tests for wrapper script
│           └── test_review_agents.py   ← tests for agent file validity
│
├── [AGENT DEFINITIONS]
│   └── .claude/
│       ├── settings.json           ← supervised mode default; deny rules active on host
│       ├── settings.assisted.json  ← committed reference for assisted mode permissions
│       │                              (settings.local.json is written/deleted at runtime — gitignored)
│       └── agents/
│           ├── quality.md          ← bugs, security, logic errors
│           ├── implementation.md   ← does code match the spec?
│           ├── testing.md          ← test coverage gaps
│           ├── simplification.md   ← over-engineering check
│           ├── product_check.md    ← runs pipeline + ffprobe + pydub + Playwright
│           └── README.md           ← documents fixes/ convention: agents flag, human writes
│
├── [E2E SMOKE TESTS]
│   └── tutor/tests/e2e/
│       ├── __init__.py
│       ├── README.md
│       ├── conftest.py             ← LLM mock; E2E runs without live API key
│       ├── fixtures/
│       │   ├── sample.md           ← tiny committed test document (< 300 words)
│       │   └── README.md
│       ├── test_pipeline_smoke.py  ← real pipeline runs; output files exist
│       ├── test_audio_quality.py   ← pydub: not silent, duration > 0
│       ├── test_video_streams.py   ← ffprobe: audio stream present + non-zero
│       ├── test_slide_render.py    ← Playwright: not blank, no error text
│       └── test_av_sync.py         ← timing.json drift < 500ms
│
├── [WORKFLOW DOCUMENTATION]
│   ├── dev_setup/
│   │   ├── spec-driven_plan.md
│   │   ├── sandbox_plan.md
│   │   ├── context_hygiene_plan.md
│   │   ├── autonomy_plan.md        ← updated: Level 4 via Docker section
│   │   ├── handoff_template.md     ← updated: container-mode handoff block
│   │   └── container_plan.md       ← new: Docker workflow step-by-step reference
│   └── dev_setup_update/
│       ├── update_plan.md          ← upgrade plan (this project)
│       ├── architecture.md         ← this file
│       └── specs/
│           ├── day0.md  ← repo cleanup
│           ├── day1.md  ← Docker image
│           ├── day2.md  ← container wrapper + settings
│           ├── day3.md  ← review pipeline + product check agent
│           ├── day4.md  ← dev_setup documentation
│           ├── day5.md  ← E2E smoke tests
│           ├── day6.md  ← CI/CD update
│           └── day7.md  ← CLAUDE.md update
│
├── [SPEC SOURCE OF TRUTH — tutor feature specs, unchanged]
│   ├── specs/v0/ v1/ v2/ v3/
│   └── plan/v0_plan.md … v3_plan.md
│
└── [INSTITUTIONAL MEMORY — human-curated, never auto-written]
    └── fixes/
        ├── fix001.md  ← ffmpeg not on PATH on Windows
        ├── fix009.md  ← per-unit loudnorm breaks audio with image concat
        ├── fix013.md  ← timing inflation from estimated offsets (v3 root cause)
        └── fix0NN.md  ← added by human after review; agents only flag candidates
```

---

## Component Responsibilities

| Component | Owns | Does NOT own |
|-----------|------|-------------|
| `Dockerfile` | Image definition: Python + ffmpeg + Claude Code | Application code; project deps beyond requirements.txt |
| `scripts/learnx_dk.py` | Starting a session in any of 4 modes; mounting credentials | What the agent does inside the session |
| `scripts/run_review.py` | Triggering the 5-agent review; passing spec path | Writing review agents; interpreting findings |
| `.claude/agents/` | Agent prompt definitions; "Suggested Fix Notes" output section | Writing to `fixes/` (agents never do this) |
| `tutor/tests/e2e/` | Running the real pipeline on a fixture; asserting output quality | Unit-testing individual functions (that's `tutor/tests/`) |
| `dev_setup/` | Human-readable workflow documentation | Enforcing workflow (that's specs + tests + CI) |
| `.github/workflows/ci.yml` | Running all tests + lint on every push | Local dev convenience |
| `CLAUDE.md` | Project instructions read by every new Claude session | Version-specific context (that belongs in specs) |
| `fixes/fix0NN.md` | Institutional memory: novel env/API/tool surprises not obvious from code | Tracking bugs (git log + tests own that) |

---

## Data Flow During One Spec Session

```
specs/v3/dayN.md        ← human writes this first; defines exactly what to build
       │
       ▼
python scripts/learnx_dk.py
       │   mounts /workspace (read-write)
       │   mounts ~/.claude  (read-only; credentials only)
       │   claude --dangerously-skip-permissions
       ▼
[agent inside container]
       │   reads spec → implements → python -m pytest → fixes → loops
       │   exit condition: all acceptance criteria pass + merge gate clean
       ▼
"done" report                             ← Point 1: agent flags surprises here
       │   - acceptance criteria checklist
       │   - gate status
       │   - files changed
       │   - surprises encountered (env quirks, API gotchas, tool edge cases)
       │     "Do NOT write to fixes/ — list here for human to decide"
       ▼
python -m pytest tutor/tests/e2e/ -v      ← Layer 2: real pipeline check
       │   fixtures/sample.md → pipeline run
       │   ffprobe → audio stream confirmed
       │   Playwright → slide screenshot taken
       │   pydub → not silent
       │   timing drift < 500ms
       ▼
python scripts/run_review.py --spec specs/v3/dayN.md
       │   quality · implementation · testing · simplification (parallel)
       │   product_check: runs pipeline again, reports on output quality
       │   each agent appends: "Suggested Fix Notes" section  ← Point 2
       ▼
human reads: "done" report (Point 1) + review findings (Point 2) + diff + screenshots
       │
       ├──► git merge sandbox/dayN   ← if MERGE READY
       │
       └──► write fixes/fixNNN.md    ← OPTIONAL; only if a finding is a novel
                                        env/API/tool gotcha not obvious from code
```

---

## Three Layers of Verification

```
Layer 1 — Unit tests
  Command: py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/
  Catches: wrong return values, missing fields, regressions
  Misses:  anything requiring real ffmpeg, real audio, real browser

Layer 2 — E2E smoke tests
  Command: py -m pytest tutor/tests/e2e/ -v
  Catches: silent audio, blank slides, pipeline crash, A/V drift
  Misses:  subjective quality (voice rhythm, curriculum clarity)

Layer 3 — Human review
  Trigger: python scripts/run_review.py
  Catches: anything subjective; agent code review provides structured checklist
  Human watches/listens to actual output before merging
```

Merge gate = all three layers in sequence. None is optional.

---

## The Container Boundary

```
Host machine                              Docker container
────────────────────                      ──────────────────────────
~/.claude   ──── read-only mount ──────►  /home/dev/.claude
~/.gitconfig ─── read-only mount ──────►  /home/dev/.gitconfig
project dir ──── read-write mount ─────►  /workspace

Container CAN:    write to /workspace, run git ops, call Claude API
Container CANNOT: reach GitHub remote (no remote configured),
                  access SSH keys, touch other directories,
                  affect host filesystem outside /workspace
```

This boundary is why `--dangerously-skip-permissions` is safe here.
The container is the deny rule. The deny rules in settings.json are redundant.

---

## Institutional Memory — How fixes/ Gets Updated

`fixes/` is human-curated. It stores knowledge that cannot be recovered by reading the
code — env quirks, API edge cases, tool gotchas, platform differences.

```
Where does knowledge live?

  Code + tests ──── explain WHAT and HOW ──────► any engineer can read
  CLAUDE.md    ──── explains the workflow ──────► every Claude session reads this
  fixes/       ──── explains the WHY behind
                    workarounds and surprises ──► read before starting any spec day

Who writes to fixes/?

  Agents: NEVER write directly to fixes/
            │
            ├──► Point 1 — implementing agent's "done" report (end of container session)
            │         lists surprises hit during implement→test→fix loop
            │         one bullet per item, informal, in plain English
            │
            └──► Point 2 — review agents' "Suggested Fix Notes" section
                      read the diff cold; flag non-obvious workarounds they see
                      product_check flags surprises from running the real pipeline
                      one bullet per finding, marked "candidate"

  Human:  reads "Suggested Fix Notes" from review output
            │
            ├── IS this a novel gotcha not obvious from code?
            │       YES → write fixes/fixNNN.md
            │       NO  → skip (the code or a test already explains it)
            │
            └── example triggers: new ffmpeg flag behaviour, Claude API quota edge case,
                Windows/Linux path difference, encoding quirk only visible in real output
```

**Decision rule:** if a future agent starting cold would make the same mistake without
the fix note, write it. If the test suite catches it automatically, skip it — the test
is already the documentation.

---

## Merge Gate Commands (After All 7 Days)

```powershell
# Unit tests
py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -v

# E2E smoke tests
py -m pytest tutor/tests/e2e/ -v

# Lint
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Same commands run locally and in CI (`.github/workflows/ci.yml`).
