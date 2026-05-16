# Day 1 (v12) — Font Bundle + CSS Token Overhaul

## Goal

Commit Inter and JetBrains Mono woff2 files to `tutor/assets/html/fonts/`.
Rewrite `slide_base.css` with the full v12 token system: web fonts, per-type accent
colours, card elevation, gradient backgrounds, and two new slide-type classes
(`step_sequence`, `callout`). Zero Python changes — all existing templates keep
working via CSS alias tokens.

---

## Done (merge gate)

```powershell
py -m pytest tutor/tests/ -v -k "visual or slide"
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Additionally verify manually by running the pipeline on any existing session:
the slides directory must contain PNG files with Inter text visible (not Segoe UI).

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Creates (new):
  tutor/assets/html/fonts/           ← new directory
  tutor/assets/html/fonts/Inter-Regular.woff2
  tutor/assets/html/fonts/Inter-SemiBold.woff2
  tutor/assets/html/fonts/Inter-Bold.woff2
  tutor/assets/html/fonts/JetBrainsMono-Regular.woff2

Modifies (existing):
  tutor/assets/html/slide_base.css   ← full rewrite

Does NOT touch:
  tutor/assets/html/theme-learnx-dark.css   ← unchanged
  tutor/assets/html/mermaid.min.js           ← unchanged
  tutor/assets/html/highlight*.js            ← unchanged
  tutor/visual/templates/                    ← unchanged (Day 2)
  tutor/visual/slide_renderer.py             ← unchanged
  tutor/**/*.py                              ← unchanged
```

---

## Change 1 — Download and commit font files

Download the four woff2 files from their official open-source releases and place
them at `tutor/assets/html/fonts/`:

**Inter** (SIL Open Font Licence 1.1):
- Release: https://github.com/rsms/inter/releases/tag/v4.0
- Download `Inter-4.0.zip`, unzip, take from `extras/woff2/`:
  - `Inter-Regular.woff2`   (weight 400, ~96 KB)
  - `Inter-SemiBold.woff2`  (weight 600, ~97 KB)
  - `Inter-Bold.woff2`      (weight 700, ~97 KB)

**JetBrains Mono** (Apache 2.0 Licence):
- Release: https://github.com/JetBrains/JetBrainsMono/releases/tag/v2.304
- Download `JetBrainsMono-2.304.zip`, unzip, take from `fonts/webfonts/`:
  - `JetBrainsMono-Regular.woff2`  (weight 400, ~80 KB)

The target directory after this step:

```
tutor/assets/html/fonts/
  Inter-Regular.woff2
  Inter-SemiBold.woff2
  Inter-Bold.woff2
  JetBrainsMono-Regular.woff2
```

Commit these binary files to git. Each is under 100 KB; the total addition is
~370 KB, well within acceptable limits for committed assets.

---

## Change 2 — Rewrite `tutor/assets/html/slide_base.css`

Replace the entire file with the following. Every existing CSS class is retained or
improved; no class is removed. Legacy alias tokens (`--accent-cyn`, `--accent-amb`,
`--accent-grn`, `--divider`) ensure existing templates continue to work until Day 2.

