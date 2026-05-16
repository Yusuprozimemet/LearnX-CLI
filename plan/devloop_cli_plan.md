# DevLoop CLI — Design Plan

**Goal:** Turn DevLoop from a project-local script (`python scripts/devloop.py`) into a
proper globally-installed CLI tool (`devloop`) that works identically on Windows,
macOS, and Ubuntu. Control everything from the terminal.

---

## The Core Idea

DevLoop is already logically separate from LearnX. This plan makes that separation
real and gives it a proper CLI.

```
Before:  python scripts/devloop.py --spec specs/v11/day32.md --review
After:   devloop run specs/v11/day32.md --review
```

Install once, run from any project that has a `devloop.toml`.

---

## The Four Real Modes

These map directly to what the code already does, named clearly:

### 1. `explore` — Ask questions, read the codebase

Claude runs on the host machine with read-only permissions. No Docker. No code
changes possible. Use this when you want to understand something before writing a
spec.

```
devloop explore
devloop explore --dry-run
```

### 2. `run` — Implement one spec

Starts Claude inside a Docker container. You get an interactive session — paste the
handoff prompt, walk away. When Claude exits, optionally runs E2E tests and the
two-phase review pipeline automatically.

```
devloop run specs/v11/day32.md
devloop run specs/v11/day32.md --review
devloop run specs/v11/day32.md --review --dry-run
devloop run specs/v11/day32.md --model claude-opus-4-7
```

### 3. `version` — Run all specs in one version, unattended

Runs every spec in `specs/vN/` sequentially in its own Docker container.
Fully automated — no human interaction needed. Each spec gets its own sandbox
branch. Rate-limit retries, session/idle timeouts, dashboard, and notifications
are all handled automatically.

```
devloop version v11
devloop version v11 --review
devloop version v11 --review --serve              # live dashboard at localhost:8080
devloop version v11 --review --approve            # pause between specs, wait for ok
devloop version v11 --session-timeout 45 --idle-timeout 10
```

### 4. `build` — Zero to hero: run multiple versions in sequence  ← NEW

Runs multiple versions one after another. This is how you build an entire product
from scratch — write all your specs across versions, run `devloop build`, walk away.
Comes back when everything is done (or something fails).

```
devloop build v0 v1 v2 v3                        # run these versions in order
devloop build v0..v11                             # range syntax: all versions v0 to v11
devloop build v0..v11 --review                   # with review after each spec
devloop build v0..v11 --review --approve         # pause after each version, wait for ok
devloop build v0..v11 --from day5                # resume from a specific spec
```

---

## The `--approve` Flag

By default `version` and `build` run without stopping. Add `--approve` to pause
between specs (or between versions for `build`) and wait for your input before
continuing. This is useful when:

- You're in unknown territory and want to check each spec before the next one starts
- Something failed and you want to inspect before continuing
- You want to run the first few specs watched, then switch to unattended

```
devloop version v11 --approve

[version] -- spec: day30.md  branch: sandbox/v11-day30 --
... (Claude runs, exits) ...
[version] day30 DONE in 23 min

Continue to day31? [y/n/q]:
```

`y` = continue, `n` = skip this spec and continue, `q` = stop the run.

---

## Other Commands

### `review` — Run the review pipeline only

```
devloop review specs/v11/day32.md
devloop review specs/v11/day32.md --no-two-phase
devloop review specs/v11/day32.md --dry-run
```

### `init` — Scaffold a devloop.toml in a new project

```
devloop init              # creates devloop.toml with commented defaults
devloop init --force      # overwrite existing
```

### `status` — Show results of the last run

```
devloop status            # last run summary: which specs passed, failed, timed out
```

### `config` — Inspect and override config

```
devloop config                                    # show resolved config (all layers merged)
devloop config set resilience.idle_timeout_minutes 10
```

---

## Config Hierarchy

Three layers, resolved in priority order:

