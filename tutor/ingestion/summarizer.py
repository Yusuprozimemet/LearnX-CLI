import hashlib
import logging
from pathlib import Path

from tutor.constants import PROMPT_VERSION, SUMMARY_CACHE_DIR
from tutor.infra.llm import load_prompt
from tutor.models import Chunk

log = logging.getLogger(__name__)


def summarize_all(
    chunks: list[Chunk],
    llm_fn,
    cache_dir: str = SUMMARY_CACHE_DIR,
) -> list[Chunk]:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    prompt_text = load_prompt("summarize.txt")

    for c in chunks:
        if c.chunk_id == "full_doc":
            c.summary = c.text[:500]
            continue

        cache_key = hashlib.md5((c.text + PROMPT_VERSION).encode()).hexdigest()
        cache_file = cache_path / f"{cache_key}.summary.txt"

        if cache_file.exists():
            c.summary = cache_file.read_text(encoding="utf-8")
            log.debug("Cache hit for chunk %s", c.chunk_id)
            continue

        log.info("Summarizing chunk %s (%d tokens)", c.chunk_id, c.token_count)
        messages = [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": c.text},
        ]
        summary = llm_fn(messages, call_type="summarize")
        cache_file.write_text(summary, encoding="utf-8")
        c.summary = summary

    return chunks
