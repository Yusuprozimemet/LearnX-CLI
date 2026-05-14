"""Slide render: Playwright loads HTML slides, page is not blank, no error messages."""
import pathlib
import tempfile

import pytest

SLIDE_DIR = pathlib.Path(tempfile.gettempdir()) / "learnx_e2e_smoke" / "slides"
SCREENSHOT_PATH = pathlib.Path(tempfile.gettempdir()) / "learnx_e2e_smoke" / "slide_01.png"


@pytest.fixture(scope="module")
def browser_page(pipeline_output):
    if not SLIDE_DIR.exists():
        pytest.skip("slides/ directory not present — visual pipeline not run")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        yield page
        browser.close()


def test_at_least_one_slide_exists(pipeline_output):
    if not SLIDE_DIR.exists():
        pytest.skip("slides/ directory not present — visual pipeline not run")
    html_files = list(SLIDE_DIR.glob("*.html"))
    assert html_files, f"No .html files found in {SLIDE_DIR}"


def test_slide_page_not_blank(browser_page):
    html_files = sorted(SLIDE_DIR.glob("*.html"))
    first_slide = html_files[0].as_uri()
    browser_page.goto(first_slide)
    content = browser_page.content()
    assert len(content) > 500, (
        f"Slide page appears blank: content length={len(content)} (expected > 500)"
    )


def test_slide_has_visible_text(browser_page):
    html_files = sorted(SLIDE_DIR.glob("*.html"))
    first_slide = html_files[0].as_uri()
    browser_page.goto(first_slide)
    text = browser_page.locator("body").inner_text().strip()
    assert text, "Slide body contains no visible text"


def test_slide_no_error_messages(browser_page):
    html_files = sorted(SLIDE_DIR.glob("*.html"))
    first_slide = html_files[0].as_uri()
    browser_page.goto(first_slide)
    text = browser_page.locator("body").inner_text()
    assert "Error" not in text, f"Slide contains 'Error' in visible text"
    assert "TypeError" not in text, f"Slide contains 'TypeError' in visible text"


def test_slide_screenshot_saved(browser_page):
    html_files = sorted(SLIDE_DIR.glob("*.html"))
    first_slide = html_files[0].as_uri()
    browser_page.goto(first_slide)
    browser_page.screenshot(path=str(SCREENSHOT_PATH))
    assert SCREENSHOT_PATH.exists(), f"Screenshot not saved: {SCREENSHOT_PATH}"
    assert SCREENSHOT_PATH.stat().st_size > 5000, (
        f"Screenshot too small ({SCREENSHOT_PATH.stat().st_size} bytes) — may be a blank image"
    )
