# Day 28 (v10) — Phase 2 Agent Files, Config, and Review Functions

## Goal

Build the components for two-phase review without wiring them into the execution
flow yet:

1. Two new agent files: `verify_fixes.md` (did each finding get fixed?) and
   `regression_check.md` (did the fixes introduce new problems?).
2. `two_phase = true` added to `devloop.toml [review]` and `_DEFAULTS`.
3. `PHASE_1_FIX_ADDENDUM` — appended to the phase 1 prompt to instruct Claude
   to apply fixes and commit them when findings exist.
4. `PHASE_2_PROMPT_TEMPLATE` — prompt for the second Claude session.
5. `_capture_output()` helper — streams a subprocess to terminal in real-time
   while capturing the full text (needed to parse phase 1 output for findings).
6. `run_phase1()` and `run_phase2()` — the two review functions (not yet called
   from `main()`; that is day2).

---

## Done (merge gate)

```powershell
py -m pytest scripts/tests/test_learnx_dk.py -v
py -m pytest scripts/tests/test_review_agents.py -v
py -m ruff check scripts/
py -m ruff format --check scripts/
```

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Creates (new):
  .claude/agents/verify_fixes.md          ← phase 2 fix-completeness agent
  .claude/agents/regression_check.md      ← phase 2 regression agent

Modifies (existing):
  devloop.toml                            ← add two_phase = true to [review]
  scripts/learnx_dk.py                    ← add "two_phase" to _DEFAULTS["review"]
  scripts/run_review.py                   ← add _capture_output(),
                                            PHASE_1_FIX_ADDENDUM,
                                            PHASE_2_PROMPT_TEMPLATE,
                                            run_phase1(), run_phase2()
  scripts/tests/test_review_agents.py     ← add 5 new tests

Does NOT touch:
  scripts/run_review.py main()   ← wired in day2
  tutor/                         ← unchanged
  existing .claude/agents/ files ← unchanged
```

---

## Change 1 — Create `.claude/agents/verify_fixes.md`

```markdown
---
name: verify_fixes
description: Verify that each phase 1 review finding was fully resolved
---

You are running Phase 2 of a two-phase review. You will be given the phase 1
findings report and must determine whether each finding was addressed.

Run `git log --oneline main..HEAD` to list all commits, including any fix commits
added after phase 1. Run `git show <hash>` on any fix commit to see what changed.

For each finding from the phase 1 report, produce one line:
  RESOLVED   — the fix is present and correct
  PARTIAL    — something changed but the finding is not fully addressed
  UNRESOLVED — no change addresses this finding

End with a summary line:
  VERIFIED (N/N findings resolved)
  or
  STILL FAILING (N/M unresolved: <short list>)
```

---

## Change 2 — Create `.claude/agents/regression_check.md`

```markdown
---
name: regression_check
description: Check that phase 1 fix commits did not introduce new problems
---

You are running Phase 2 of a two-phase review. Examine only the changes introduced
by the phase 1 fix commits — not the original implementation diff.

Run `git log --oneline main..HEAD` to list all commits. Identify which commits are
fix commits (typically the most recent ones, added after the original spec work).
Run `git show <hash>` on each fix commit.

Look for:
1. New logic errors or off-by-ones introduced by the fix
2. New security issues or resource leaks
3. Broken or removed tests
4. Unrelated changes bundled into the fix commit

End with a single verdict line:
  CLEAN — no regressions detected
  or
  REGRESSION FOUND — <one-sentence description>
```

---

## Change 3 — Add `two_phase = true` to `devloop.toml [review]`

```toml
[review]
agents_dir = ".claude/agents"
review_script = "scripts/run_review.py"
two_phase = true          # set false to skip phase 2 verification
```

---

## Change 4 — Add `"two_phase"` to `_DEFAULTS["review"]` in `learnx_dk.py`

```python
_DEFAULTS: dict = {
    ...
    "review": {
        "agents_dir": ".claude/agents",
        "review_script": "scripts/run_review.py",
        "two_phase": True,    # ← new
    },
    ...
}
```

---

## Change 5 — Add `_capture_output()` to `run_review.py`

This helper runs a command non-interactively, streams each output line to the
terminal in real-time, and returns the complete captured text when done.

```python
def _capture_output(cmd: list[str]) -> tuple[int, str]:
    """Run cmd, stream stdout to terminal, return (returncode, full_output)."""
    lines: list[str] = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.decode(errors="replace")
        print(line, end="", flush=True)
        lines.append(line)
    proc.wait()
    return proc.returncode, "".join(lines)
