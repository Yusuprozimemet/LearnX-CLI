# Day 3 — Review Pipeline + Product Verification

## Goal

Add two things between "agent reports done" and "human merges":

**1. Code review agents** — four agents (quality, implementation, testing, simplification)
check the diff for bugs, spec compliance, test gaps, and over-engineering. This is code
review: does the code look right?

**2. Product verification agent** — one agent actually runs the LearnX pipeline on the
committed test fixture, checks the output files with ffprobe and pydub, and takes a
Playwright screenshot of the rendered HTML slides. This is experience review: does the
product work?

The distinction matters. Code review can pass on a video pipeline that produces silent
audio. Product verification catches it because it actually runs ffprobe on the output.

Both run inside the Docker container. Both produce plain-text findings. Neither blocks
the merge automatically — the human reads the summary and decides.

Note: Day 5 adds the full E2E smoke test suite. This day adds the review-time product
check that the agent runs before reporting findings. They are complementary: E2E tests
catch regressions on every push; the product verification agent provides a structured
human-readable summary during review.

---

## Done (merge gate)

```powershell
# Agent files are valid (frontmatter parses, content non-empty)
py -m pytest scripts/tests/test_review_agents.py -v

# Review script generates correct command (dry run)
python scripts/run_review.py --dry-run

# Full suite still green
py -m pytest
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Report: paste test results and dry-run output.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Creates (new):
  .claude/agents/quality.md           ← bugs, security, logic errors
  .claude/agents/implementation.md    ← does code match the spec?
  .claude/agents/testing.md           ← test coverage and quality
  .claude/agents/simplification.md    ← over-engineering check
  .claude/agents/product_check.md     ← runs pipeline, verifies output quality
  .claude/agents/README.md            ← how to add/modify agents
  scripts/run_review.py               ← launches review session inside container
  scripts/tests/test_review_agents.py ← validates agent files and review command

Does NOT touch:
  tutor/                  ← no application code changes
  Dockerfile              ← no changes to the image
  .claude/settings.json   ← no settings changes
  dev_setup/              ← documentation update is Day 4
  tutor/tests/e2e/        ← E2E smoke test suite is Day 5
```

---

## Agent file format

Each agent is a Markdown file with a YAML frontmatter block and a plain-text prompt body.
Claude Code loads agents from `.claude/agents/` automatically.

```
---
name: <agent-name>
description: <one-line description used by the Task tool>
---

<review instructions — plain text, numbered list preferred>
```

**Frontmatter rules:**
- `name` must match the filename without `.md`
- `description` is used by Claude when selecting which agent to invoke
- Body text is the prompt sent to the agent when it runs

---

## Agent file contents

### `.claude/agents/quality.md`

```markdown
---
name: quality
description: Reviews code for bugs, security issues, and logic errors
---

Review the git diff for the following. Report each finding as:
  FILE:LINE — severity (critical/major/minor) — description

1. Logic errors: off-by-one, wrong condition, silent failure paths
2. Security: hardcoded secrets, path traversal, injection vulnerabilities
3. Resource leaks: unclosed files, unreleased locks, unbounded loops
4. Error handling: exceptions swallowed silently, wrong exception types caught

Output "NO ISSUES FOUND" if the diff is clean. Do not suggest style improvements
— that is the simplification agent's job.
```

### `.claude/agents/implementation.md`

```markdown
---
name: implementation
description: Verifies that the implementation matches the spec's acceptance criteria
---

You will be given a git diff and the acceptance criteria from the spec that drove
these changes. Check each criterion against the diff.

For each criterion:
- PASS: the diff clearly satisfies it
- FAIL: the diff does not satisfy it — explain what is missing
- PARTIAL: the diff partially satisfies it — explain what remains

List spec criteria in order. End with a one-line summary: "N/M criteria satisfied."

If no spec file is provided, verify that the implementation is internally consistent
and that all stated goals in commit messages or comments are actually achieved.
```

### `.claude/agents/testing.md`

