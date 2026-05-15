from tutor.audio import sanitizer
from tutor.models import DialogueLine, TeachingUnit


def assemble(
    units: list[TeachingUnit],
    all_lines: list[list[DialogueLine]],
    fmt: str,
    doc_title: str,
    mode: str = "conversation",
) -> list[DialogueLine]:
    result: list[DialogueLine] = []

    result.extend(_build_intro(units, doc_title, mode))

    for i, (unit, lines) in enumerate(zip(units, all_lines, strict=False)):
        result.extend(lines)
        if mode == "conversation" and i < len(units) - 1:
            next_concept = units[i + 1].concept if i + 1 < len(units) else ""
            result.append(
                DialogueLine(
                    speaker="MAYA",
                    text=f"Alright, let's move on to the next one: {next_concept}.",
                    unit_number=unit.unit,
                )
            )

    result.extend(_build_outro(units, doc_title, mode))

    for line in result:
        line.text = sanitizer.apply(line.text)

    return result


def _build_intro(units: list[TeachingUnit], doc_title: str, mode: str) -> list[DialogueLine]:
    if mode == "explain":
        text = (
            f"Let's walk through {doc_title}. "
            f"I'll cover {len(units)} section{'s' if len(units) != 1 else ''} from top to bottom, "
            f"following the document as you read along."
        )
        return [DialogueLine(speaker="ALEX", text=text, unit_number=0)]
    else:
        concepts = ", ".join(u.concept for u in units)
        alex_text = (
            f"Welcome. In this session we're covering {doc_title}. "
            f"We'll walk through {len(units)} concept{'s' if len(units) != 1 else ''} step by step: {concepts}."
        )
        maya_text = (
            "We'll explain each one clearly, with analogies, so by the end you'll have "
            "a solid picture of how it all fits together. Let's get into it."
        )
        return [
            DialogueLine(speaker="ALEX", text=alex_text, unit_number=0),
            DialogueLine(speaker="MAYA", text=maya_text, unit_number=0),
        ]


def _build_outro(units: list[TeachingUnit], doc_title: str, mode: str) -> list[DialogueLine]:
    if mode == "explain":
        text = (
            f"That covers all {len(units)} section{'s' if len(units) != 1 else ''} of {doc_title}. "
            f"You can replay any section with the replay command, or ask a question with ask."
        )
        return [DialogueLine(speaker="ALEX", text=text, unit_number=-1)]
    else:
        hooks = ". ".join(u.memory_hook for u in units if u.memory_hook)
        alex_text = (
            f"That's everything for {doc_title}. "
            f"We covered {len(units)} concept{'s' if len(units) != 1 else ''} today. "
            f"Here's what to hold onto: {hooks}."
        )
        maya_text = (
            "If any of those didn't fully click, replay that unit and let it settle. "
            "These are the ideas that show up constantly in real Java code."
        )
        return [
            DialogueLine(speaker="ALEX", text=alex_text, unit_number=-1),
            DialogueLine(speaker="MAYA", text=maya_text, unit_number=-1),
        ]
