# LearnX v12 — Visual Quality Upgrade

## The problem with v3 visual quality

v3 solved the _structural_ problems with the video pipeline: Playwright replaces
Pillow, Jinja2 templates replace hardcoded pixel coordinates, Mermaid renders
real diagrams. The architecture is correct.

The _visual quality_ is still weak. Three specific failures:

**Failure 1 — System fonts.** `slide_base.css` uses `"Segoe UI"` for body and
`"Cascadia Code"` for code. System fonts vary by machine, have no visual character,
and look like a developer prototype. Every professional educational video platform
uses custom web fonts: Coursera uses Source Sans, 3Blue1Brown uses CMU, Lumen5
uses Inter. LearnX has no font identity.

**Failure 2 — Flat design.** Every slide looks the same: dark background, thin
border, no depth. There is no visual distinction between a `definition` slide, a
`key_insight` slide, and a `memory_hook` slide. A learner cannot glance at the
screen and know what kind of content is being presented. This is not a matter of
taste — it is a functional failure of the slide-type system.

**Failure 3 — Thin prompt output.** The `visual_v3.txt` prompt produces adequate
but conservative segments. It has no guidance for two common narrative patterns —
multi-step processes and highlighted callouts — so the LLM forces them into
`definition` or `key_insight` where they fit poorly. Slide variety is lower than it
should be.

---

## What we borrow from presentation-ai

`presentation-ai` (downloaded to `presentation-ai/`) is a full-stack Next.js web
app — we cannot import its code. But it contains two directly extractable assets:

### 1. CSS design patterns (`src/lib/presentation/themes.ts`)

The theme system defines a coherent set of design decisions we can lift directly:

- **Per-type accent colours** — different slide types get different accent colours.
  This is the key visual distinction that makes each slide immediately identifiable.
- **Left accent border on content cards** — a 4px left border in the type's accent
  colour gives every content block a clear visual anchor.
- **Subtle radial gradient background** — a faint glow derived from the type accent
  colour in the top-right corner. Used in presentation-ai's professional themes.
- **Card elevation** — `box-shadow: 0 4px 24px rgba(0,0,0,.4)` with a 1px border
  instead of a flat border. Adds depth without a flat look.

### 2. Typography (Inter + JetBrains Mono)

presentation-ai uses Inter as the primary UI font (one of its defaults across
multiple themes) and JetBrains Mono for code. Both are open-source, free to
redistribute, and designed for screen reading at large sizes. Committing the woff2
files to `tutor/assets/html/fonts/` and referencing them via `@font-face` gives
LearnX slides immediate typographic quality.

---

## The four changes

### Day 1 — Font bundle + CSS token overhaul
Commit Inter (Regular/SemiBold/Bold) and JetBrains Mono (Regular) woff2 files to
`tutor/assets/html/fonts/`. Rewrite `slide_base.css` with:
- `@font-face` declarations for both families
- Extended token set: surface levels, border tiers, full accent palette, `--type-accent` variable
- Per-slide-type CSS improvements using the new tokens
- Two new slide-type classes: `.step-slide` and `.callout-slide`

Zero Python changes. The visual improvement is immediate for any session that
re-runs `/video`.

### Day 2 — Template upgrades
Update `_base.html.j2` to support `{% block extra_style %}`. Update all 12 content
templates to set `--type-accent` to their assigned accent colour via
`{% block extra_style %}`. Add two new templates:
- `step_sequence.html.j2` — numbered steps from `seg.body` (newline-separated)
- `callout.html.j2` — highlighted callout box for warnings, tips, and key quotes

All changes are in `tutor/visual/templates/`. No Python files touched.

### Day 3 — Visual planner prompt upgrade
Rewrite `tutor/prompts/visual_v3.txt` with:
- `step_sequence` type (numbered process steps — when ALEX explains "first… then… finally…")
- `callout` type (highlighted tip/warning/quote — for single important statements)
- Sharper assignment rules for all 12 types
- Guidance to aim for higher slide diversity (discourage over-use of `definition`)

Update `tutor/generation/segment_planner.py` to add the two new types to the valid
type set. Add tests for the new type handling.

### Day 4 — Playwright rendering hardening
Fix the three silent failure modes in `tutor/visual/slide_renderer.py`:
- Mermaid timeout swallowed by `except Exception: pass` — replace with logged
  warning + fallback to `key_insight` slide with diagram description as body
- Screenshot produced without verifying it is non-empty — add file-size assertion
- No retry on transient page navigation failure — add one retry before raising

---

## What does not change

| Component | Status |
|---|---|
| `tutor/visual/video_assembler.py` | UNCHANGED |
| `tutor/visual/beat_timer.py` | UNCHANGED |
| `tutor/visual/subtitle_writer.py` | UNCHANGED |
| `tutor/visual/__init__.py` | UNCHANGED |
| `tutor/generation/visual_planner.py` | UNCHANGED |
| `tutor/generation/segment_planner.py` | Day 3 only: add 2 types to valid set |
| `tutor/models.py` | UNCHANGED — no new dataclass fields |
| `tutor/audio/` | UNCHANGED |
| `tutor/cli/` | UNCHANGED |
| ffmpeg commands | UNCHANGED |
| Pipeline step order (1/6 … 6/6) | UNCHANGED |

`video_assembler.py` receives `(png_path, duration_s)` tuples regardless of how
the PNGs look. Visual quality changes are fully contained in the templates and CSS.

---

## Expected outcome

After v12, a LearnX video slide has:
- Inter typeface — clean, readable at 64px headlines and 34px body text
- JetBrains Mono for all code blocks — professional mono with ligatures
- Per-type accent colour — `definition` slides are blue, `key_insight` are pink,
  `memory_hook` are rose. A learner glancing at the screen knows what they are seeing
- Left accent border on content cards — immediate visual depth without complex layout
- Subtle radial glow — matches the slide type's colour, gives each slide a sense of
  identity without being distracting
- 12 slide types (was 10) — `step_sequence` and `callout` capture patterns that
  previously produced awkward `definition` or `key_insight` mismatches

No architecture change. No new Python dependencies. No pipeline restructuring.
