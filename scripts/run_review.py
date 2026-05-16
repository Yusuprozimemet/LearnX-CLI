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


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    dry_run = "--dry-run" in argv
    remaining = [a for a in argv if a != "--dry-run"]

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

    if agents_dir is None:
        config = _load_config(project_dir)
        agents_dir = config["review"]["agents_dir"]

    cmd = build_review_command(project_dir, home_dir, spec_path, remaining, agents_dir=agents_dir)

    if dry_run:
        print(" ".join(cmd))
        return

    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
