from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tutor.player.player import TutorPlayer


@dataclass
class ShellContext:
    player: TutorPlayer | None = None
    player_thread: threading.Thread | None = None
    last_units_dir: Path | None = None
    current_session: str | None = None
    last_video: Path | None = None