```css
/* ============================================================
   LearnX Slide Base — v12
   Typography: Inter (UI) + JetBrains Mono (code)
   Design: per-type accent system adapted from presentation-ai
   ============================================================ */

/* ── Web Fonts ──────────────────────────────────────────── */

@font-face {
  font-family: "Inter";
  src: url("fonts/Inter-Regular.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
  font-display: block;
}
@font-face {
  font-family: "Inter";
  src: url("fonts/Inter-SemiBold.woff2") format("woff2");
  font-weight: 600;
  font-style: normal;
  font-display: block;
}
@font-face {
  font-family: "Inter";
  src: url("fonts/Inter-Bold.woff2") format("woff2");
  font-weight: 700;
  font-style: normal;
  font-display: block;
}
@font-face {
  font-family: "JetBrains Mono";
  src: url("fonts/JetBrainsMono-Regular.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
  font-display: block;
}

/* ── Design Tokens ──────────────────────────────────────── */

:root {
  /* Surfaces */
  --bg-deep:      #0d1117;
  --bg-card:      #161b22;
  --bg-elevated:  #1c2128;
  --bg-overlay:   rgba(255,255,255,.04);

  /* Borders */
  --border-soft:   #21262d;
  --border-mid:    #30363d;
  --border-strong: #484f58;

  /* Text */
  --text-pri:  #e6edf3;
  --text-sec:  #8b949e;
  --text-dim:  #656d76;

  /* Full accent palette */
  --cyan:   #22d3ee;
  --blue:   #60a5fa;
  --purple: #c084fc;
  --teal:   #2dd4bf;
  --green:  #4ade80;
  --amber:  #fbbf24;
  --orange: #fb923c;
  --pink:   #f472b6;
  --rose:   #fb7185;
  --sky:    #38bdf8;
  --indigo: #818cf8;

  /*
   * Per-slide-type accent — each template overrides this via:
   *   {% block extra_style %}:root { --type-accent: var(--blue); }{% endblock %}
   * Default (cyan) applies when no template overrides it.
   */
  --type-accent: var(--cyan);

  /* Typography */
  --font-ui:   "Inter", system-ui, "Helvetica Neue", Arial, sans-serif;
  --font-mono: "JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace;

  /* Legacy aliases — keep existing templates working until Day 2 */
  --accent-cyn: var(--cyan);
  --accent-amb: var(--amber);
  --accent-grn: var(--green);
  --divider:    var(--border-mid);
  --font-ui-legacy: var(--font-ui);
  --font-mono-legacy: var(--font-mono);
}

/* ── Reset + Base ───────────────────────────────────────── */

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  width: 1920px;
  height: 1080px;
  overflow: hidden;
  background: var(--bg-deep);
  color: var(--text-pri);
  font-family: var(--font-ui);
  /*
   * Subtle per-type accent glow — top-right corner.
   * Inspired by presentation-ai professional themes.
   * Uses color-mix() (Chromium 111+, compatible with Playwright).
   */
  background-image: radial-gradient(
    ellipse 900px 600px at 96% 4%,
    color-mix(in srgb, var(--type-accent) 7%, transparent) 0%,
    transparent 70%
  );
}

/* ── Chrome Layout ──────────────────────────────────────── */

.top-bar {
  height: 60px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-soft);
  display: flex;
  align-items: center;
  padding: 0 48px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-sec);
  gap: 16px;
}

.footer-bar {
  position: absolute;
  bottom: 0;
  height: 56px;
  width: 100%;
  background: var(--bg-card);
  border-top: 1px solid var(--border-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.content {
  position: absolute;
  top: 60px;
  bottom: 56px;
  left: 80px;
  right: 80px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

/* ── Progress Dots ──────────────────────────────────────── */

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.dot--filled { background: var(--type-accent); }
.dot--hollow { background: transparent; border: 1.5px solid var(--border-strong); }

/* ── Shared Helpers ─────────────────────────────────────── */

/*
 * Card — elevated content container with left accent border.
 * Adapted from presentation-ai's card pattern.
 */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  border-left: 4px solid var(--type-accent);
  border-radius: 0 12px 12px 0;
  padding: 40px 48px;
  box-shadow: 0 4px 24px rgba(0,0,0,.4);
}

/* Small coloured pill — slide type label */
.type-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 20px;
  border-radius: 24px;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  background: var(--type-accent);
  color: #0d1117;
}

/* ── hook_question ──────────────────────────────────────── */

.hook-slide { display: flex; flex-direction: column; gap: 40px; }
.hook-question {
  font-size: 68px;
  font-weight: 700;
  color: var(--text-pri);
  line-height: 1.2;
  max-width: 1520px;
}
.learn-label {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: .10em;
  text-transform: uppercase;
  color: var(--type-accent);
  margin-bottom: 16px;
}
.learn-list {
  font-size: 34px;
  color: var(--text-sec);
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.learn-list li::before { content: "→  "; color: var(--type-accent); font-weight: 700; }

/* ── definition ─────────────────────────────────────────── */

.definition-slide { display: flex; flex-direction: column; gap: 32px; }
.definition-term {
  font-size: 60px;
  font-weight: 700;
  color: var(--type-accent);
}
.definition-text {
  font-size: 36px;
  color: var(--text-pri);
  line-height: 1.55;
  max-width: 1440px;
}

/* ── analogy ────────────────────────────────────────────── */

.analogy-slide {
  display: grid;
  grid-template-columns: 1fr 72px 1fr;
  align-items: stretch;
  gap: 32px;
  height: 100%;
}
.analogy-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-soft);
  border-top: 3px solid var(--type-accent);
  border-radius: 12px;
  padding: 40px 48px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  box-shadow: 0 4px 20px rgba(0,0,0,.35);
}
.analogy-label {
  font-size: 22px;
  font-weight: 700;
  color: var(--type-accent);
  text-transform: uppercase;
  letter-spacing: .06em;
}
.analogy-body  { font-size: 34px; color: var(--text-pri); line-height: 1.5; }
.analogy-sep   { font-size: 80px; color: var(--type-accent); text-align: center; align-self: center; opacity: .8; }

/* ── comparison / decision_guide ────────────────────────── */

.comparison-slide { width: 100%; }
.comparison-table { width: 100%; border-collapse: collapse; font-size: 32px; }
.comparison-table th {
  padding: 20px 36px;
  font-weight: 700;
  font-size: 36px;
  border-bottom: 2px solid var(--border-mid);
}
.comparison-table td { padding: 16px 36px; border-top: 1px solid var(--border-soft); }
.comparison-table tr:nth-child(even) td { background: var(--bg-card); }
.comparison-table tr:nth-child(odd)  td { background: var(--bg-deep); }
.th-left  { color: var(--type-accent); text-align: left; }
.th-right { color: var(--orange);      text-align: left; }
.td-ellipsis { text-align: center; color: var(--text-sec); font-size: 28px; }

/* ── code_example ───────────────────────────────────────── */

.code-slide { display: flex; flex-direction: column; gap: 24px; }
.code-desc  { font-size: 32px; color: var(--text-sec); }
.code-slide pre {
  font-family: var(--font-mono);
  font-size: 26px;
  line-height: 1.65;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border-soft);
  box-shadow: 0 2px 16px rgba(0,0,0,.5);
}

/* ── diagram ────────────────────────────────────────────── */

.diagram-slide {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
.diagram-slide .mermaid { font-size: 26px; }

/* ── question_prompt ────────────────────────────────────── */

.question-slide {
  position: absolute;
  inset: 0;
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  background-image: radial-gradient(
    ellipse 800px 500px at 50% 50%,
    color-mix(in srgb, var(--type-accent) 5%, transparent) 0%,
    transparent 70%
  );
}
.question-text {
  font-size: 56px;
  font-weight: 600;
  color: var(--text-pri);
  text-align: center;
  max-width: 1400px;
  line-height: 1.4;
}
.speaker-badge {
  position: absolute;
  top: 80px;
  right: 80px;
  padding: 10px 32px;
  border-radius: 32px;
  font-size: 26px;
  font-weight: 700;
  color: #0d1117;
}
.badge-maya { background: var(--green); }
.badge-sam  { background: var(--amber); }

/* ── key_insight ────────────────────────────────────────── */

.key-insight-slide {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 32px;
}
.key-insight-text {
  font-size: 64px;
  font-weight: 700;
  color: var(--text-pri);
  text-align: center;
  max-width: 1400px;
  line-height: 1.35;
}
.key-insight-rule { width: 500px; height: 3px; background: var(--type-accent); }

/* ── memory_hook ────────────────────────────────────────── */

.memory-hook-slide {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
.memory-hook-text {
  font-size: 56px;
  font-weight: 500;
  color: var(--text-pri);
  text-align: center;
  max-width: 1400px;
  line-height: 1.45;
}

/* ── title_card ─────────────────────────────────────────── */

.title-card-slide {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 32px;
}
.title-card-title {
  font-size: 88px;
  font-weight: 700;
  color: var(--text-pri);
  text-align: center;
  line-height: 1.15;
}
.title-card-sub  { font-size: 40px; color: var(--text-sec); text-align: center; }
.title-card-accent {
  width: 200px;
  height: 4px;
  background: linear-gradient(90deg, var(--cyan), var(--blue));
  border-radius: 2px;
}

/* ── outro ──────────────────────────────────────────────── */

.outro-slide {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 32px;
}
.outro-text { font-size: 68px; font-weight: 700; color: var(--text-pri); text-align: center; }
.outro-sub  { font-size: 36px; color: var(--text-sec); text-align: center; }

/* ── step_sequence (new — v12) ──────────────────────────── */

.step-slide { display: flex; flex-direction: column; gap: 28px; }
.step-item  { display: flex; align-items: flex-start; gap: 32px; }
.step-num {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--type-accent);
  color: #0d1117;
  font-size: 30px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.step-text  { font-size: 34px; color: var(--text-pri); line-height: 1.5; padding-top: 10px; }

/* ── callout (new — v12) ────────────────────────────────── */

.callout-slide {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
.callout-box {
  background: color-mix(in srgb, var(--type-accent) 10%, var(--bg-card));
  border: 2px solid var(--type-accent);
  border-radius: 16px;
  padding: 56px 72px;
  max-width: 1440px;
  display: flex;
  flex-direction: column;
  gap: 28px;
  box-shadow: 0 0 60px color-mix(in srgb, var(--type-accent) 15%, transparent);
}
.callout-label {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: .10em;
  text-transform: uppercase;
  color: var(--type-accent);
}
.callout-text {
  font-size: 48px;
  font-weight: 600;
  color: var(--text-pri);
  line-height: 1.4;
}
```

