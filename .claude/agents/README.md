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
