import re

from tutor.constants import CODE_SUBSTITUTIONS


def apply(text: str) -> str:
    for pattern, replacement in CODE_SUBSTITUTIONS:
        text = re.sub(pattern, replacement, text)
    return text
