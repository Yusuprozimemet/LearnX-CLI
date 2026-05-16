import pathlib
from unittest.mock import patch

import pytest

from scripts.run_review import (
    PHASE_1_FIX_ADDENDUM,
    PHASE_2_PROMPT_TEMPLATE,
    REVIEW_PROMPT_TEMPLATE,
    build_review_command,
    main,
)

AGENTS_DIR = pathlib.Path(".claude/agents")
AGENT_NAMES = ["quality", "implementation", "testing", "simplification", "product_check"]


def _parse_frontmatter(path: pathlib.Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) for a markdown file with --- delimiters."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    # parts: ['', frontmatter, body]
    fm: dict = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    body = parts[2].strip() if len(parts) > 2 else ""
    return fm, body


@pytest.fixture()
def dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    return project, home


def test_all_five_agent_files_exist():
    for name in AGENT_NAMES:
        assert (AGENTS_DIR / f"{name}.md").exists(), f"{name}.md not found in .claude/agents/"


def test_agent_frontmatter_has_name_and_description():
    for name in AGENT_NAMES:
        fm, _ = _parse_frontmatter(AGENTS_DIR / f"{name}.md")
        assert "name" in fm, f"{name}.md missing 'name' in frontmatter"
        assert "description" in fm, f"{name}.md missing 'description' in frontmatter"


def test_agent_name_matches_filename():
    for name in AGENT_NAMES:
        fm, _ = _parse_frontmatter(AGENTS_DIR / f"{name}.md")
        assert fm["name"] == name, (
            f"{name}.md: frontmatter name '{fm['name']}' != filename '{name}'"
        )


def test_agent_body_is_nonempty():
    for name in AGENT_NAMES:
        _, body = _parse_frontmatter(AGENTS_DIR / f"{name}.md")
        assert len(body) >= 50, f"{name}.md body too short ({len(body)} chars)"


def test_product_check_covers_ffprobe():
    _, body = _parse_frontmatter(AGENTS_DIR / "product_check.md")
    assert "ffprobe" in body


def test_product_check_covers_silence():
    _, body = _parse_frontmatter(AGENTS_DIR / "product_check.md")
    assert "dBFS" in body


def test_product_check_covers_playwright():
    _, body = _parse_frontmatter(AGENTS_DIR / "product_check.md")
    assert "playwright" in body.lower()


def test_product_check_covers_sync():
    _, body = _parse_frontmatter(AGENTS_DIR / "product_check.md")
    assert "drift" in body


def test_review_command_contains_print_flag(dirs):
    project, home = dirs
    cmd = build_review_command(project, home, spec_path=None, extra_args=[])
    assert "--print" in cmd


def test_review_command_with_spec_includes_spec_path(dirs):
    project, home = dirs
    spec = pathlib.Path("specs/v3/day13.md")
    cmd = build_review_command(project, home, spec_path=spec, extra_args=[])
    full = " ".join(cmd)
    assert "day13.md" in full


def test_review_dry_run_does_not_call_subprocess(dirs, capsys):
    with (
        patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]),
        patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]),
        patch("scripts.run_review.subprocess.run") as mock_run,
    ):
        main(["--dry-run"])
    mock_run.assert_not_called()


def test_review_prompt_contains_fix_notes_section():
    assert "Suggested Fix Notes" in REVIEW_PROMPT_TEMPLATE


def test_review_prompt_says_do_not_write_fixes():
    assert "Do NOT write to the fixes/" in REVIEW_PROMPT_TEMPLATE


def test_product_check_covers_fix_notes():
    _, body = _parse_frontmatter(AGENTS_DIR / "product_check.md")
    assert "Suggested fix notes" in body or "Suggested Fix Notes" in body


def test_readme_mentions_fixes_convention():
    readme = AGENTS_DIR / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "fixes/" in text
    assert "human" in text


def test_build_review_command_accepts_custom_agents_dir(dirs):
    project, home = dirs
    cmd = build_review_command(
        project, home, spec_path=None, extra_args=[], agents_dir="custom/agents"
    )
    full = " ".join(cmd)
    assert "custom/agents" in full


def test_review_main_dry_run_accepts_agents_dir_flag(dirs, capsys):
    with (
        patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]),
        patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]),
        patch("scripts.run_review.subprocess.run") as mock_run,
    ):
        main(["--agents-dir", "my/agents", "--dry-run"])
    out = capsys.readouterr().out
    assert "my/agents" in out
    mock_run.assert_not_called()


def test_review_agents_dir_missing_value_exits(dirs):
    with (
        patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]),
        patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]),
    ):
        with pytest.raises(SystemExit) as exc:
            main(["--agents-dir"])
    assert exc.value.code == 1


# ── Day 28 — two-phase review components ─────────────────────────────────────


def test_new_agent_files_exist():
    for name in ("verify_fixes", "regression_check"):
        assert (AGENTS_DIR / f"{name}.md").exists(), f"{name}.md missing"


def test_verify_fixes_agent_frontmatter():
    fm, body = _parse_frontmatter(AGENTS_DIR / "verify_fixes.md")
    assert fm.get("name") == "verify_fixes"
    assert "description" in fm
    assert len(body) >= 50


def test_regression_check_agent_frontmatter():
    fm, body = _parse_frontmatter(AGENTS_DIR / "regression_check.md")
    assert fm.get("name") == "regression_check"
    assert "description" in fm
    assert len(body) >= 50


def test_phase1_fix_addendum_mentions_commit():
    assert "commit" in PHASE_1_FIX_ADDENDUM.lower()


def test_phase2_prompt_template_has_phase1_report_placeholder():
    assert "{phase1_report}" in PHASE_2_PROMPT_TEMPLATE
    assert "{agents_instruction}" in PHASE_2_PROMPT_TEMPLATE
    assert "verify_fixes" in PHASE_2_PROMPT_TEMPLATE
    assert "regression_check" in PHASE_2_PROMPT_TEMPLATE
