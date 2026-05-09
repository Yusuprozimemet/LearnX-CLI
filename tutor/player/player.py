import logging
import os
import time
from dataclasses import dataclass, field
from typing import Literal

import pygame

from tutor.constants import PLAYER_POLL_HZ
from tutor.models import Chunk, SessionLog, TeachingUnit
from tutor.player import input_handler, player_display

log = logging.getLogger(__name__)

PlayerState = Literal["PLAYING", "PAUSED", "ASKING", "ANSWERING", "STOPPED"]

MUSIC_END = pygame.USEREVENT + 1


@dataclass
class TutorPlayer:
    unit_files: list[str]
    units: list[TeachingUnit]
    chunks: list[Chunk] = field(default_factory=list)
    session: SessionLog | None = None
    llm_fn: object = None
    no_qa: bool = False
    qa_count: int = 0
    _state: PlayerState = field(default="PAUSED", init=False)
    _current_idx: int = field(default=0, init=False)
    _start_time: float = field(default=0.0, init=False)
    _pause_start: float = field(default=0.0, init=False)
    _current_unit_duration_s: int = field(default=0, init=False)
    _duration_cache: dict = field(default_factory=dict, init=False)

    def run(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        pygame.mixer.init()
        pygame.mixer.music.set_endevent(MUSIC_END)

        self._load_unit(0)
        self._play()

        poll_interval = 1.0 / PLAYER_POLL_HZ

        try:
            while self._state != "STOPPED":
                self._handle_events()
                self._handle_keys()
                self._redraw()
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            pass
        finally:
            pygame.mixer.quit()
            pygame.quit()

    def _play(self) -> None:
        pygame.mixer.music.play()
        self._state = "PLAYING"
        self._start_time = time.time()

    def _pause(self) -> None:
        pygame.mixer.music.pause()
        self._pause_start = time.time()
        self._state = "PAUSED"

    def _resume(self) -> None:
        pygame.mixer.music.unpause()
        paused_for = time.time() - self._pause_start
        self._start_time += paused_for
        self._state = "PLAYING"

    def _load_unit(self, idx: int) -> None:
        if idx >= len(self.unit_files):
            self._on_session_complete()
            return
        self._current_idx = idx
        path = self.unit_files[idx]
        pygame.mixer.music.load(path)
        if path not in self._duration_cache:
            try:
                from pydub import AudioSegment

                audio = AudioSegment.from_mp3(path)
                self._duration_cache[path] = len(audio) // 1000
            except Exception:
                self._duration_cache[path] = 0
        self._current_unit_duration_s = self._duration_cache[path]
        log.info("Loaded unit %d: %s", idx, path)

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == MUSIC_END and self._state == "PLAYING":
                next_idx = self._current_idx + 1
                if next_idx < len(self.unit_files):
                    self._load_unit(next_idx)
                    self._play()
                else:
                    self._on_session_complete()

    def _handle_keys(self) -> None:
        if self._state in ("ASKING", "ANSWERING"):
            return
        key = input_handler.get_key()
        if key is None:
            return
        dispatch: dict[str, object] = {
            " ": self._toggle_play_pause,
            "p": self._toggle_play_pause,
            "n": self._next_unit,
            "b": self._prev_unit,
            "r": self._replay_unit,
            "s": self._print_summary,
            "q": self._quit,
            "?": self._ask_question,
        }
        action = dispatch.get(key)
        if action:
            action()

    def _toggle_play_pause(self) -> None:
        if self._state == "PLAYING":
            self._pause()
        elif self._state == "PAUSED":
            self._resume()

    def _next_unit(self) -> None:
        was_playing = self._state == "PLAYING"
        pygame.mixer.music.stop()
        next_idx = min(self._current_idx + 1, len(self.unit_files) - 1)
        self._load_unit(next_idx)
        if was_playing:
            self._play()

    def _prev_unit(self) -> None:
        was_playing = self._state == "PLAYING"
        pygame.mixer.music.stop()
        prev_idx = max(self._current_idx - 1, 0)
        self._load_unit(prev_idx)
        if was_playing:
            self._play()

    def _replay_unit(self) -> None:
        pygame.mixer.music.stop()
        self._load_unit(self._current_idx)
        self._play()

    def _print_summary(self) -> None:
        if self._current_idx < len(self.units):
            player_display.print_summary(self.units[self._current_idx])

    def _quit(self) -> None:
        pygame.mixer.music.stop()
        self._state = "STOPPED"

    def _ask_question(self) -> None:
        if self.no_qa or self.llm_fn is None:
            player_display.print_qa_disabled()
            return

        if self._state == "PLAYING":
            self._pause()

        self._state = "ASKING"
        player_display.clear_status()
        question = self._prompt_for_question()

        if question is None:
            self._state = "PAUSED"
            return

        self._state = "ANSWERING"
        player_display.print_thinking()

        from tutor.qa import qa

        current_unit = (
            self.units[self._current_idx] if self._current_idx < len(self.units) else None
        )
        if current_unit is None:
            player_display.print_no_context()
            self._state = "PAUSED"
            return

        answer_text = qa.answer(
            question=question,
            current_unit=current_unit,
            all_chunks=self.chunks,
            session=self.session,
            llm_fn=self.llm_fn,
            position_seconds=self._elapsed_seconds(),
        )
        self.qa_count += 1

        player_display.print_answer(answer_text, current_unit.concept)
        self._state = "PAUSED"
        player_display.print_resume_hint()

    def _prompt_for_question(self) -> str | None:
        unit = self.units[self._current_idx] if self._current_idx < len(self.units) else None
        topic = unit.concept if unit else "current topic"
        player_display.print_question_header(
            topic, player_display._fmt_time(self._elapsed_seconds())
        )
        try:
            return input("Your question: ").strip() or None
        except (KeyboardInterrupt, EOFError):
            player_display.print_cancelled()
            return None

    def _redraw(self) -> None:
        if self._state == "STOPPED" or self._current_idx >= len(self.units):
            return
        unit = self.units[self._current_idx]
        elapsed_s = self._elapsed_seconds()
        total_s = self._unit_duration_s()
        player_display.render_status(
            unit=unit,
            unit_idx=self._current_idx + 1,
            total_units=len(self.units),
            elapsed_s=elapsed_s,
            total_s=total_s,
            state=self._state,
        )

    def _elapsed_seconds(self) -> int:
        if self._state == "PAUSED":
            return int(self._pause_start - self._start_time)
        if self._state == "PLAYING":
            return int(time.time() - self._start_time)
        return 0

    def _unit_duration_s(self) -> int:
        return self._current_unit_duration_s

    def _get_duration(self, filepath: str) -> int:
        return self._duration_cache.get(filepath, 0)

    def run_in_shell(self) -> None:
        """Headless playback loop for the interactive shell — no keyboard, no status bar."""
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.init()
        pygame.mixer.init()
        pygame.mixer.music.set_endevent(MUSIC_END)

        self._load_unit(0)
        self._play()

        poll_interval = 1.0 / PLAYER_POLL_HZ

        try:
            while self._state != "STOPPED":
                self._handle_events()
                time.sleep(poll_interval)
        finally:
            pygame.mixer.quit()
            pygame.quit()

    def _ask_question_from_shell(self, question: str) -> None:
        """Answer a question posed from the shell thread (question already collected)."""
        if self.no_qa or self.llm_fn is None:
            from tutor.cli import theme

            print(theme.yellow("  Q&A is disabled (no API key or --no-qa set)."))
            return
        if self._current_idx >= len(self.units):
            from tutor.cli import theme

            print(theme.red("  No unit loaded."))
            return

        self._state = "ANSWERING"
        from tutor.cli import theme

        print(theme.dim("  Thinking..."))

        from tutor.qa import qa

        current_unit = self.units[self._current_idx]
        answer_text = qa.answer(
            question=question,
            current_unit=current_unit,
            all_chunks=self.chunks,
            session=self.session,
            llm_fn=self.llm_fn,
            position_seconds=self._elapsed_seconds(),
        )
        self.qa_count += 1

        print(f"\n  {theme.bold(current_unit.concept)}")
        print(f"  {answer_text}\n")
        self._state = "PAUSED"

    def _on_session_complete(self) -> None:
        self._state = "STOPPED"
        player_display.print_session_complete(
            unit_count=len(self.units),
            total_s=sum(self._get_duration(f) for f in self.unit_files),
            qa_count=self.qa_count,
        )