```markdown
---
name: testing
description: Reviews test coverage and test quality for the changed code
---

Review the test changes in the diff.

1. Coverage: are all new code paths exercised by at least one test?
2. Assertions: do tests assert specific values, or do they just assert no exception?
3. Isolation: do tests depend on external state (filesystem, network, other tests)?
4. Names: do test names describe what they verify (not just "test_function_x")?
5. Missing tests: list any new public functions or edge cases with no test at all.

Format: FILE — finding description
Output "TESTS LOOK GOOD" if no issues found.
```

### `.claude/agents/simplification.md`

```markdown
---
name: simplification
description: Detects over-engineering, unnecessary abstraction, and dead code
---

Review the diff for complexity that is not justified by the spec.

1. Abstractions: classes or functions created for a single use case
2. Premature generalisation: parameters, config, or interfaces for hypothetical callers
3. Dead code: code that is added but never called
4. Over-indirection: wrapper functions that just call one other function
5. Unnecessary comments: comments that restate what the code already says

Rate overall complexity: LOW / MEDIUM / HIGH.
List specific findings only. Do not suggest refactors not related to over-engineering.
```

### `.claude/agents/product_check.md`

```markdown
---
name: product_check
description: Runs the LearnX pipeline on the test fixture and verifies audio, video, and slide output quality
---

You are checking whether the product works, not whether the code looks right.
Run the following steps in order and report the result of each.

## Step 1 — Run the pipeline on the test fixture

```bash
python -m tutor generate tutor/tests/e2e/fixtures/sample.md --output /tmp/learnx_check
```

Expected: exits 0, output directory contains tutorial.mp3, tutorial.mp4 (or slides).
If it crashes: paste the traceback. STOP — do not proceed to further steps.

## Step 2 — Verify audio stream in video

```bash
ffprobe -v error \
  -select_streams a:0 \
  -show_entries stream=codec_type,duration,bit_rate \
  -of json /tmp/learnx_check/tutorial.mp4
```

Expected: `codec_type` is `audio`, `duration` > 0.
FAIL if: no audio stream returned, or duration is 0 or null.

## Step 3 — Check audio is not silent

```python
from pydub import AudioSegment
audio = AudioSegment.from_mp3("/tmp/learnx_check/tutorial.mp3")
db_level = audio.dBFS
print(f"Audio level: {db_level:.1f} dBFS")
# Anything above -60 dBFS is audible
assert db_level > -60, f"Audio appears silent: {db_level:.1f} dBFS"
```

Expected: dBFS above -60.
FAIL if: dBFS is -inf or below -60 (silent or near-silent track).

## Step 4 — Screenshot HTML slides (if slides were generated)

```python
from playwright.sync_api import sync_playwright
import pathlib

