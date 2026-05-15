# Day 22 (v7) — devloop.toml and Config-Driven Image/Workspace/Specs

## Goal

Create `devloop.toml` at the project root and teach `learnx_dk.py` to read from it,
replacing the three hardcoded module-level constants (`IMAGE`, `WORKSPACE`, and the
`"specs"` directory name) with config-driven values.

After this day, running the launcher on a hypothetical different project only requires
a different `devloop.toml` — no changes to `learnx_dk.py`.

---

## Done (merge gate)

```powershell
py -m pytest scripts/tests/test_learnx_dk.py -v
py -m ruff check scripts/
py -m ruff format --check scripts/
```

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Creates (new):
  devloop.toml                        ← project-level config at repo root

Modifies (existing):
  scripts/learnx_dk.py                ← add _DEFAULTS, _load_config();
                                        update build_docker_command(),
                                        run_yolo_version(), main()
  scripts/tests/test_learnx_dk.py     ← add 4 new tests

Does NOT touch:
  scripts/run_review.py       ← updated in day2
  scripts/tests/test_review_agents.py ← updated in day2
  tutor/                      ← application code unchanged
  .claude/agents/             ← unchanged
  README.md / CLAUDE.md       ← unchanged
```

---

## Change 1 — Create `devloop.toml`

Full file content (place at repo root, next to `pyproject.toml`):

```toml
# devloop.toml — project config for the learnx_dk.py dev loop
# Edit this file to adapt the loop to a different project.

[project]
name = "LearnX"
docker_image = "learnx-dev"
specs_dir = "specs"
workspace = "/workspace"

[validation]
unit_tests = "python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -m 'not slow' -v"
e2e_tests = "python -m pytest tutor/tests/e2e/ -v"
lint = "python -m ruff check tutor/"
format_check = "python -m ruff format --check tutor/"

[review]
agents_dir = ".claude/agents"
review_script = "scripts/run_review.py"
```

---

## Change 2 — Add `_DEFAULTS` and `_load_config()` to `learnx_dk.py`

Add after the imports block, before the constants:

```python
import tomllib

_DEFAULTS: dict = {
    "project": {
        "name": "LearnX",
        "docker_image": "learnx-dev",
        "specs_dir": "specs",
        "workspace": "/workspace",
    },
    "validation": {
        "unit_tests": "python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -m 'not slow' -v",
        "e2e_tests": "python -m pytest tutor/tests/e2e/ -v",
        "lint": "python -m ruff check tutor/",
        "format_check": "python -m ruff format --check tutor/",
    },
    "review": {
        "agents_dir": ".claude/agents",
        "review_script": "scripts/run_review.py",
    },
}


def _load_config(project_dir: pathlib.Path) -> dict:
    """Load devloop.toml from project_dir; fall back to _DEFAULTS if absent."""
    config_path = project_dir / "devloop.toml"
    if not config_path.exists():
        return _DEFAULTS
    with open(config_path, "rb") as fh:
        raw = tomllib.load(fh)
    # Merge section-by-section so missing keys get defaults
    config: dict = {}
    for section, defaults in _DEFAULTS.items():
        config[section] = {**defaults, **raw.get(section, {})}
    return config
```

`tomllib` is in the Python 3.11+ standard library. No new dependency required.

---

## Change 3 — Update `build_docker_command()` to accept image and workspace

Add `image` and `workspace` as keyword parameters with the existing constants as
defaults. This keeps all existing tests working without changes.

```python
def build_docker_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
    image: str = IMAGE,
    workspace: str = WORKSPACE,
) -> list[str]:
    ...
    # Replace the hardcoded IMAGE and WORKSPACE references inside the body
    # with the image and workspace parameters.
    cmd = [
        "docker", "run", "--rm", "-it",
        "-v", f"{_to_posix(project_dir)}:{workspace}",
    ]
    ...
    cmd += ["-w", workspace, image]
    ...
```

Update `build_command()` (the backwards-compat alias) to forward the new params:

```python
def build_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
    image: str = IMAGE,
    workspace: str = WORKSPACE,
) -> list[str]:
    return build_docker_command(project_dir, home_dir, extra_args, image, workspace)
```

---

## Change 4 — Update `run_yolo_version()` to accept `specs_dir`

Add `specs_dir: str = "specs"` parameter. Replace the hardcoded `project_dir / "specs"`:

```python
def run_yolo_version(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    version: str,
    review: bool,
    extra_args: list[str],
    dry_run: bool,
    specs_dir: str = "specs",    # ← new parameter
) -> None:
    version_dir = project_dir / specs_dir   # was: project_dir / "specs"
    specs = _discover_specs(version_dir.parent, version)
    ...
