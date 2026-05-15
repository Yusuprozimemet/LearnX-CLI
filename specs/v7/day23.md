# Day 23 (v7) — Config-Driven E2E Command, Review Script Path, and run_review.py --agents-dir

## Goal

Complete the generic dev loop by making the remaining two hardcoded paths
config-driven:

1. The E2E test command (`"python -m pytest tutor/tests/e2e/ -v"`) now comes from
   `devloop.toml [validation] e2e_tests`.
2. The review script path (`"scripts/run_review.py"`) now comes from
   `devloop.toml [review] review_script`.
3. `scripts/run_review.py` reads `devloop.toml` for `review.agents_dir` and accepts
   `--agents-dir` as a CLI override.

After this day, `learnx_dk.py` contains zero project-specific strings.

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
Modifies (existing):
  scripts/learnx_dk.py                   ← update _build_e2e_command() and
                                           run_implement() to use config values
  scripts/run_review.py                  ← load devloop.toml; add --agents-dir flag
  scripts/tests/test_learnx_dk.py        ← add 2 new tests for e2e config
  scripts/tests/test_review_agents.py    ← add 2 new tests for agents-dir config

Does NOT touch:
  devloop.toml          ← created in day1, unchanged here
  tutor/                ← application code unchanged
  .claude/agents/       ← unchanged
```

---

## Change 1 — Update `_build_e2e_command()` to accept inner command from config

### Current

```python
def _build_e2e_command(project_dir: pathlib.Path) -> list[str]:
    return [
        "docker", "run", "--rm",
        "-v", f"{_to_posix(project_dir)}:{WORKSPACE}",
        "-w", WORKSPACE,
        IMAGE,
        "python", "-m", "pytest", "tutor/tests/e2e/", "-v",
    ]
```

### New

```python
import shlex

def _build_e2e_command(
    project_dir: pathlib.Path,
    e2e_cmd: str = "python -m pytest tutor/tests/e2e/ -v",
    image: str = IMAGE,
    workspace: str = WORKSPACE,
) -> list[str]:
    """Build docker run command that runs e2e_cmd inside the container."""
    inner = shlex.split(e2e_cmd)
    return [
        "docker", "run", "--rm",
        "-v", f"{_to_posix(project_dir)}:{workspace}",
        "-w", workspace,
        image,
    ] + inner
```

`shlex.split()` is safe here — the command string comes from a trusted config file,
not user input. The default value preserves existing behaviour for any caller that
does not pass `e2e_cmd`.

---

## Change 2 — Update `run_implement()` to read e2e and review paths from config

`run_implement()` currently hardcodes `"scripts/run_review.py"` and calls
`_build_e2e_command(project_dir)` with no args. Add `config` as a parameter:

```python
def run_implement(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec: pathlib.Path | None,
    review: bool,
    extra_args: list[str],
    dry_run: bool,
    image: str = IMAGE,
    workspace: str = WORKSPACE,
    config: dict | None = None,     # ← new
) -> None:
    cfg = config or _DEFAULTS
    e2e_cmd = cfg["validation"]["e2e_tests"]
    review_script = cfg["review"]["review_script"]

    container_cmd = build_docker_command(project_dir, home_dir, extra_args,
                                         image=image, workspace=workspace)

    if dry_run:
        print("# Step 1 — container session")
        print(" ".join(container_cmd))
        if review:
            e2e_docker_cmd = _build_e2e_command(project_dir, e2e_cmd, image, workspace)
            rev_cmd = [_PY, review_script]
            if spec:
                rev_cmd += ["--spec", spec.as_posix()]
            print("# Step 2 — E2E smoke tests (inside container)")
            print(" ".join(e2e_docker_cmd))
            print("# Step 3 — review pipeline")
            print(" ".join(rev_cmd))
        return

    print("\n[implement] starting container session...")
    subprocess.run(container_cmd, check=False)

    if review:
        print("\n[implement] running E2E smoke tests...")
        e2e_result = subprocess.run(
            _build_e2e_command(project_dir, e2e_cmd, image, workspace), check=False
        )
        rev_cmd = [_PY, review_script]
        if spec:
            rev_cmd += ["--spec", spec.as_posix()]
        print("\n[implement] running review pipeline...")
        subprocess.run(rev_cmd, check=False)

        if e2e_result.returncode != 0:
            print("\n[implement] WARNING: E2E tests had failures — review findings carefully")
```

Update `main()` to pass `config` to `run_implement()`:

```python
run_implement(project_dir, home_dir, spec, review, extra, dry_run,
              image=image, workspace=workspace, config=config)
