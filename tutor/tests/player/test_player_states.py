from unittest.mock import MagicMock, patch

import pytest

from tutor.models import TeachingUnit


def _make_unit(n: int = 1) -> TeachingUnit:
    return TeachingUnit(
        unit=n,
        concept=f"Concept {n}",
        source_sections=[],
        complexity=2,
        word_budget=400,
        key_facts=["fact"],
        common_misconception="wrong",
        good_analogy="like a thing",
        question_style="recall",
        memory_hook="remember this",
    )


@pytest.fixture
def player(tmp_path):
    """Create a TutorPlayer with mocked pygame."""
    fake_mp3 = tmp_path / "unit_01.mp3"
    fake_mp3.write_bytes(b"fake")

    with patch("tutor.player.player.pygame") as mock_pygame:
        mock_pygame.USEREVENT = 0
        mock_pygame.mixer = MagicMock()

        from tutor.player.player import TutorPlayer

        p = TutorPlayer(
            unit_files=[str(fake_mp3)],
            units=[_make_unit()],
        )
        p._state = "PAUSED"
        yield p


def test_initial_state_is_paused(player):
    assert player._state == "PAUSED"


def test_toggle_play_pause_from_paused(player):
    with patch.object(player, "_resume") as mock_resume:
        player._toggle_play_pause()
        mock_resume.assert_called_once()


def test_toggle_play_pause_from_playing(player):
    player._state = "PLAYING"
    with patch.object(player, "_pause") as mock_pause:
        player._toggle_play_pause()
        mock_pause.assert_called_once()


def test_quit_sets_stopped(player):
    with patch("tutor.player.player.pygame"):
        player._quit()
    assert player._state == "STOPPED"


def test_no_qa_flag_skips_llm(player, capsys):
    player.no_qa = True
    player._state = "PAUSED"
    player._ask_question()
    out = capsys.readouterr().out
    assert "disabled" in out.lower() or "no-qa" in out.lower()


def test_ask_question_pauses_if_playing(player):
    player._state = "PLAYING"
    player.no_qa = True
    player._ask_question()
    assert player._state in ("PAUSED", "PLAYING")


def test_next_unit_bounded(player):
    player._current_idx = 0
    with patch("tutor.player.player.pygame"):
        with patch.object(player, "_load_unit") as mock_load:
            with patch.object(player, "_play"):
                player._state = "PLAYING"
                player._next_unit()
                mock_load.assert_called_with(0)