```

Wait — `_discover_specs(specs_dir, version)` takes the parent `specs/` path and the
version string. Pass `project_dir / specs_dir` as the base:

```python
specs = _discover_specs(project_dir / specs_dir, version)
```

Update `_discover_specs()` signature to accept a `pathlib.Path` directly (it already
takes `specs_dir: pathlib.Path` — confirm this is consistent with the v5 implementation).

---

## Change 5 — Update `main()` to load config and pass values

```python
def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    explore, review, dry_run, spec, version, extra = _parse(argv)
    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()
    config = _load_config(project_dir)                # ← load config

    proj = config["project"]
    image = proj["docker_image"]
    workspace = proj["workspace"]
    specs_dir = proj["specs_dir"]

    if explore:
        run_explore(extra, dry_run)
        return

    if version:
        run_yolo_version(
            project_dir, home_dir, version, review, extra, dry_run,
            specs_dir=specs_dir,
        )
        return

    run_implement(project_dir, home_dir, spec, review, extra, dry_run,
                  image=image, workspace=workspace)
```

Update `run_implement()` to accept and forward `image` and `workspace` to
`build_docker_command()` and `_build_e2e_command()` (the e2e command comes in
day2 — for now just pass them through to `build_docker_command()`):

```python
def run_implement(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec: pathlib.Path | None,
    review: bool,
    extra_args: list[str],
    dry_run: bool,
    image: str = IMAGE,         # ← new
    workspace: str = WORKSPACE, # ← new
) -> None:
    container_cmd = build_docker_command(project_dir, home_dir, extra_args,
                                         image=image, workspace=workspace)
    ...
```

---

## New tests — add to `scripts/tests/test_learnx_dk.py`

```python
import tomllib  # Python 3.11+ stdlib

from scripts.learnx_dk import _DEFAULTS, _load_config


def test_load_config_returns_defaults_when_toml_missing(tmp_path):
    config = _load_config(tmp_path)   # tmp_path has no devloop.toml
    assert config["project"]["docker_image"] == "learnx-dev"
    assert config["project"]["workspace"] == "/workspace"
    assert config["review"]["review_script"] == "scripts/run_review.py"


def test_load_config_reads_docker_image_from_toml(tmp_path):
    (tmp_path / "devloop.toml").write_text(
        '[project]\ndocker_image = "custom-image"\n'
    )
    config = _load_config(tmp_path)
    assert config["project"]["docker_image"] == "custom-image"


def test_load_config_merges_missing_keys_with_defaults(tmp_path):
    # Only override docker_image; workspace should still come from defaults.
    (tmp_path / "devloop.toml").write_text(
        '[project]\ndocker_image = "custom-image"\n'
    )
    config = _load_config(tmp_path)
    assert config["project"]["workspace"] == "/workspace"


def test_build_docker_command_uses_custom_image(dirs):
    project, home = dirs
    cmd = build_docker_command(project, home, extra_args=[], image="my-img", workspace="/app")
    assert "my-img" in cmd
    mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
    assert any("/app" in m for m in mounts)
```

---

## Acceptance criteria

- [ ] `devloop.toml` exists at project root with `[project]`, `[validation]`, `[review]` sections
- [ ] `_load_config()` returns `_DEFAULTS` when `devloop.toml` is absent
- [ ] `_load_config()` reads `docker_image` from `[project]` when file is present
- [ ] Missing keys in `devloop.toml` are filled from `_DEFAULTS` (merge, not replace)
- [ ] `build_docker_command()` uses the `image` kwarg when provided
- [ ] `build_docker_command()` uses the `workspace` kwarg in the `-v` mount and `-w` flag
- [ ] `run_yolo_version()` accepts `specs_dir` kwarg; uses it instead of hardcoded `"specs"`
- [ ] `main()` calls `_load_config(project_dir)` and passes `image`, `workspace`, `specs_dir` to callers
- [ ] All existing tests still pass — the new keyword params have defaults matching old constants
- [ ] `test_load_config_returns_defaults_when_toml_missing` passes
- [ ] `test_load_config_reads_docker_image_from_toml` passes
- [ ] `test_load_config_merges_missing_keys_with_defaults` passes
- [ ] `test_build_docker_command_uses_custom_image` passes
- [ ] ruff clean