```
1. CLI flags                      --session-timeout 45
2. Project config                 devloop.toml  (current directory)
3. Global config                  ~/.config/devloop/config.toml
4. Built-in defaults              hardcoded in config.py
```

Global config lets you set defaults once for all projects — useful for notification
credentials, preferred timeouts, Docker image name.

```toml
# ~/.config/devloop/config.toml
[resilience]
session_timeout_minutes = 45
idle_timeout_minutes = 10

[notify]
telegram_token_env = "NOTIFY_TELEGRAM_TOKEN"
telegram_chat_id_env = "NOTIFY_TELEGRAM_CHAT_ID"
```

---

## Terminal Output

Current DevLoop prints raw `print()` text. After this plan:

- Coloured phase headers (running = green, review = cyan, failed = red, timed out = orange)
- In-place spec status table during `version` and `build` runs (updates without
  scrolling, even without `--serve`)
- Clear summary at the end of every run
- `--quiet` — suppress everything except the final summary
- `--json` — machine-readable output (useful for CI or piping to other tools)

Example of what a `version` run looks like in the terminal:

```
devloop version v11 --review

[v11] 3 specs found

  day30  ► running ...
  day31  waiting
  day32  waiting

[v11] day30 DONE (23 min)

  day30  ✓ DONE       23 min
  day31  ► running ...
  day32  waiting
```

---

## Cross-Platform

The three platforms differ in three places only:

| Concern | Windows | macOS | Ubuntu |
|---|---|---|---|
| Docker socket | TCP via Docker Desktop | `/var/run/docker.sock` | `/var/run/docker.sock` |
| Python executable | `python` | `python3` | `python3` |
| Forward slash in paths | Required — already enforced by `pathlib` | same | same |

DevLoop already uses `pathlib.Path` throughout, so paths work everywhere.
Docker is detected before any run — if Docker isn't running, you get a clear error
immediately instead of a silent hang.

Shell completion works on all three platforms via Typer's built-in support
(PowerShell, bash, zsh, fish).

---

## Internal Structure Change

```
devloop/                  ← new top-level Python package
  cli/
    main.py               ← Typer app, registers all commands
    run.py                ← devloop run
    version.py            ← devloop version
    build.py              ← devloop build  (new)
    explore.py            ← devloop explore
    review.py             ← devloop review
    init.py               ← devloop init
    config_cmd.py         ← devloop config
    status.py             ← devloop status
  core/                   ← was scripts/dk/ — zero logic changes
    config.py
    dashboard.py
    docker.py
    notifier.py
    process.py
    runners.py
```

`pyproject.toml` entry point:
```toml
[project.scripts]
devloop = "devloop.cli.main:app"
```

After `pipx install .`, `devloop` is on PATH on all platforms.

---

## What Stays the Same

- All existing `scripts/dk/` logic — moved to `devloop/core/`, zero rewrite
- `devloop.toml` format — fully backward compatible
- All 105 existing tests — import paths updated, logic unchanged
- Docker container workflow
- Two-phase review pipeline
- Dashboard (`--serve`)
- Telegram / webhook / script notifications
- Rate-limit retry and session/idle timeouts

---

## What's New

| Feature | Description |
|---|---|
| `devloop build` | Run multiple versions in sequence — zero to hero |
| `--approve` flag | Pause between specs/versions and wait for confirmation |
| In-place status table | Live terminal table without needing `--serve` |
| `devloop init` | Scaffold `devloop.toml` in any project |
| `devloop status` | Show last run results |
| `devloop config` | Inspect/set config from the terminal |
| Global config | `~/.config/devloop/config.toml` for machine-wide defaults |
| Docker check | Clear error if Docker isn't running before attempting anything |
| Shell completion | `devloop --install-completion` on all platforms |
| `--json` output | Machine-readable output for CI |

---

## Out of Scope for This Plan

- GUI / web UI (dashboard already covers this)
- Cloud sync of configs or results
- Multi-project management dashboard
- Plugin system
- Parallel spec execution (specs within a version still run sequentially)
