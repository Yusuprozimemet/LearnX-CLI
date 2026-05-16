# Day 2 (v12) — Template Visual Upgrades

## Goal

Update `_base.html.j2` to support per-template style injection. Update all 12
content templates to set their type-specific `--type-accent` colour and switch to
the new CSS classes introduced in Day 1. Add two new templates: `step_sequence`
and `callout`.

After this day every slide type renders with its own accent colour and the Day 1
CSS classes are fully exercised.

---

## Done (merge gate)

```powershell
py -m pytest tutor/tests/ -v -k "visual or slide"
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Additionally render one slide of each type manually and visually verify the accent
colour is correct. No PNG should contain the Segoe UI font (verify with Inter).

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Modifies (existing):
  tutor/visual/templates/_base.html.j2
  tutor/visual/templates/hook_question.html.j2
  tutor/visual/templates/definition.html.j2
  tutor/visual/templates/analogy.html.j2
  tutor/visual/templates/comparison.html.j2
  tutor/visual/templates/code_example.html.j2
  tutor/visual/templates/diagram.html.j2
  tutor/visual/templates/question_prompt.html.j2
  tutor/visual/templates/decision_guide.html.j2
  tutor/visual/templates/key_insight.html.j2
  tutor/visual/templates/memory_hook.html.j2
  tutor/visual/templates/title_card.html.j2
  tutor/visual/templates/outro.html.j2

Creates (new):
  tutor/visual/templates/step_sequence.html.j2
  tutor/visual/templates/callout.html.j2

Does NOT touch:
  tutor/assets/html/slide_base.css   ← already done in Day 1
  tutor/visual/slide_renderer.py     ← unchanged
  tutor/**/*.py                      ← unchanged
```

---

## Type-accent colour assignments

Each visual type is assigned one colour from the v12 accent palette.
These assignments are consistent across all slides in a session.

| Visual type       | CSS variable | Colour   |
|-------------------|--------------|----------|
| `hook_question`   | `--cyan`     | #22d3ee  |
| `definition`      | `--blue`     | #60a5fa  |
| `analogy`         | `--purple`   | #c084fc  |
| `comparison`      | `--teal`     | #2dd4bf  |
| `code_example`    | `--green`    | #4ade80  |
| `diagram`         | `--indigo`   | #818cf8  |
| `question_prompt` | `--amber`    | #fbbf24  |
| `decision_guide`  | `--orange`   | #fb923c  |
| `key_insight`     | `--pink`     | #f472b6  |
| `memory_hook`     | `--rose`     | #fb7185  |
| `step_sequence`   | `--sky`      | #38bdf8  |
| `callout`         | `--amber`    | #fbbf24  |

---

## Change 1 — Update `_base.html.j2`

Add a `{% block extra_style %}{% endblock %}` block inside `<head>` so child
templates can inject CSS (specifically `:root { --type-accent: ... }`). Move the
`slide_base.css` link so it loads first; `extra_style` loads after, allowing
per-template overrides.

```jinja2
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1920, height=1080">
<link rel="stylesheet" href="{{ asset_dir }}/slide_base.css">
<link rel="stylesheet" href="{{ asset_dir }}/theme-learnx-dark.css">
<script src="{{ asset_dir }}/highlight.min.js"></script>
<script src="{{ asset_dir }}/highlight-java.min.js"></script>
<script src="{{ asset_dir }}/highlight-python.min.js"></script>
<script src="{{ asset_dir }}/highlight-javascript.min.js"></script>
<script src="{{ asset_dir }}/mermaid.min.js"></script>
<style>
{% block extra_style %}{% endblock %}
</style>
<script>
  document.addEventListener('DOMContentLoaded', function() {
    if (typeof hljs !== 'undefined') { hljs.highlightAll(); }
    if (typeof mermaid !== 'undefined') { mermaid.initialize({startOnLoad: true, theme: 'dark'}); }
  });
</script>
</head>
<body>
<div class="top-bar">
  {% block top_bar %}
  {% if seg is defined %}Unit {{ seg.unit_index }} &middot; {{ seg.title | e }}{% endif %}
  {% endblock %}
</div>
<div class="content">
  {% block content %}{% endblock %}
</div>
<div class="footer-bar">
  {% block footer %}
  {% if total_dots is defined %}
    {% for i in range(total_dots) %}
      <span class="dot {% if i < current_dot %}dot--filled{% else %}dot--hollow{% endif %}"></span>
    {% endfor %}
  {% endif %}
  {% endblock %}
</div>
</body>
</html>
```

---

## Change 2 — `hook_question.html.j2`

