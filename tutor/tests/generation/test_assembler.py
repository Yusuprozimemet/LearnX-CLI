from tutor.generation.assembler import assemble
from tutor.models import DialogueLine, TeachingUnit


def _make_unit(n: int) -> TeachingUnit:
    return TeachingUnit(
        unit=n,
        concept=f"Concept {n}",
        source_sections=[f"s0{n}"],
        complexity=2,
        word_budget=400,
        key_facts=["fact"],
        common_misconception="wrong belief",
        good_analogy="like a thing",
        question_style="recall",
        memory_hook=f"Remember concept {n}",
    )


def _make_lines(unit_num: int, count: int = 4) -> list[DialogueLine]:
    return [
        DialogueLine(
            speaker="ALEX" if i % 2 == 0 else "MAYA",
            text=f"Unit {unit_num} line {i}",
            unit_number=unit_num,
        )
        for i in range(count)
    ]


def test_assemble_starts_with_alex_intro():
    units = [_make_unit(1), _make_unit(2)]
    result = assemble(units, [_make_lines(1), _make_lines(2)], "tutor-student", "Java Basics")
    assert result[0].speaker == "ALEX"
    assert result[0].unit_number == 0


def test_assemble_ends_with_outro():
    units = [_make_unit(1)]
    result = assemble(units, [_make_lines(1)], "tutor-student", "Java Basics")
    assert result[-1].unit_number == -1


def test_assemble_transitions_between_units():
    units = [_make_unit(1), _make_unit(2)]
    result = assemble(units, [_make_lines(1), _make_lines(2)], "tutor-student", "Java Basics")
    unit_numbers = [l.unit_number for l in result]
    assert 1 in unit_numbers and 2 in unit_numbers


def test_assemble_outro_contains_memory_hooks():
    units = [_make_unit(1), _make_unit(2)]
    result = assemble(units, [_make_lines(1), _make_lines(2)], "tutor-student", "Java Basics")
    outro = result[-1]
    assert "Remember concept 1" in outro.text
    assert "Remember concept 2" in outro.text


def test_sanitizer_applied_no_symbols():
    units = [_make_unit(1)]
    lines = [DialogueLine(speaker="ALEX", text="Use List<String>", unit_number=1)]
    result = assemble(units, [lines], "tutor-student", "Java Basics")
    for line in result:
        assert "<" not in line.text, f"Symbol leak in: {line.text}"
