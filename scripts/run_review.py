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

# Ensure project root is on sys.path when run as a script (not via pytest)
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.learnx_dk import _load_config, build_command  # noqa: E402, I001


REVIEW_PROMPT_TEMPLATE = """
You are running a pre-merge code review for the LearnX project.

Branch diff: run `git diff main...HEAD` to see all changes on this branch.
{spec_instruction}
{agents_instruction}

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

PHASE_1_FIX_ADDENDUM = """
After writing the consolidated report above, check the ## Recommendation section:

If the recommendation is NEEDS FIXES:
  1. Apply every blocking fix using Edit/Write tools
  2. Run: python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -m 'not slow' -q
  3. Commit all fixes: git add -A && git commit -m "review: phase 1 fix findings"

If the recommendation is MERGE READY, skip this step.
"""

PHASE_2_PROMPT_TEMPLATE = """
You are running Phase 2 of a two-phase code review.

The phase 1 review produced the following report:
=== PHASE 1 REPORT ===
{phase1_report}
=== END PHASE 1 REPORT ===

{agents_instruction}

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


def build_review_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec_path: pathlib.Path | None,
    extra_args: list[str],
    agents_dir: str = ".claude/agents",
) -> list[str]:
    if spec_path:
        spec_instruction = f"Spec file: {spec_path} (pass to implementation agent)"
    else:
        spec_instruction = "No spec file provided — implementation agent checks consistency only."

    agents_instruction = f"Review agents are in {agents_dir}/."

    prompt = REVIEW_PROMPT_TEMPLATE.format(
        spec_instruction=spec_instruction,
        agents_instruction=agents_instruction,
    ).strip()

    cmd = build_command(project_dir, home_dir, extra_args=[])

    claude_idx = cmd.index("claude")
    cmd = cmd[:claude_idx] + [
        "claude",
        "--dangerously-skip-permissions",
        "--print",
        prompt,
    ]

    return cmd


def run_phase1(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec_path: pathlib.Path | None,
    agents_dir: str,
    extra_args: list[str],
) -> tuple[int, str, bool]:
    """Run the 5-agent phase 1 review and apply fixes.

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

    cmd = build_command(project_dir, home_dir, extra_args=extra_args, interactive=False)
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
    """Run the 2-agent phase 2 verification.

    Returns:
        returncode — exit code of the Claude session
        output     — full captured stdout
    """
    agents_instruction = f"Review agents are in {agents_dir}/."
    prompt = PHASE_2_PROMPT_TEMPLATE.format(
        phase1_report=phase1_report,
        agents_instruction=agents_instruction,
    ).strip()

    cmd = build_command(project_dir, home_dir, extra_args=extra_args, interactive=False)
    claude_idx = cmd.index("claude")
    cmd = cmd[:claude_idx] + [
        "claude",
        "--dangerously-skip-permissions",
        "--print",
        prompt,
    ]

    rc, output = _capture_output(cmd)
    return rc, output


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    dry_run = "--dry-run" in argv
    no_two_phase = "--no-two-phase" in argv
    remaining = [a for a in argv if a not in ("--dry-run", "--no-two-phase")]

    spec_path: pathlib.Path | None = None
    if "--spec" in remaining:
        idx = remaining.index("--spec")
        spec_path = pathlib.Path(remaining[idx + 1])
        remaining = remaining[:idx] + remaining[idx + 2 :]

    agents_dir: str | None = None
    if "--agents-dir" in remaining:
        idx = remaining.index("--agents-dir")
        if idx + 1 >= len(remaining):
            print("error: --agents-dir requires a value")
            sys.exit(1)
        agents_dir = remaining[idx + 1]
        remaining = remaining[:idx] + remaining[idx + 2 :]

    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()

    config = _load_config(project_dir)
    if agents_dir is None:
        agents_dir = config["review"]["agents_dir"]

    two_phase = config["review"].get("two_phase", True) and not no_two_phase

    if dry_run:
        cmd = build_review_command(
            project_dir, home_dir, spec_path, remaining, agents_dir=agents_dir
        )
        print(" ".join(cmd))
        if two_phase:
            print("# [two-phase] phase 2 would run if phase 1 finds issues")
        return

    print("\n── Phase 1 (issue discovery) ──")
    _rc1, phase1_output, had_findings = run_phase1(
        project_dir, home_dir, spec_path, agents_dir, remaining
    )

    if two_phase and had_findings:
        print("\n── Phase 2 (fix verification) ──")
        run_phase2(project_dir, home_dir, phase1_output, agents_dir, remaining)
    elif two_phase and not had_findings:
        print("\n[review] phase 1 clean — skipping phase 2")
    else:
        print("\n[review] two-phase disabled — phase 1 only")


if __name__ == "__main__":
    main()