slide_dir = pathlib.Path("/tmp/learnx_check/slides")
if slide_dir.exists():
    html_files = list(slide_dir.glob("*.html"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for html in html_files[:3]:   # first 3 slides max
            page.goto(f"file://{html}")
            page.wait_for_load_state("networkidle")
            screenshot = f"/tmp/learnx_check/screenshot_{html.stem}.png"
            page.screenshot(path=screenshot)
            print(f"Screenshot saved: {screenshot}")
        browser.close()
```

After running: describe what the screenshots look like. Are slides blank? Is text visible?
Are there any error messages or broken layout?

## Step 5 — Check A/V sync (timing.json vs audio duration)

```python
import json
from pydub import AudioSegment

timing = json.loads(
    pathlib.Path("/tmp/learnx_check/tutorial.timing.json").read_text()
)
audio = AudioSegment.from_mp3("/tmp/learnx_check/tutorial.mp3")

last_unit = max(int(k) for k in timing["units"])
last_entry = timing["units"][str(last_unit)][-1]
timing_end_ms = last_entry["end_ms"]
audio_duration_ms = len(audio)
drift_ms = abs(audio_duration_ms - timing_end_ms)

print(f"Audio duration: {audio_duration_ms}ms")
print(f"Timing end:     {timing_end_ms}ms")
print(f"Drift:          {drift_ms}ms")
assert drift_ms < 500, f"A/V drift too large: {drift_ms}ms"
```

Expected: drift < 500ms.
FAIL if: drift >= 500ms (slides and audio will be noticeably out of sync).

## Report format

```
PIPELINE RUN: PASS / FAIL
AUDIO STREAM: PRESENT (Xs) / MISSING
SILENCE CHECK: {dBFS value} — PASS / FAIL
SLIDE SCREENSHOTS: [describe what you see for each slide]
A/V SYNC: {drift}ms — PASS / FAIL

OVERALL: PRODUCT WORKING / PRODUCT BROKEN
Blocking issues: [list or "none"]

Suggested fix notes:
[List any novel pipeline surprises — env issues, tool edge cases, encoding quirks —
that are NOT obvious from reading the code. Write "none" if nothing surprising happened.
Do NOT write to fixes/ — this is for the human to decide.]
```
```

### `.claude/agents/README.md`

```markdown
# Review Agents

Each `.md` file in this directory is a Claude sub-agent invoked during pre-merge review.

## Agents

| File | Role |
|------|------|
| quality.md | Bugs, security, logic errors |
| implementation.md | Does the code match the spec's acceptance criteria? |
| testing.md | Test coverage and quality |
| simplification.md | Over-engineering and dead code |
| product_check.md | Runs the real pipeline, checks output quality with ffprobe/pydub/Playwright |

## How to add an agent

1. Create `.claude/agents/<name>.md`
2. Add YAML frontmatter with `name` (must match filename) and `description`
3. Write the review instructions in the body
4. Add the agent name to the parallel launch list in `REVIEW_PROMPT_TEMPLATE` in `scripts/run_review.py`

## The fixes/ convention

Agents do NOT write to `fixes/`. The `fixes/` directory is human-curated institutional
memory for surprises that are not derivable from reading the code.

Each agent's output includes a **Suggested Fix Notes** section. If an agent encountered
a novel env quirk, API edge case, or tool gotcha during review, it flags it there.
The human reads those flags and decides whether to write a permanent `fixes/fixNNN.md`.

Rule: if removing the fix note would confuse a future agent reading the codebase cold,
it belongs in `fixes/`. If the code or a test already explains it, it does not.
```

---

## `scripts/run_review.py` — algorithm

```python
#!/usr/bin/env python3
"""
run_review.py — Launch a review session inside the learnx-dev container.

Usage:
    python scripts/run_review.py [--dry-run] [--spec specs/v3/dayN.md]

Runs Claude inside Docker with a prompt that invokes the four review agents
in parallel against the current branch diff (git diff main...HEAD).

The --spec flag passes the spec file to the implementation agent so it can
check acceptance criteria directly. Optional but recommended.
"""

import pathlib
import subprocess
import sys

from scripts.learnx_dk import IMAGE, WORKSPACE, _to_posix, build_command


REVIEW_PROMPT_TEMPLATE = """
You are running a pre-merge code review for the LearnX project.

Branch diff: run `git diff main...HEAD` to see all changes on this branch.
{spec_instruction}

Launch the following four review agents IN PARALLEL using the Task tool:
1. quality        — bugs, security, logic errors
2. implementation — does the code match the spec?
3. testing        — test coverage and quality
4. simplification — over-engineering and dead code

After all agents complete, write a single consolidated report:

## Review Summary
[one paragraph: overall assessment]

## Findings by Agent
[paste each agent's output under its name]

## Recommendation
MERGE READY — no blocking issues found
or
NEEDS FIXES — list blocking issues that must be resolved before merge

## Suggested Fix Notes
List any novel surprises encountered during this review that are NOT obvious from
reading the code: environment quirks, API edge cases, tool behaviour that contradicts
documentation, Windows/Linux differences, or timing/encoding gotchas.

Format each as:
- fixes/fix0NN.md candidate: [one sentence describing the gotcha and where it bites]

Leave this section empty (write "none") if nothing surprised you.

NOTE: Do NOT write to the fixes/ directory. This section is for the human to read
and decide whether the finding warrants a permanent fix note.
"""


def build_review_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec_path: pathlib.Path | None,
    extra_args: list[str],
) -> list[str]:
    if spec_path:
        spec_instruction = f"Spec file: {spec_path} (pass to implementation agent)"
    else:
        spec_instruction = "No spec file provided — implementation agent checks consistency only."

    prompt = REVIEW_PROMPT_TEMPLATE.format(spec_instruction=spec_instruction).strip()

    # Build the base docker run command (reuses learnx_dk logic)
    cmd = build_command(project_dir, home_dir, extra_args=[])

    # Replace the trailing 'claude --dangerously-skip-permissions' with a
    # prompt-driven invocation
    claude_idx = cmd.index("claude")
    cmd = cmd[:claude_idx] + [
        "claude",
        "--dangerously-skip-permissions",
        "--print",          # non-interactive: print result and exit
        prompt,
    ]

    return cmd


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    dry_run   = "--dry-run" in argv
    remaining = [a for a in argv if a != "--dry-run"]

    spec_path: pathlib.Path | None = None
    if "--spec" in remaining:
        idx       = remaining.index("--spec")
        spec_path = pathlib.Path(remaining[idx + 1])
        remaining = remaining[:idx] + remaining[idx + 2:]

    project_dir = pathlib.Path.cwd()
    home_dir    = pathlib.Path.home()

    cmd = build_review_command(project_dir, home_dir, spec_path, remaining)

    if dry_run:
        print(" ".join(cmd))
        return

    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
```

---

## Acceptance criteria

- [ ] All five agent files exist in `.claude/agents/`: quality, implementation, testing, simplification, product_check
- [ ] Each agent file has valid YAML frontmatter (`name` and `description` fields)
- [ ] `name` in frontmatter matches the filename without `.md`
- [ ] Each agent body is non-empty (at least 50 characters)
- [ ] `product_check.md` body contains references to all five steps: pipeline run, ffprobe, pydub dBFS check, Playwright screenshot, A/V sync
- [ ] `product_check.md` report format includes a "Suggested fix notes" section
- [ ] `.claude/agents/README.md` exists and documents the `fixes/` convention (agents flag, human writes)
- [ ] Consolidated review report template includes a "Suggested Fix Notes" section with instructions not to write to `fixes/`
- [ ] `scripts/run_review.py` exists and is importable
- [ ] `python scripts/run_review.py --dry-run` prints a docker command containing `--print`
- [ ] `python scripts/run_review.py --dry-run --spec specs/v3/day13.md` prints a command containing the spec path in the prompt
- [ ] All existing pytest tests still pass

---

## Tests — `scripts/tests/test_review_agents.py`

- `test_all_five_agent_files_exist` — assert quality, implementation, testing, simplification, product_check `.md` files exist in `.claude/agents/`
- `test_agent_frontmatter_has_name_and_description` — parse YAML frontmatter of each file; both keys present
- `test_agent_name_matches_filename` — `name` value equals `Path(file).stem`
- `test_agent_body_is_nonempty` — text after frontmatter delimiter is at least 50 chars
- `test_product_check_covers_ffprobe` — `product_check.md` body contains the string `ffprobe`
- `test_product_check_covers_silence` — `product_check.md` body contains `dBFS`
- `test_product_check_covers_playwright` — `product_check.md` body contains `playwright` (case-insensitive)
- `test_product_check_covers_sync` — `product_check.md` body contains `drift`
- `test_review_command_contains_print_flag` — `build_review_command(...)` output contains `--print`
- `test_review_command_with_spec_includes_spec_path` — when spec_path given, its string appears in the prompt within the command
- `test_review_dry_run_does_not_call_subprocess` — `main(["--dry-run"])` does not invoke `subprocess.run`
- `test_review_prompt_contains_fix_notes_section` — `REVIEW_PROMPT_TEMPLATE` contains the string `Suggested Fix Notes`
- `test_review_prompt_says_do_not_write_fixes` — `REVIEW_PROMPT_TEMPLATE` contains `Do NOT write to fixes`
- `test_product_check_covers_fix_notes` — `product_check.md` body contains `Suggested fix notes`
- `test_readme_mentions_fixes_convention` — `README.md` body contains `fixes/` and `human`
