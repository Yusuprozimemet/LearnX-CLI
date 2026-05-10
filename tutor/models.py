from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class DocProfile:
    filepath: str
    raw_bytes: int
    estimated_tokens: int
    strategy: Literal["A", "B", "C"]
    section_count: int
    has_code_blocks: bool
    language_hint: str


@dataclass
class Chunk:
    chunk_id: str
    breadcrumb: str
    heading: str
    level: int
    token_count: int
    text: str
    has_code: bool = False
    summary: str = ""
    overlapping: bool = False
    key_terms: list[str] = field(default_factory=list)


@dataclass
class TeachingUnit:
    unit: int
    concept: str
    source_sections: list[str]
    complexity: int  # 1 | 2 | 3
    word_budget: int
    key_facts: list[str]
    common_misconception: str
    good_analogy: str
    question_style: str
    memory_hook: str
    prerequisite_concepts: list[str] = field(default_factory=list)
    js_contrast: str = ""
    production_relevance: str = ""


@dataclass
class DialogueLine:
    speaker: str  # "ALEX" | "MAYA" | "SAM"
    text: str
    unit_number: int  # 0 = intro, 1+ = unit, -1 = outro


@dataclass
class RenderedSegment:
    line: DialogueLine
    audio_path: str
    duration_ms: int


@dataclass
class QAExchange:
    id: int
    unit_number: int
    unit_concept: str
    position_seconds: int
    question: str
    answer: str
    source_sections: list[str]
    timestamp: str


@dataclass
class SessionLog:
    source_file: str
    session_start: str
    format: str
    duration_minutes: int
    exchanges: list[QAExchange] = field(default_factory=list)


@dataclass
class TimingEntry:
    line_index: int  # 0-based within the unit
    speaker: str  # "ALEX" | "MAYA" | "SAM"
    text: str  # dialogue line text — for cross-referencing only
    start_ms: int  # offset from unit MP3 start, in milliseconds
    end_ms: int  # exclusive end; end_ms - start_ms == len(audio) in ms


VALID_VISUAL_TYPES: frozenset[str] = frozenset(
    {
        "hook_question",
        "definition",
        "analogy",
        "comparison",
        "code_example",
        "diagram",
        "question_prompt",
        "decision_guide",
        "key_insight",
        "memory_hook",
    }
)


@dataclass
class SlideSegment:
    unit_index: int
    segment_index: int
    lines_start: int
    lines_end: int
    visual_type: str
    title: str
    body: str | None
    code: str | None
    language: str | None
    mermaid: str | None
    left: str | None
    right: str | None
    rows: list | None
    png_path: str = ""


@dataclass
class VisualSpec:
    unit_index: int
    slide_type: str  # "title_card" | "unit" | "outro"
    concept: str = ""
    hook_question: str = ""
    key_points: list[str] = field(default_factory=list)
    code_snippet: str | None = None
    diagram_type: str = "none"
    diagram_spec: str | dict[str, object] | None = None
    memory_hook: str = ""
    analogy: str = ""
    # title_card fields
    title: str = ""
    subtitle: str = ""
    doc_source: str = ""
    # outro fields
    memory_hooks: list[str] = field(default_factory=list)
    session_stats: str = ""
