import re

from tutor.models import Chunk


def enrich(chunk: Chunk) -> Chunk:
    chunk.has_code = "```" in chunk.text

    raw_terms = re.findall(r"\*\*(.+?)\*\*|`(.+?)`", chunk.text)
    seen: set[str] = set()
    key_terms: list[str] = []
    for bold, code in raw_terms:
        term = bold or code
        if term and term not in seen:
            seen.add(term)
            key_terms.append(term)

    chunk.key_terms = key_terms
    return chunk
