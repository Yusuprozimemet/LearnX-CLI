from tutor.constants import WPM
from tutor.models import Chunk, DocProfile, TeachingUnit


def report_ingestion(profile: DocProfile, chunks: list[Chunk]) -> None:
    print("\n=== Ingestion Report ===")
    print(f"File:              {profile.filepath}")
    print(f"Raw size:          {profile.raw_bytes:,} bytes")
    print(f"Estimated tokens:  {profile.estimated_tokens:,}")
    print(f"Strategy:          {profile.strategy}")
    print(f"Sections found:    {profile.section_count}")
    print(f"Chunks created:    {len(chunks)}")

    if chunks:
        avg = sum(c.token_count for c in chunks) // len(chunks)
        largest = max(chunks, key=lambda c: c.token_count)
        code_count = sum(1 for c in chunks if c.has_code)
        print(f"  Avg chunk size:  {avg} tokens")
        print(f"  Largest chunk:   {largest.token_count} tokens  ({largest.chunk_id})")
        print(f"  Chunks with code: {code_count}/{len(chunks)}")

    print("\n=== Chunk Map ===")
    print(f"{'ID':<25} {'Heading':<35} {'Tokens':>7}  {'Code'}")
    print("-" * 75)
    for c in chunks:
        code_flag = "yes" if c.has_code else "no"
        print(f"{c.chunk_id:<25} {c.heading:<35} {c.token_count:>7}  {code_flag}")

    _report_warnings(chunks)
    _report_orphans(chunks)


def _report_warnings(chunks: list[Chunk]) -> None:
    from tutor.constants import MAX_CHUNK_TOKENS
    warnings = []
    for c in chunks:
        if c.token_count > MAX_CHUNK_TOKENS and c.has_code:
            warnings.append(f"! {c.chunk_id} — code block preserved intact at {c.token_count} tokens (correct behavior).")
        elif c.token_count > MAX_CHUNK_TOKENS:
            warnings.append(f"! {c.chunk_id} — {c.token_count} tokens, may produce shallow dialogue.")

    if warnings:
        print("\n=== Chunk Quality Warnings ===")
        for w in warnings:
            print(w)


def _report_orphans(chunks: list[Chunk]) -> None:
    orphans = [c for c in chunks if c.token_count < 200]
    if orphans:
        print("\n=== Orphan Risk ===")
        for c in orphans:
            print(f"  {c.chunk_id} ({c.token_count} tokens) — small section, may be skipped by planner")


def report_curriculum(
    units: list[TeachingUnit],
    chunks: list[Chunk],
    duration_min: int,
) -> None:
    print("\n=== Duration Plan ===")
    print(f"Target duration:   {duration_min} min")
    print(f"Word budget:       {duration_min * WPM} words (@ {WPM} WPM)")
    print(f"Silence overhead:  ~1m 20s")

    print("\n=== Teaching Units ===")
    header = f"{'':45} {'Complexity':>10}  {'Words':>7}  {'Est. time'}"
    print(header)
    print("-" * 80)

    intro_words = 100
    intro_secs = intro_words * 60 // WPM
    print(f"{'Intro':<45} {'—':>10}  {intro_words:>7}  {_fmt_time(intro_secs)}")

    total_words = intro_words
    total_secs = intro_secs

    for u in units:
        secs = u.word_budget * 60 // WPM
        label = f"Unit {u.unit}  \"{u.concept}\""
        print(f"{label:<45} {u.complexity:>10}  {u.word_budget:>7}  {_fmt_time(secs)}")
        total_words += u.word_budget
        total_secs += secs

    outro_words = 80
    outro_secs = outro_words * 60 // WPM
    print(f"{'Outro (memory hook recap)':<45} {'—':>10}  {outro_words:>7}  {_fmt_time(outro_secs)}")
    total_words += outro_words
    total_secs += outro_secs + 80  # silence overhead

    print("-" * 80)
    print(f"{'Total':<45} {'':>10}  {total_words:>7}  {_fmt_time(total_secs)}")

    used_ids = {sid for u in units for sid in u.source_sections}
    used = sum(1 for c in chunks if c.chunk_id in used_ids)
    pct = used / len(chunks) * 100 if chunks else 0
    skipped = [c.chunk_id for c in chunks if c.chunk_id not in used_ids]

    print(f"\n=== Coverage ===")
    print(f"Sections used:     {used}/{len(chunks)} ({pct:.1f}%)")
    if skipped:
        print(f"Sections skipped:  {', '.join(skipped[:8])}")
        if len(skipped) > 8:
            print(f"                   ... and {len(skipped) - 8} more")


def _fmt_time(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}m {s:02d}s"
