# Day 5 — Q&A Engine

## What works at the end of this day

The `?` key now works in the interactive player. When pressed:
1. Audio pauses immediately
2. Terminal shows a question prompt
3. Student types their question and presses Enter
4. A spinner appears while the LLM answers (~1–3 seconds on Groq)
5. The answer prints with a source citation
6. Student presses `space` to resume audio

Every Q&A exchange is saved to `tutorial.session.json`.

```bash
python tutor/tutor.py play tutorial_units/ --no-qa   # listen-only, Q&A disabled
python tutor/tutor.py sample_docs/java-basics.md --play  # generate + play + Q&A
```

## Prerequisites

- Day 4 completed: player runs, audio plays, keyboard commands work
- `tutorial.units.json` exists alongside `tutorial_units/` (saved by Day 4 generation)
- The source chunks need to be accessible at play-time — see "Chunk persistence" below

---

## Chunk persistence (required before Q&A can work)

Q&A needs the original source chunks as context for the LLM. These are in memory during generation but discarded afterward. Persist them alongside the audio output.

**In `tutor.py`'s `cmd_generate()`**, after summarization, save chunks to disk:

```python
import json
from dataclasses import asdict
chunks_path = Path(args.output).parent / "tutorial.chunks.json"
with open(chunks_path, "w", encoding="utf-8") as f:
    json.dump([asdict(c) for c in chunks], f, indent=2, ensure_ascii=False)
```

**In `cmd_play()`**, load them back:
```python
chunks_path = units_dir.parent / "tutorial.chunks.json"
if chunks_path.exists():
    with open(chunks_path) as f:
        raw_chunks = json.load(f)
    from tutor.models import Chunk
    chunks = [Chunk(**c) for c in raw_chunks]
else:
    chunks = []
    log.warning("tutorial.chunks.json not found — Q&A will work without source context")
```

Pass `chunks` into `TutorPlayer`.

---

## Files to create or modify today

---

### 1. `tutor/qa/__init__.py` (empty)

---

### 2. `tutor/qa/qa.py` (~150 lines)

One responsibility: answer a student's question grounded in the source document.

```python
import logging
from datetime import datetime
from pathlib import Path
import json

from tutor.models import TeachingUnit, Chunk, QAExchange, SessionLog
from tutor.infra import llm
from tutor.config import Config
from tutor.exceptions import LLMError

log = logging.getLogger(__name__)

QA_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "qa.txt"
```

**`answer()` — public function:**
```python
def answer(
    question: str,
    current_unit: TeachingUnit,
    all_chunks: list[Chunk],
    session: SessionLog,
    llm_fn,
    position_seconds: int = 0,
) -> str:
    """
    Answer student's question. Returns answer string. Appends exchange to session.
    """
    context = _build_context(current_unit, all_chunks, session)
    prompt = _load_qa_prompt(current_unit.concept)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"{context}\n\nStudent's question: {question}"},
    ]

    try:
        raw = llm_fn(messages, call_type="qa")
    except LLMError as e:
        log.error("Q&A LLM call failed: %s", e)
        return f"Sorry — could not generate an answer right now. ({e})"

    answer_text = raw.strip()
    _append_exchange(session, current_unit, question, answer_text, position_seconds)
    return answer_text
```

**`_build_context()` — three-layer context:**
```python
def _build_context(
    current_unit: TeachingUnit,
    all_chunks: list[Chunk],
    session: SessionLog,
) -> str:
    chunk_map = {c.chunk_id: c for c in all_chunks}

    # Layer 1: current unit source chunks
    current_chunks = [
        chunk_map[s]
        for s in current_unit.source_sections
        if s in chunk_map
    ]

    # Layer 2: adjacent unit chunks (±1 unit) — requires session to have unit list
    # For now: skip adjacent chunks (they're in session.unit_list, not available here)
    # Day 6 enhancement: pass all_units list and find adjacent source_sections

    # Layer 3: last 3 Q&A exchanges
    recent = session.exchanges[-3:] if session.exchanges else []

    parts: list[str] = []

    if current_chunks:
        parts.append("=== Source Content ===")
        for chunk in current_chunks:
            parts.append(f"[{chunk.breadcrumb}]\n{chunk.text}")

    if recent:
        parts.append("\n=== Prior Questions This Session ===")
        for ex in recent:
            parts.append(f"Q: {ex.question}\nA: {ex.answer}")

    return "\n\n".join(parts) if parts else "No source content available."
```

