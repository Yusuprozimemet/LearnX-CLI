from tutor.constants import MIN_CHUNK_TOKENS
from tutor.ingestion.chunker import chunk
from tutor.models import DocProfile

SAMPLE_B = """
## The JVM

The JVM loads bytecode stored in .class files and executes it on any operating system.
JIT compilation identifies hot code paths and compiles them to native machine code at
runtime, so repeated calls become significantly faster than interpreted execution.
Memory is split into the stack for local variables and method calls, and the heap for
all objects created with the new keyword.

## Primitives

Java has eight primitive types: int, long, double, float, boolean, char, byte, and short.
Primitives are stored directly on the stack and hold their values inline, unlike reference
types which store a pointer to an object on the heap. Autoboxing converts primitives to
their wrapper classes such as Integer or Boolean automatically when needed.

## Pass-by-Value

Java is strictly pass-by-value. When you pass a variable to a method, Java copies the
value of that variable into the method parameter. For primitives this is the actual number.
For reference types this is the memory address, which means the caller and the method share
the same heap object, but reassigning the parameter inside the method does not affect the
caller's original variable.
""".strip()

SAMPLE_NO_HEADINGS = "Java is a language. It has classes and objects. " * 100


def _make_profile(text: str, strategy: str) -> DocProfile:
    return DocProfile(
        filepath="test.md",
        raw_bytes=len(text.encode()),
        estimated_tokens=int(len(text.split()) * 1.3),
        strategy=strategy,
        section_count=3,
        has_code_blocks=False,
        language_hint="java",
    )


def test_strategy_b_produces_multiple_chunks():
    profile = _make_profile(SAMPLE_B, "B")
    chunks = chunk(SAMPLE_B, profile)
    assert len(chunks) >= 2


def test_strategy_b_chunk_ids_are_slugified():
    profile = _make_profile(SAMPLE_B, "B")
    chunks = chunk(SAMPLE_B, profile)
    for c in chunks:
        assert " " not in c.chunk_id
        assert c.chunk_id == c.chunk_id.lower()


def test_strategy_b_no_headings_falls_back_to_c():
    profile = _make_profile(SAMPLE_NO_HEADINGS, "B")
    chunks = chunk(SAMPLE_NO_HEADINGS, profile)
    assert any("window" in c.chunk_id for c in chunks)


def test_strategy_a_produces_single_chunk():
    short = "Java is statically typed."
    profile = _make_profile(short, "A")
    chunks = chunk(short, profile)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "full_doc"


def test_strategy_c_produces_window_chunks():
    long_text = "Java is a language. " * 500
    profile = _make_profile(long_text, "C")
    chunks = chunk(long_text, profile)
    assert len(chunks) > 1
    assert all("window" in c.chunk_id for c in chunks)


def test_strategy_c_overlap_flag():
    long_text = "Java is a language. " * 500
    profile = _make_profile(long_text, "C")
    chunks = chunk(long_text, profile)
    # First chunk is not overlapping, rest are
    assert chunks[0].overlapping is False
    assert all(c.overlapping is True for c in chunks[1:])


def test_no_chunk_under_min_tokens():
    profile = _make_profile(SAMPLE_B, "B")
    chunks = chunk(SAMPLE_B, profile)
    for c in chunks:
        assert c.token_count >= MIN_CHUNK_TOKENS