Accent: `--cyan`. Replaces `.learn-list li` with the new `::before` arrow pattern;
adds `.learn-label` heading above the list.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--cyan); }{% endblock %}
{% block content %}
<div class="hook-slide">
  <div class="hook-question">{{ seg.body | e }}</div>
  {% if seg.rows %}
  <div>
    <div class="learn-label">What you'll learn</div>
    <ul class="learn-list">
      {% for point in seg.rows %}<li>{{ point[0] | e }}</li>{% endfor %}
    </ul>
  </div>
  {% endif %}
</div>
{% endblock %}
```

---

## Change 3 — `definition.html.j2`

Accent: `--blue`. Keep structure; update class names to v12.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--blue); }{% endblock %}
{% block content %}
<div class="definition-slide">
  <div class="definition-term">{{ seg.title | e }}</div>
  <div class="definition-text">{{ seg.body | e }}</div>
  {% if seg.code %}
  <pre><code class="language-{{ seg.language or 'text' }}">{{ seg.code | e }}</code></pre>
  {% endif %}
</div>
{% endblock %}
```

---

## Change 4 — `analogy.html.j2`

Accent: `--purple`. Two-panel grid with top-border accent. Use `seg.left`,
`seg.right`, `seg.rows` (first row) as panel content; fall back to `seg.body`
split on ` — ` when `seg.rows` is absent.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--purple); }{% endblock %}
{% block content %}
<div class="analogy-slide">
  {% if seg.rows and seg.rows|length > 0 %}
  <div class="analogy-panel">
    <div class="analogy-label">{{ seg.left or 'Real world' }}</div>
    <div class="analogy-body">{{ seg.rows[0][0] | e }}</div>
  </div>
  <div class="analogy-sep">≈</div>
  <div class="analogy-panel">
    <div class="analogy-label">{{ seg.right or 'In code' }}</div>
    <div class="analogy-body">{{ seg.rows[0][1] | e }}</div>
  </div>
  {% else %}
  <div class="analogy-panel" style="grid-column:1/4;">
    <div class="analogy-body">{{ seg.body | e }}</div>
  </div>
  {% endif %}
</div>
{% endblock %}
```

---

## Change 5 — `comparison.html.j2`

Accent: `--teal`. No structural change; update any inline accent references removed
now that `--type-accent` drives colours.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--teal); }{% endblock %}
{% block content %}
<div class="comparison-slide">
  <table class="comparison-table">
    <thead>
      <tr>
        <th class="th-left">{{ seg.left | e }}</th>
        <th class="th-right">{{ seg.right | e }}</th>
      </tr>
    </thead>
    <tbody>
      {% for row in seg.rows %}
      <tr>
        <td>{{ row[0] | e }}</td>
        <td>{{ row[1] | e }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

---

## Change 6 — `code_example.html.j2`

Accent: `--green`. Adds `.code-desc` when `seg.body` is present.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--green); }{% endblock %}
{% block content %}
<div class="code-slide">
  {% if seg.body %}
  <div class="code-desc">{{ seg.body | e }}</div>
  {% endif %}
  {% if seg.code %}
  <pre><code class="language-{{ seg.language or 'text' }}">{{ seg.code | e }}</code></pre>
  {% endif %}
</div>
{% endblock %}
```

---

## Change 7 — `diagram.html.j2`

Accent: `--indigo`. No structural change; accent injection is new.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--indigo); }{% endblock %}
{% block content %}
<div class="diagram-slide">
  <div class="mermaid">{{ seg.mermaid }}</div>
</div>
{% endblock %}
```

---

## Change 8 — `question_prompt.html.j2`

Accent: `--amber`. Speaker badge colour driven by speaker name.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--amber); }{% endblock %}
{% block top_bar %}{% endblock %}
{% block content %}
<div class="question-slide">
  <div class="speaker-badge badge-{{ seg.body.split(':')[0].lower() if seg.body and ':' in seg.body else 'maya' }}">
    {{ seg.body.split(':')[0] if seg.body and ':' in seg.body else 'MAYA' }}
  </div>
  <div class="question-text">
    "{{ (seg.body.split(':', 1)[1].strip() if seg.body and ':' in seg.body else seg.body) | e }}"
  </div>
</div>
{% endblock %}
{% block footer %}{% endblock %}
```

---

## Change 9 — `decision_guide.html.j2`

