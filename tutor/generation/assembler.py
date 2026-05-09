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
            result.append(
                DialogueLine(
                    speaker="ALEX",
                    text="Now let's look at something related that catches people in a different way.",
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
    else:
        text = (
            f"Today we're covering {doc_title}. "
            f"By the end of this session, you'll understand {len(units)} concepts "
            f"that Java developers regularly get wrong. Let's start with a question."
        )
    return [DialogueLine(speaker="ALEX", text=text, unit_number=0)]


def _build_outro(units: list[TeachingUnit], doc_title: str, mode: str) -> list[DialogueLine]:
    if mode == "explain":
        text = (
            f"That covers all {len(units)} section{'s' if len(units) != 1 else ''} of {doc_title}. "
            f"You can replay any section with the replay command, or ask a question with ask."
        )
    else:
        hooks = ". ".join(u.memory_hook for u in units if u.memory_hook)
        text = (
            f"Before we finish — here are the things worth remembering. "
            f"{hooks}. Keep those in mind next time you're reading Java code."
        )
    return [DialogueLine(speaker="ALEX", text=text, unit_number=-1)]
