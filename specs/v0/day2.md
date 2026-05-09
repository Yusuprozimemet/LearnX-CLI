# Day 2 — Type Safety

## Goal

Configure mypy and fix all type errors so the existing type annotations actually
enforce correctness. After this day, `mypy tutor/` passes clean and a third CI
job blocks any future type errors from merging.

Type hints already exist throughout the codebase — they document intent but
are not verified. This day converts them from documentation into enforcement.

---

## mypy configuration — `pyproject.toml`

Add `[tool.mypy]` to `pyproject.toml` (Day 0 is a prerequisite):

```toml
[tool.mypy]
python_version     = "3.11"
strict             = true
warn_unused_ignores = true
exclude            = ["tutor/tests/"]
```

**`strict = true`** enables:
- `disallow_untyped_defs` — every function must have full annotations
- `disallow_any_generics` — `list` must be `list[str]`, not bare `list`
- `warn_return_any` — functions returning `Any` are flagged
- `no_implicit_optional` — `def f(x: str = None)` is an error
- And more

**`warn_unused_ignores = true`** — removes stale `# type: ignore` comments that
accumulate over time.

**`exclude = ["tutor/tests/"]`** — tests use `assert`, `MagicMock`, and other
patterns that generate noise under strict mode. Tests still run through mypy's
non-strict pass via the CI job, but strict violations there are not required to fix.

---

## Known type issues to resolve

Running `mypy tutor/` with strict settings will surface errors in specific patterns.
Fix them module by module in this order — start with the shared models and work outward.

### 1. `tutor/models.py` — `object` field type

```python
# Current — too broad
diagram_spec: object = None   # str (DOT) | dict | None
```

```python
# Fix — precise union
diagram_spec: str | dict | None = None
```

### 2. `tutor/cli/commands.py` — `ShellContext.player` untyped

```python
# Current — erases all player method types
player: object = None
```

```python
# Fix — use the actual type with a forward reference
from __future__ import annotations
from tutor.player.player import TutorPlayer

@dataclass
class ShellContext:
    player: TutorPlayer | None = None
    ...
```

If importing `TutorPlayer` creates a circular import, use `TYPE_CHECKING`:

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tutor.player.player import TutorPlayer

@dataclass
class ShellContext:
    player: TutorPlayer | None = None
```

### 3. `tutor/infra/llm.py` — LLM response typed as `Any`

The LLM client returns `str`. Functions that call `llm_fn` pass it as
`Callable[..., Any]` or `Callable`. Fix with a precise callable type alias:

```python
from typing import TypeAlias

LLMFn: TypeAlias = Callable[[list[dict[str, str]], str], str]
```

Use `LLMFn` in all function signatures that accept `llm_fn`.

### 4. `tutor/visual/` — missing return type annotations

Some `compose_*` functions and `_run_ffmpeg` lack return annotations.
Add `-> Path` or `-> None` as appropriate.

### 5. Third-party stub packages

pygame, Pillow, tqdm, and pydub do not ship inline types. Install stubs:

```
pip install types-Pillow types-tqdm
```

These are already in the `[dev]` dependencies (Day 0). For packages without
published stubs (pygame, pydub, edge-tts), add per-module ignores in `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["pygame.*", "pydub.*", "edge_tts.*"]
ignore_missing_imports = true
```

Do not use `# type: ignore` inline for missing stubs — the `overrides` section is
the correct mechanism and does not suppress other errors in those call sites.

---

## Fix strategy

Do not attempt to fix all errors at once. Work module by module:

```
1. tutor/models.py          → fix VisualSpec.diagram_spec type
2. tutor/exceptions.py      → likely already correct, verify
3. tutor/constants.py       → likely already correct, verify
4. tutor/infra/llm.py       → add LLMFn type alias, fix return types
5. tutor/generation/        → update function signatures to use LLMFn
6. tutor/visual/            → add missing return annotations
7. tutor/cli/               → fix ShellContext.player type
8. tutor/audio/             → verify (already well-typed)
9. tutor/player/            → verify
10. tutor/qa/               → verify
```

After each module passes, commit it. Small commits make rollback easier if a fix
introduces a runtime regression.

### Allowed `# type: ignore`

Use `# type: ignore[<code>]` only where mypy is provably wrong:
- A `cast()` that mypy cannot infer through a dynamic JSON load
- A third-party function that returns `Any` despite actually returning a known type

Every `# type: ignore` must include the error code (e.g. `# type: ignore[attr-defined]`)
so `warn_unused_ignores` catches stale ones later.

---

## CI job — add `typecheck` to `.github/workflows/ci.yml`

Add a third job after `lint` and `test`:

```yaml
  typecheck:
    name: Type check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run mypy
        run: mypy tutor/
```

This job runs in parallel with `lint` and `test`. Add it only after `mypy tutor/`
passes locally — adding it before will fail every CI run until errors are fixed.

---

## Acceptance criteria

- [ ] `[tool.mypy]` section with `strict = true` present in `pyproject.toml`
- [ ] `[[tool.mypy.overrides]]` for `pygame.*`, `pydub.*`, `edge_tts.*`
- [ ] `mypy tutor/` exits with code 0 (zero errors)
- [ ] No bare `# type: ignore` without an error code
- [ ] `VisualSpec.diagram_spec` typed as `str | dict | None` (not `object`)
- [ ] `ShellContext.player` typed as `TutorPlayer | None` (not `object`)
- [ ] `LLMFn` type alias used consistently across `generation/` and `infra/`
- [ ] `typecheck` job added to `.github/workflows/ci.yml`
- [ ] All 115 existing tests still pass after type fixes (no runtime regression)
- [ ] `pyproject.toml` contains `types-Pillow` and `types-tqdm` in `[dev]` deps

## Verification commands

```bash
mypy tutor/                   # must exit 0
pytest                        # must still pass all tests
mypy --strict tutor/models.py # spot-check key module
```