```

---

## Change 3 — Update `scripts/run_review.py` to load config and accept `--agents-dir`

### Add config loading

`run_review.py` currently imports `IMAGE`, `WORKSPACE`, `_to_posix`, `build_command`
from `learnx_dk`. Add `_load_config` to that import:

```python
from scripts.learnx_dk import _load_config, _to_posix, build_command  # noqa: E402
```

### Add `--agents-dir` to `main()`

```python
def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    dry_run = "--dry-run" in argv
    remaining = [a for a in argv if a != "--dry-run"]

    spec_path: pathlib.Path | None = None
    if "--spec" in remaining:
        idx = remaining.index("--spec")
        spec_path = pathlib.Path(remaining[idx + 1])
        remaining = remaining[:idx] + remaining[idx + 2:]

    agents_dir: str | None = None
    if "--agents-dir" in remaining:
        idx = remaining.index("--agents-dir")
        agents_dir = remaining[idx + 1]
        remaining = remaining[:idx] + remaining[idx + 2:]

    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()

    # Resolve agents_dir: CLI flag > devloop.toml > default
    if agents_dir is None:
        config = _load_config(project_dir)
        agents_dir = config["review"]["agents_dir"]

    cmd = build_review_command(project_dir, home_dir, spec_path, remaining,
                                agents_dir=agents_dir)

    if dry_run:
        print(" ".join(cmd))
        return

    subprocess.run(cmd, check=False)
```

### Update `build_review_command()` to accept `agents_dir`

```python
def build_review_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec_path: pathlib.Path | None,
    extra_args: list[str],
    agents_dir: str = ".claude/agents",   # ← new
) -> list[str]:
    ...
```

The `agents_dir` value is currently unused in the prompt (Claude Code auto-discovers
agents). Include it in the prompt as context so Claude knows where to look:

```python
agents_instruction = f"Review agents are in {agents_dir}/."

prompt = REVIEW_PROMPT_TEMPLATE.format(
    spec_instruction=spec_instruction,
    agents_instruction=agents_instruction,
).strip()
```

Update `REVIEW_PROMPT_TEMPLATE` to include `{agents_instruction}` in the header:

```python
REVIEW_PROMPT_TEMPLATE = """
You are running a pre-merge code review for the LearnX project.

Branch diff: run `git diff main...HEAD` to see all changes on this branch.
{spec_instruction}
{agents_instruction}

Launch the following four review agents IN PARALLEL using the Task tool:
...
"""
```

---

## New tests

### Add to `scripts/tests/test_learnx_dk.py`

```python
def test_build_e2e_command_uses_config_cmd(dirs):
    project, home = dirs
    cmd = _build_e2e_command(project, e2e_cmd="go test ./...", image="go-dev", workspace="/app")
    assert "go" in cmd
    assert "test" in cmd
    assert "./..." in cmd
    assert "go-dev" in cmd


def test_run_implement_review_dry_run_uses_config_review_script(dirs, capsys):
    project, home = dirs
    config = {
        "validation": {"e2e_tests": "python -m pytest tutor/tests/e2e/ -v"},
        "review": {"review_script": "scripts/custom_review.py"},
    }
    run_implement(project, home, spec=None, review=True,
                  extra_args=[], dry_run=True, config=config)
    out = capsys.readouterr().out
    assert "custom_review.py" in out
```

### Add to `scripts/tests/test_review_agents.py`

```python
from scripts.run_review import build_review_command


def test_build_review_command_accepts_custom_agents_dir(dirs):
    project, home = dirs
    cmd = build_review_command(project, home, spec_path=None, extra_args=[],
                               agents_dir="custom/agents")
    full = " ".join(cmd)
    assert "custom/agents" in full


def test_review_main_dry_run_accepts_agents_dir_flag(dirs, capsys):
    with patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]), \
         patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]), \
         patch("scripts.run_review.subprocess.run") as mock_run:
        main(["--agents-dir", "my/agents", "--dry-run"])
    out = capsys.readouterr().out
    assert "my/agents" in out
    mock_run.assert_not_called()
```

---

## Acceptance criteria

- [ ] `_build_e2e_command()` accepts `e2e_cmd`, `image`, and `workspace` keyword args
- [ ] `_build_e2e_command()` uses `shlex.split(e2e_cmd)` for the inner command
- [ ] Default `e2e_cmd` value matches the existing hardcoded command (no behavior change when unset)
- [ ] `run_implement()` accepts `config` keyword arg; reads `e2e_tests` and `review_script` from it
- [ ] `run_implement()` falls back to `_DEFAULTS` when `config` is `None`
- [ ] `run_implement()` dry-run with custom `review_script` shows the custom path
- [ ] `run_review.py` `main()` accepts `--agents-dir` CLI flag
- [ ] `run_review.py` reads `review.agents_dir` from `devloop.toml` when `--agents-dir` not given
- [ ] `build_review_command()` accepts `agents_dir` parameter and includes it in the prompt
- [ ] `learnx_dk.py` contains no hardcoded `"tutor/tests/e2e/"`, `"scripts/run_review.py"` strings
- [ ] `test_build_e2e_command_uses_config_cmd` passes
- [ ] `test_run_implement_review_dry_run_uses_config_review_script` passes
- [ ] `test_build_review_command_accepts_custom_agents_dir` passes
- [ ] `test_review_main_dry_run_accepts_agents_dir_flag` passes
- [ ] All pre-existing tests still pass
- [ ] ruff clean
