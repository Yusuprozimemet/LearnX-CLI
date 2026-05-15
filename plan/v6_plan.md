# LearnX v6 — Docker as Default

## The problem with v5

v5 (and v4 before it) treats Docker as a special mode:

```powershell
python scripts/learnx_dk.py                         # supervised (host, default)
python scripts/learnx_dk.py --mode container         # Docker, one spec
python scripts/learnx_dk.py --mode yolo --spec ...   # Docker, one spec + review
```

This design implies that running on the host is normal and Docker is the upgrade.
But Docker is not an upgrade — it is the only correct environment for code changes.
The host has no reproducibility guarantee: different Python version, different PATH,
different OS state. Code that passes tests on the host may fail in CI.

The 4-mode design also causes confusion:
- `supervised` = host, frequent prompts
- `assisted` = host, rare prompts
- `container` = Docker, zero prompts
- `yolo` = Docker + review

Why would you ever write code on the host? The supervised/assisted distinction
made sense before Docker was the default. Now it is just noise.

---

## The redesign

Docker is the default. Always. For any code task.

```powershell
python scripts/learnx_dk.py --spec specs/v5/day1.md          # implement, Docker
python scripts/learnx_dk.py --mode yolo --version v5          # full version run, Docker
python scripts/learnx_dk.py --explore                         # host, read-only, questions only
```

### Modes collapse to two

| Mode | Where | Use when |
|---|---|---|
| `implement` (default) | Docker | writing code, any spec |
| `explore` | Host | asking questions, reading code, exploring — no code changes |

The `supervised`, `assisted`, `container` modes are retired. The `yolo` flag is
kept as a modifier for version-level execution, not a mode.

### Default behavior

Running without flags opens an implement session in Docker:

```powershell
python scripts/learnx_dk.py
```

This is equivalent to the old `--mode container`. Docker starts, Claude opens,
you interact. No prompts blocked, no prompts forced — Claude uses its own judgment.

### Explore mode

When you want to ask questions without risking any code changes:

```powershell
python scripts/learnx_dk.py --explore
```

Runs Claude on the host, read-only tool permissions. No Docker required.
Useful for: "explain this function", "what does this test do", "how does X work".

### Yolo as a modifier, not a mode

```powershell
# implement one spec, Docker, no review
python scripts/learnx_dk.py --spec specs/v5/day1.md

# implement one spec, Docker, with review
python scripts/learnx_dk.py --spec specs/v5/day1.md --review

# implement entire version, Docker, with review, all specs
python scripts/learnx_dk.py --version v5 --review
```

`--review` triggers the 5-agent review + report after implementation.
`--version` triggers multi-spec execution (v5 feature).
`--spec` runs a single spec.

---

## Migration

| Old command | New command |
|---|---|
| `learnx_dk.py` | `learnx_dk.py --explore` |
| `learnx_dk.py --mode assisted` | `learnx_dk.py --explore` |
| `learnx_dk.py --mode container` | `learnx_dk.py` (new default) |
| `learnx_dk.py --mode yolo --spec X` | `learnx_dk.py --spec X --review` |
| `learnx_dk.py --mode yolo --spec X --dry-run` | `learnx_dk.py --spec X --dry-run` |

---

## What changes

| Component | Change |
|---|---|
| `scripts/learnx_dk.py` | Remove `supervised`, `assisted`, `container` mode names |
| `scripts/learnx_dk.py` | Docker is default; `--explore` runs on host |
| `scripts/learnx_dk.py` | `--review` flag replaces `--mode yolo` |
| `scripts/learnx_dk.py` | `--version` flag for multi-spec execution |
| `README.md` | Update quick start and mode table |
| `CLAUDE.md` | Update commands reference |

---

## What does not change

- Docker image and container setup unchanged
- Review pipeline unchanged
- Branch strategy unchanged
- Spec format unchanged