Accent: `--orange`. Uses `comparison-table` layout (same markup as comparison but
different accent). Falls back to body text when `seg.rows` is absent.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--orange); }{% endblock %}
{% block content %}
<div class="comparison-slide">
  {% if seg.rows %}
  <table class="comparison-table">
    <thead>
      <tr>
        <th class="th-left">{{ seg.left or 'Use when' | e }}</th>
        <th class="th-right">{{ seg.right or 'Avoid when' | e }}</th>
      </tr>
    </thead>
    <tbody>
      {% for row in seg.rows %}
      <tr><td>{{ row[0] | e }}</td><td>{{ row[1] | e }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <div class="definition-slide">
    <div class="definition-term">{{ seg.title | e }}</div>
    <div class="definition-text">{{ seg.body | e }}</div>
  </div>
  {% endif %}
</div>
{% endblock %}
```

---

## Change 10 — `key_insight.html.j2`

Accent: `--pink`. Accent rule bar (`key-insight-rule`) now uses `--type-accent`
automatically via the Day 1 CSS.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--pink); }{% endblock %}
{% block content %}
<div class="key-insight-slide">
  <div class="key-insight-rule"></div>
  <div class="key-insight-text">{{ seg.body | e }}</div>
  <div class="key-insight-rule"></div>
</div>
{% endblock %}
```

---

## Change 11 — `memory_hook.html.j2`

Accent: `--rose`.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--rose); }{% endblock %}
{% block content %}
<div class="memory-hook-slide">
  <div class="memory-hook-text">{{ seg.body | e }}</div>
</div>
{% endblock %}
```

---

## Change 12 — `title_card.html.j2`

Uses the gradient accent bar. `--type-accent` default (cyan) applies; no override
needed since title cards have no specific type.

```jinja2
{% extends "_base.html.j2" %}
{% block top_bar %}LearnX{% endblock %}
{% block content %}
<div class="title-card-slide">
  <div class="title-card-accent"></div>
  <div class="title-card-title">{{ spec.title | e }}</div>
  <div class="title-card-sub">{{ spec.subtitle | e }}</div>
</div>
{% endblock %}
{% block footer %}{% endblock %}
```

---

## Change 13 — `outro.html.j2`

```jinja2
{% extends "_base.html.j2" %}
{% block top_bar %}LearnX{% endblock %}
{% block content %}
<div class="outro-slide">
  <div class="outro-text">That's a wrap.</div>
  {% if spec.memory_hooks %}
  <div class="outro-sub">
    {% for hook in spec.memory_hooks[:3] %}{{ hook | e }}{% if not loop.last %} &nbsp;·&nbsp; {% endif %}{% endfor %}
  </div>
  {% endif %}
  <div class="outro-sub">{{ spec.session_stats | e }}</div>
</div>
{% endblock %}
{% block footer %}{% endblock %}
```

---

## Change 14 — New: `step_sequence.html.j2`

Accent: `--sky`. Renders numbered steps from `seg.body` (steps separated by `\n`).
Each step gets a numbered circle. Used when ALEX narrates a sequential process
("first… then… finally…").

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--sky); }{% endblock %}
{% block content %}
<div class="step-slide">
  {% if seg.body %}
    {% for step in seg.body.split('\n') %}
    {% if step.strip() %}
    <div class="step-item">
      <div class="step-num">{{ loop.index }}</div>
      <div class="step-text">{{ step.strip() | e }}</div>
    </div>
    {% endif %}
    {% endfor %}
  {% endif %}
</div>
{% endblock %}
```

---

## Change 15 — New: `callout.html.j2`

Accent: `--amber`. A highlighted box for single important statements: warnings,
tips, prerequisites, or quotes. `seg.title` is the label (e.g. "NOTE", "WARNING",
"TIP"). `seg.body` is the main text.

```jinja2
{% extends "_base.html.j2" %}
{% block extra_style %}:root { --type-accent: var(--amber); }{% endblock %}
{% block content %}
<div class="callout-slide">
  <div class="callout-box">
    <div class="callout-label">{{ seg.title | e }}</div>
    <div class="callout-text">{{ seg.body | e }}</div>
  </div>
</div>
{% endblock %}
```

---

## Acceptance criteria

- [ ] `_base.html.j2` contains `{% block extra_style %}{% endblock %}`
- [ ] Every content template (hook_question through memory_hook) sets `--type-accent` in `{% block extra_style %}`
- [ ] `hook_question.html.j2` uses `--cyan`
- [ ] `definition.html.j2` uses `--blue`
- [ ] `analogy.html.j2` uses `--purple`
- [ ] `comparison.html.j2` uses `--teal`
- [ ] `code_example.html.j2` uses `--green`
- [ ] `diagram.html.j2` uses `--indigo`
- [ ] `question_prompt.html.j2` uses `--amber`
- [ ] `decision_guide.html.j2` uses `--orange`
- [ ] `key_insight.html.j2` uses `--pink`
- [ ] `memory_hook.html.j2` uses `--rose`
- [ ] `step_sequence.html.j2` exists and uses `--sky`
- [ ] `callout.html.j2` exists and uses `--amber`
- [ ] `step_sequence.html.j2` renders numbered circles (`.step-num`) for each `\n`-separated step in `seg.body`
- [ ] `callout.html.j2` renders `.callout-label` from `seg.title` and `.callout-text` from `seg.body`
- [ ] `title_card.html.j2` renders `.title-card-accent` gradient bar
- [ ] All pre-existing tests still pass
- [ ] ruff clean
