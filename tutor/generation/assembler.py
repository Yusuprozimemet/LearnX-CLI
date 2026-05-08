from tutor.audio import sanitizer
from tutor.models import DialogueLine, TeachingUnit


def assemble(
    units: list[TeachingUnit],
    all_lines: list[list[DialogueLine]],
    fmt: str,
    doc_title: str,
) -> list[DialogueLine]:
    result: list[DialogueLine] = []

    result.extend(_build_intro(units, doc_title))

    for i, (unit, lines) in enumerate(zip(units, all_lines)):
        result.extend(lines)
        if i < len(units) - 1:
            result.append(
                DialogueLine(
                    speaker="ALEX",
                    text="Now let's look at something related that catches people in a different way.",
                    unit_number=unit.unit,
                )
            )

    result.extend(_build_outro(units))

    for line in result:
        line.text = sanitizer.apply(line.text)

    return result


def _build_intro(units: list[TeachingUnit], doc_title: str) -> list[DialogueLine]:
    text = (
        f"Today we're covering {doc_title}. "
        f"By the end of this session, you'll understand {len(units)} concepts "
        f"that Java developers regularly get wrong. Let's start with a question."
    )
    return [DialogueLine(speaker="ALEX", text=text, unit_number=0)]


def _build_outro(units: list[TeachingUnit]) -> list[DialogueLine]:
    hooks = ". ".join(u.memory_hook for u in units if u.memory_hook)
    text = (
        f"Before we finish — here are the things worth remembering. "
        f"{hooks}. Keep those in mind next time you're reading Java code."
    )
    return [DialogueLine(speaker="ALEX", text=text, unit_number=-1)]