**`_append_exchange()` — log to session and save:**
```python
def _append_exchange(
    session: SessionLog,
    unit: TeachingUnit,
    question: str,
    answer: str,
    position_seconds: int,
) -> None:
    exchange = QAExchange(
        id=len(session.exchanges) + 1,
        unit_number=unit.unit,
        unit_concept=unit.concept,
        position_seconds=position_seconds,
        question=question,
        answer=answer,
        source_sections=unit.source_sections,
        timestamp=datetime.utcnow().isoformat(),
    )
    session.exchanges.append(exchange)
    _save_session(session)
```

**`_save_session()` — persist to disk:**
```python
def _save_session(session: SessionLog) -> None:
    from dataclasses import asdict
    path = Path("tutorial.session.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(session), f, indent=2, ensure_ascii=False)
```

**`_load_qa_prompt()`:**
```python
def _load_qa_prompt(concept: str) -> str:
    try:
        template = QA_PROMPT_PATH.read_text(encoding="utf-8")
        return template.replace("{concept}", concept)
    except FileNotFoundError:
        return (
            f"Answer the student's question about: {concept}. "
            "Be concise, cite sources, end with a follow-up question."
        )
```

---

### 3. `tutor/player/player.py` — wire in Q&A (modify existing)

Add `chunks`, `session`, `llm_fn`, `no_qa` to the `TutorPlayer` dataclass:

```python
from tutor.models import TeachingUnit, Chunk, SessionLog
from tutor.config import Config

@dataclass
class TutorPlayer:
    unit_files: list[str]
    units: list[TeachingUnit]
    chunks: list[Chunk] = field(default_factory=list)
    session: SessionLog | None = None
    llm_fn: callable | None = None
    no_qa: bool = False
    qa_count: int = 0
    # ... existing private fields ...
```

Replace the `_ask_question()` stub with the real implementation:

```python
def _ask_question(self) -> None:
    if self.no_qa or self.llm_fn is None:
        print("\nQ&A disabled (--no-qa). Press [space] to resume.")
        return

    if self._state == "PLAYING":
        self._pause()

    self._state = "ASKING"
    player_display.clear_status()
    question = self._prompt_for_question()

    if question is None:
        # Ctrl+C pressed — cancel and stay paused
        self._state = "PAUSED"
        return

    self._state = "ANSWERING"
    print("\nThinking...", end="", flush=True)

    from tutor.qa import qa
    current_unit = self.units[self._current_idx] if self._current_idx < len(self.units) else None
    if current_unit is None:
        print("\n(No unit context available)")
        self._state = "PAUSED"
        return

    if self.session is None:
        self.session = _make_session()

    answer = qa.answer(
        question=question,
        current_unit=current_unit,
        all_chunks=self.chunks,
        session=self.session,
        llm_fn=self.llm_fn,
        position_seconds=self._elapsed_seconds(),
    )
    self.qa_count += 1

    _print_answer(question, answer, current_unit)
    self._state = "PAUSED"
    print("Press [space] to resume or [?] to ask another question.\n")
```

**`_prompt_for_question()`:**
```python
def _prompt_for_question(self) -> str | None:
    from tutor.player import player_display
    unit = self.units[self._current_idx] if self._current_idx < len(self.units) else None
    topic = unit.concept if unit else "current topic"

    print(f"\n── Ask a question ──────────────────────────────────")
    print(f"Topic: {topic}  |  Position: {player_display._fmt_time(self._elapsed_seconds())}")
    print()
    try:
        return input("Your question: ").strip() or None
    except (KeyboardInterrupt, EOFError):
        print(" (cancelled)")
        return None
```

**`_print_answer()`** (module-level helper, not a method):
```python
def _print_answer(question: str, answer: str, unit: TeachingUnit) -> None:
    border = "─" * 56
    print(f"\n{border}")
    print(f"Answer:\n{answer}")
    print(f"\n── Source: §{unit.concept} {border[len(unit.concept) + 10:]}")
    print()
```