```

Requires `interactive=False` on the Docker command so `stdout=PIPE` does not
conflict with `-it`. Both `run_phase1()` and `run_phase2()` must build their Docker
command with `interactive=False`.

---

## Change 6 — Add `PHASE_1_FIX_ADDENDUM` to `run_review.py`

Append this to the phase 1 prompt when calling `run_phase1()`. It instructs Claude
to apply fixes and commit before exiting:

```python
PHASE_1_FIX_ADDENDUM = """
After writing the consolidated report above, check the ## Recommendation section:

If the recommendation is NEEDS FIXES:
  1. Apply every blocking fix using Edit/Write tools
  2. Run: python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -m 'not slow' -q
  3. Commit all fixes: git add -A && git commit -m "review: phase 1 fix findings"

If the recommendation is MERGE READY, skip this step.
"""
```

---

## Change 7 — Add `PHASE_2_PROMPT_TEMPLATE` to `run_review.py`

```python
PHASE_2_PROMPT_TEMPLATE = """
You are running Phase 2 of a two-phase code review.

The phase 1 review produced the following report:
=== PHASE 1 REPORT ===
{phase1_report}
=== END PHASE 1 REPORT ===

Launch these two agents IN PARALLEL using the Task tool:
1. verify_fixes      — for each phase 1 finding, was it fully resolved?
2. regression_check  — did the fix commits introduce any new problems?

After both agents complete, output:

## Phase 2 Verification

### Fix completeness
[paste verify_fixes agent output verbatim]

### Regression check
[paste regression_check agent output verbatim]

## Phase 2 Gate
VERIFIED — all findings resolved and no regressions introduced
or
STILL FAILING — [list unresolved findings and/or regressions]
"""
```

---

## Change 8 — Add `run_phase1()` and `run_phase2()` to `run_review.py`

```python
def run_phase1(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec_path: pathlib.Path | None,
    agents_dir: str,
    extra_args: list[str],
) -> tuple[int, str, bool]:
    """
    Run the 5-agent phase 1 review and apply fixes.

    Returns:
        returncode   — exit code of the Claude session
        output       — full captured stdout
        had_findings — True if output contains "NEEDS FIXES"
    """
    if spec_path:
        spec_instruction = f"Spec file: {spec_path} (pass to implementation agent)"
    else:
        spec_instruction = "No spec file provided — implementation agent checks consistency only."

    agents_instruction = f"Review agents are in {agents_dir}/."
    base_prompt = REVIEW_PROMPT_TEMPLATE.format(
        spec_instruction=spec_instruction,
        agents_instruction=agents_instruction,
    ).strip()
    prompt = base_prompt + "\n\n" + PHASE_1_FIX_ADDENDUM.strip()

    cmd = build_command(project_dir, home_dir, extra_args=[], interactive=False)
    claude_idx = cmd.index("claude")
    cmd = cmd[:claude_idx] + [
        "claude",
        "--dangerously-skip-permissions",
        "--print",
        prompt,
    ]

    rc, output = _capture_output(cmd)
    had_findings = "NEEDS FIXES" in output
    return rc, output, had_findings


def run_phase2(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    phase1_report: str,
    agents_dir: str,
    extra_args: list[str],
) -> tuple[int, str]:
    """
    Run the 2-agent phase 2 verification.

    Returns:
        returncode — exit code of the Claude session
        output     — full captured stdout
    """
    prompt = PHASE_2_PROMPT_TEMPLATE.format(
        phase1_report=phase1_report,
    ).strip()

    cmd = build_command(project_dir, home_dir, extra_args=[], interactive=False)
    claude_idx = cmd.index("claude")
    cmd = cmd[:claude_idx] + [
        "claude",
        "--dangerously-skip-permissions",
        "--print",
        prompt,
    ]

    rc, output = _capture_output(cmd)
    return rc, output
```

`build_command()` now accepts `interactive=False` (added in v8/day1).

---

## New tests — add to `scripts/tests/test_review_agents.py`

```python
from scripts.run_review import (
    PHASE_1_FIX_ADDENDUM,
    PHASE_2_PROMPT_TEMPLATE,
    _capture_output,
    run_phase1,
    run_phase2,
)


def test_new_agent_files_exist():
    for name in ("verify_fixes", "regression_check"):
        assert (AGENTS_DIR / f"{name}.md").exists(), f"{name}.md missing"


def test_verify_fixes_agent_frontmatter():
    fm, body = _parse_frontmatter(AGENTS_DIR / "verify_fixes.md")
    assert fm.get("name") == "verify_fixes"
    assert "description" in fm
    assert len(body) >= 50


def test_regression_check_agent_frontmatter():
    fm, body = _parse_frontmatter(AGENTS_DIR / "regression_check.md")
    assert fm.get("name") == "regression_check"
    assert "description" in fm
    assert len(body) >= 50


def test_phase1_fix_addendum_mentions_commit():
    assert "commit" in PHASE_1_FIX_ADDENDUM.lower()


def test_phase2_prompt_template_has_phase1_report_placeholder():
    assert "{phase1_report}" in PHASE_2_PROMPT_TEMPLATE
    assert "verify_fixes" in PHASE_2_PROMPT_TEMPLATE
    assert "regression_check" in PHASE_2_PROMPT_TEMPLATE
```

---

## Acceptance criteria

- [ ] `.claude/agents/verify_fixes.md` exists with valid frontmatter (`name: verify_fixes`)
- [ ] `.claude/agents/regression_check.md` exists with valid frontmatter (`name: regression_check`)
- [ ] Both new agent bodies reference running `git show` on fix commits
- [ ] `devloop.toml [review]` has `two_phase = true`
- [ ] `_DEFAULTS["review"]["two_phase"]` is `True`
- [ ] `PHASE_1_FIX_ADDENDUM` contains a `git commit` instruction
- [ ] `PHASE_2_PROMPT_TEMPLATE` has `{phase1_report}` placeholder, references both new agent names
- [ ] `_capture_output()` streams output to terminal AND returns full text
- [ ] `run_phase1()` uses `interactive=False` in `build_command()` (required for `stdout=PIPE`)
- [ ] `run_phase1()` sets `had_findings=True` when output contains `"NEEDS FIXES"`
- [ ] `run_phase1()` sets `had_findings=False` when output contains `"MERGE READY"`
- [ ] `run_phase2()` uses `interactive=False` and `PHASE_2_PROMPT_TEMPLATE` with `phase1_report` filled in
- [ ] `test_new_agent_files_exist` passes
- [ ] `test_verify_fixes_agent_frontmatter` passes
- [ ] `test_regression_check_agent_frontmatter` passes
- [ ] `test_phase1_fix_addendum_mentions_commit` passes
- [ ] `test_phase2_prompt_template_has_phase1_report_placeholder` passes
- [ ] All pre-existing tests still pass
- [ ] ruff clean
