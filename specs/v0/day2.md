# Day 2 — Type Safety

## Goal

Configure mypy and fix the most impactful type errors so the existing type
annotations do more than document intent. After this day, `mypy tutor/` passes
with no errors and every developer can run it locally before opening a PR.

**mypy is a local developer tool in v0 — it is not added to CI.** Running a
full type check in CI adds 20–40 seconds per push and requires fixing every
strict-mode error before the gate turns green. That is a distraction from feature
work at this stage. The right enforcement point is pre-PR discipline: run
`mypy tutor/` locally, fix errors, then push.

---

## mypy configuration — `pyproject.toml`

Add `[tool.mypy]` to `pyproject.toml` (Day 0 is a prerequisite):

```toml
[tool.mypy]
python_version      = "3.11"
strict              = true
warn_unused_ignores = true
exclude             = ["tutor/tests/"]
```

**`strict = true`** enables the full set of checks:
- `disallow_untyped_defs` — every function must have annotations
- `disallow_any_generics` — `list` must be `list[str]`, not bare `list`
- `warn_return_any` — functions returning `Any` are flagged
- `no_implicit_optional` — `def f(x: str = None)` is an error

**`warn_unused_ignores = true`** — stale `# type: ignore` comments are flagged
as errors, preventing them from accumulating.

**`exclude = ["tutor/tests/"]`** — tests use `assert`, `MagicMock`, and patterns
that generate noise under strict mode. Tests are excluded from the strict pass.

### Third-party stubs

pygame, pydub, and edge-tts do not ship inline type information. Rather than
scattering `# type: ignore` across call sites, suppress at the module level:

```toml
[[tool.mypy.overrides]]
module = ["pygame.*", "pydub.*", "edge_tts.*"]
ignore_missing_imports = true
```

Pillow and tqdm have published stub packages — install them via the `[dev]` group
(already in Day 0's `pyproject.toml`):

```toml
"types-Pillow",
"types-tqdm",
```

---

## Known errors to fix

These are the errors mypy will surface immediately on the current codebase.
Fix them in this order — shared types first, then outward.

### 1. `tutor/models.py` — `object` field

```python
# Current — too broad, loses all type information
diagram_spec: object = None   # str (DOT) | dict | None

# Fix
diagram_spec: str | dict | None = None
```

### 2. `tutor/cli/commands.py` — `ShellContext.player`

```python
# Current — erases all method types on the player
player: object = None

# Fix — TYPE_CHECKING guard avoids the circular import
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tutor.player.player import TutorPlayer

@dataclass
class ShellContext:
    player: TutorPlayer | None = None
```

### 3. `tutor/infra/llm.py` — untyped `llm_fn` parameter

The LLM callable is passed across the pipeline as `Callable` with no signature.
Define a type alias once and use it everywhere:

```python
from typing import TypeAlias

LLMFn: TypeAlias = Callable[[list[dict[str, str]], str], str]
```

Replace `Callable` or `Callable[..., Any]` with `LLMFn` in all function
signatures across `generation/`, `visual/`, and `cli/`.

### 4. `tutor/visual/` — missing return annotations

Some `compose_*` functions and `_run_ffmpeg` have no return type. Add `-> Path`
or `-> None` as appropriate. These are the easiest fixes — usually one word.

---

## Fix strategy

Work module by module. After each module passes, commit it. Small commits make
rollback safe if a type fix inadvertently changes runtime behaviour.

```
1. tutor/models.py          → diagram_spec union type
2. tutor/exceptions.py      → verify (likely already correct)
3. tutor/constants.py       → verify
4. tutor/infra/llm.py       → LLMFn alias, return annotations
5. tutor/generation/        → adopt LLMFn in all signatures
6. tutor/visual/            → return annotations on compose_* and _run_ffmpeg
7. tutor/cli/               → ShellContext.player type
8. tutor/audio/             → verify
9. tutor/player/            → verify
10. tutor/qa/               → verify
```

### When to use `# type: ignore`

Use `# type: ignore[<code>]` only where mypy is provably wrong — for example,
when it cannot infer the type through a dynamic `json.loads()` call that you know
always returns a specific shape. Always include the error code so
`warn_unused_ignores` catches stale suppressions later.

---

## Developer workflow

```bash
# Run before opening a PR
mypy tutor/

# Check a single module while fixing
mypy tutor/models.py
mypy tutor/infra/llm.py
```

There is no CI enforcement. The expectation is: `mypy tutor/` passes clean
before a PR is opened. If it regresses, the developer who broke it fixes it.

---

## Acceptance criteria

- [ ] `[tool.mypy]` section with `strict = true` in `pyproject.toml`
- [ ] `[[tool.mypy.overrides]]` for `pygame.*`, `pydub.*`, `edge_tts.*`
- [ ] `types-Pillow` and `types-tqdm` in `[dev]` deps
- [ ] `mypy tutor/` exits with code 0 (no errors)
- [ ] No bare `# type: ignore` without an error code
- [ ] `VisualSpec.diagram_spec` typed as `str | dict | None`
- [ ] `ShellContext.player` typed as `TutorPlayer | None`
- [ ] `LLMFn` type alias defined in `infra/llm.py` and used across the pipeline
- [ ] All 115 existing tests still pass after type fixes (no runtime regression)
- [ ] mypy is **not** added to `.github/workflows/ci.yml`

## Verification

```bash
mypy tutor/        # must exit 0
pytest             # must pass all tests — type fixes must not break runtime
```