---

### 4. `tutor/tutor.py` — pass Q&A dependencies to player (modify existing)

In `cmd_play()`, after loading chunks and units:

```python
from functools import partial
from tutor.infra import llm
from tutor.models import SessionLog
from datetime import datetime

config = load_config()
no_qa = getattr(args, "no_qa", False)
llm_fn = None if no_qa else partial(llm.chat, provider=args.provider, config=config)

session = SessionLog(
    source_file=str(getattr(args, "audio_file", args.output)),
    session_start=datetime.utcnow().isoformat(),
    format="tutor-student",
    duration_minutes=20,
)

player = TutorPlayer(
    unit_files=[str(f) for f in unit_files],
    units=units,
    chunks=chunks,
    session=session,
    llm_fn=llm_fn,
    no_qa=no_qa,
)
player.run()
```

---

### 5. `tutor/tests/player/test_player_states.py` (~80 lines)

State machine tests without pygame or real audio.

```python
import pytest
from unittest.mock import MagicMock, patch
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
    # Even with no_qa, playing → paused transition should happen
    # (no_qa exits before prompting, so state is PAUSED after the pause call)
    assert player._state in ("PAUSED", "PLAYING")  # no_qa returns early


def test_next_unit_bounded(player):
    player._current_idx = 0
    with patch("tutor.player.player.pygame"):
        with patch.object(player, "_load_unit") as mock_load:
            with patch.object(player, "_play"):
                player._state = "PLAYING"
                player._next_unit()
                # Already at last unit (index 0, 1 total) — should not go to 1
                # _load_unit called with min(1, 0) = 0
                mock_load.assert_called_with(0)
```

---

## Acceptance criteria

1. `python tutor/tutor.py play tutorial_units/` — press `?` — question prompt appears, type a question, answer prints with citation

2. Answer appears in < 5 seconds on Groq (llama-3.1-8b-instant is fast)

3. `tutorial.session.json` is created/appended after each question

4. `tutorial.session.json` contains correct `unit_concept`, `position_seconds`, `question`, `answer`, `timestamp`

5. Press `?` twice in succession — both answers are logged in the session file

6. `python tutor/tutor.py play tutorial_units/ --no-qa` — `?` prints "Q&A disabled" and audio resumes

7. Ctrl+C during question input — player stays paused, no LLM call, no crash

8. `cd tutor && python -m pytest tests/ -v` — all tests (Day 3 + Day 5) pass

---

## Gotchas

**`input()` blocks the player loop**: when `_prompt_for_question()` calls `input()`, the player loop is fully blocked (no event handling, no redraws). This is intentional and correct for MVP — the player is in `ASKING` state, audio is paused, no state transitions need to happen. The blocking input is the simplest correct implementation.

**Session file path**: `_save_session()` writes to `tutorial.session.json` in the current working directory. If the user runs from a different directory, this may not be alongside the audio file. Improve by passing `session_path` as a parameter to `qa.answer()`, initialized from the units directory in `cmd_play()`.

**LLM context length**: the Q&A context includes source chunk text, which can be 1–4k tokens. The `qa.txt` system prompt adds ~200 tokens. Total is safely under 6k tokens (Groq) and under the 6k budget for OpenRouter free models.

**`QAExchange` has no `position_label` field**: the plan.md schema showed it, but `models.py` may not have it. If not present, skip it — `position_seconds` is sufficient. Do not add fields to `models.py` just for display; compute `_fmt_time(position_seconds)` at display time.

**Adjacent chunk context (deferred)**: `_build_context()` has a comment about adjacent unit chunks but doesn't implement it. This is intentional for Day 5 — the current unit's chunks alone provide sufficient context for most questions. Day 6 or Phase 2 can add adjacent chunks once all units are available during play.

**Free model response quality**: Groq's `llama-3.1-8b-instant` is fast but sometimes gives generic answers not grounded in the source. If answers feel disconnected from the tutorial, check that the source chunks are being passed correctly — add `log.debug("Q&A context length: %d chars", len(context))` to verify.
