"""Tests for tutor/assets/__init__.py — path constants."""

from pathlib import Path

from tutor.assets import ASSETS_DIR, FONTS_DIR, LOGO_PATH


def test_assets_dir_is_path():
    assert isinstance(ASSETS_DIR, Path)


def test_fonts_dir_is_path():
    assert isinstance(FONTS_DIR, Path)


def test_logo_path_is_path():
    assert isinstance(LOGO_PATH, Path)


def test_fonts_dir_is_child_of_assets_dir():
    assert FONTS_DIR.parent == ASSETS_DIR


def test_logo_path_is_inside_assets_dir():
    assert LOGO_PATH.parent == ASSETS_DIR


def test_assets_dir_exists():
    """The assets package directory should exist on disk."""
    assert ASSETS_DIR.exists()
    assert ASSETS_DIR.is_dir()


def test_fonts_dir_name_is_fonts():
    assert FONTS_DIR.name == "fonts"


def test_logo_path_name():
    assert LOGO_PATH.name == "logo_small.png"