---

## Acceptance criteria

- [ ] `tutor/assets/html/fonts/Inter-Regular.woff2` exists, file size ≥ 80 KB
- [ ] `tutor/assets/html/fonts/Inter-SemiBold.woff2` exists, file size ≥ 80 KB
- [ ] `tutor/assets/html/fonts/Inter-Bold.woff2` exists, file size ≥ 80 KB
- [ ] `tutor/assets/html/fonts/JetBrainsMono-Regular.woff2` exists, file size ≥ 60 KB
- [ ] `slide_base.css` contains `@font-face` for `"Inter"` with weights 400, 600, 700
- [ ] `slide_base.css` contains `@font-face` for `"JetBrains Mono"` with weight 400
- [ ] `slide_base.css` declares `--type-accent: var(--cyan)` in `:root`
- [ ] `slide_base.css` declares `--font-ui` using `"Inter"` as the first family
- [ ] `slide_base.css` declares `--font-mono` using `"JetBrains Mono"` as the first family
- [ ] `slide_base.css` contains `.step-num` class (for step_sequence)
- [ ] `slide_base.css` contains `.callout-box` class (for callout)
- [ ] All legacy alias tokens present: `--accent-cyn`, `--accent-amb`, `--accent-grn`, `--divider`
- [ ] All pre-existing tests still pass
- [ ] ruff clean (no Python changes, but verify imports)
